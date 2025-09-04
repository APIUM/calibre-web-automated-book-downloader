#!/usr/bin/env python3
"""Unit tests for Prowlarr API compatibility based on LazyLibrarian format."""

import unittest
import json
import os
import sys
from unittest.mock import patch, MagicMock

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables to avoid logging issues and directory creation
os.environ['ENABLE_LOGGING'] = 'false'
os.environ['LOG_LEVEL'] = 'error'
os.environ['INGEST_DIR'] = '/tmp/test-ingest'  # Use temp directory for testing

from app import app
from models import IndexerConfig, IndexerManager, APIKeyManager

class TestProwlarrAPI(unittest.TestCase):
    """Test Prowlarr API compatibility."""
    
    def setUp(self):
        """Set up test environment."""
        self.app = app.test_client()
        self.app.testing = True
        
        # Mock API key manager for testing
        self.test_api_key = "test-api-key-12345"
        
        # Create test indexer configurations
        self.test_indexers = [
            IndexerConfig(
                name="TestNewznab",
                provider_type="newznab",
                host="https://api.nzbgeek.info",
                api_key="test-api-key",
                enabled=True,
                categories=["7000", "7020", "7030"],
                priority=1,
                alternative_name="NZBGeek"
            ),
            IndexerConfig(
                name="TestTorznab", 
                provider_type="torznab",
                host="https://torrentleech.org",
                api_key="torznab-key",
                enabled=True,
                categories=["3000", "8000"],
                priority=2,
                alternative_name="TorrentLeech"
            ),
            IndexerConfig(
                name="DisabledIndexer",
                provider_type="newznab", 
                host="https://disabled.example.com",
                api_key="disabled-key",
                enabled=False,
                categories=["7000"],
                priority=3,
                alternative_name=None
            )
        ]
    
    @patch('app.api_key_manager')
    @patch('app.indexer_manager')
    def test_test_endpoint_success(self, mock_indexer_manager, mock_api_key_manager):
        """Test the 'test' command endpoint."""
        # Test endpoint should work without API key
        response = self.app.get('/api?cmd=test')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'application/json')
        
        data = json.loads(response.data)
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'OK')
        self.assertIn('version', data)
        self.assertIn('api', data)
    
    @patch('app.api_key_manager')
    @patch('app.indexer_manager')
    def test_listProviders_with_valid_api_key(self, mock_indexer_manager, mock_api_key_manager):
        """Test listProviders command with valid API key."""
        # Mock API key validation
        mock_api_key_manager.is_valid_api_key.return_value = True
        
        # Mock indexer manager response
        expected_response = {
            "Data": {
                "Newznabs": [
                    {
                        "ENABLED": True,
                        "NAME": "TestNewznab", 
                        "HOST": "https://api.nzbgeek.info",
                        "API": "test-api-key",
                        "CATEGORIES": "7000,7020,7030",
                        "PRIORITY": 1
                    },
                    {
                        "ENABLED": False,
                        "NAME": "DisabledIndexer",
                        "HOST": "https://disabled.example.com", 
                        "API": "disabled-key",
                        "CATEGORIES": "7000",
                        "PRIORITY": 3
                    }
                ],
                "Torznabs": [
                    {
                        "ENABLED": True,
                        "NAME": "TestTorznab",
                        "HOST": "https://torrentleech.org",
                        "API": "torznab-key", 
                        "CATEGORIES": "3000,8000",
                        "PRIORITY": 2
                    }
                ],
                "RSS": []
            }
        }
        mock_indexer_manager.list_providers_api_response.return_value = expected_response
        
        response = self.app.get(f'/api?cmd=listProviders&apikey={self.test_api_key}')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'application/json')
        
        data = json.loads(response.data)
        self.assertIn('Data', data)
        self.assertIn('Newznabs', data['Data'])
        self.assertIn('Torznabs', data['Data'])
        self.assertIn('RSS', data['Data'])
        
        # Verify structure matches LazyLibrarian format
        newznabs = data['Data']['Newznabs']
        self.assertEqual(len(newznabs), 2)
        
        # Check first newznab entry
        first_newznab = newznabs[0]
        required_fields = ['ENABLED', 'NAME', 'HOST', 'API', 'CATEGORIES', 'PRIORITY']
        for field in required_fields:
            self.assertIn(field, first_newznab)
        
        # Verify boolean field is proper boolean (not null)
        self.assertIsInstance(first_newznab['ENABLED'], bool)
    
    @patch('app.api_key_manager')
    def test_listProviders_without_api_key(self, mock_api_key_manager):
        """Test listProviders command without API key should fail."""
        response = self.app.get('/api?cmd=listProviders')
        
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'API key required')
    
    @patch('app.api_key_manager')
    def test_listProviders_with_invalid_api_key(self, mock_api_key_manager):
        """Test listProviders command with invalid API key should fail."""
        mock_api_key_manager.is_valid_api_key.return_value = False
        
        response = self.app.get('/api?cmd=listProviders&apikey=invalid-key')
        
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Invalid API key')
    
    @patch('app.api_key_manager')
    @patch('app.indexer_manager')
    def test_changeProvider_add_new_indexer(self, mock_indexer_manager, mock_api_key_manager):
        """Test changeProvider command to add a new indexer."""
        mock_api_key_manager.is_valid_api_key.return_value = True
        mock_indexer_manager.add_or_update_indexer = MagicMock()
        
        # Test data matching what Prowlarr would send
        params = {
            'cmd': 'changeProvider',
            'apikey': self.test_api_key,
            'name': 'NewIndexer',
            'host': 'https://new-indexer.com',
            'type': 'newznab',
            'prov_apikey': 'new-api-key',
            'enabled': 'true',
            'categories': '7000,7020',
            'priority': '5'
        }
        
        response = self.app.get('/api', query_string=params)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'application/json')
        
        data = json.loads(response.data)
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'OK')
        
        # Verify indexer manager was called
        mock_indexer_manager.add_or_update_indexer.assert_called_once()
    
    @patch('app.api_key_manager') 
    def test_changeProvider_missing_required_params(self, mock_api_key_manager):
        """Test changeProvider command with missing required parameters."""
        mock_api_key_manager.is_valid_api_key.return_value = True
        
        # Missing 'host' parameter
        params = {
            'cmd': 'changeProvider',
            'apikey': self.test_api_key,
            'name': 'IncompleteIndexer'
            # 'host' is missing
        }
        
        response = self.app.get('/api', query_string=params)
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('Missing required parameters', data['error'])
    
    def test_help_endpoint(self):
        """Test the help command endpoint."""
        response = self.app.get('/api?cmd=help')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'application/json')
        
        data = json.loads(response.data)
        
        # Should contain help for all supported commands
        expected_commands = ['listProviders', 'changeProvider', 'test']
        for command in expected_commands:
            self.assertIn(command, data)
    
    def test_unknown_command(self):
        """Test unknown command returns error."""
        response = self.app.get('/api?cmd=unknowncommand')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('Unknown command', data['error'])
    
    def test_no_command_parameter(self):
        """Test API call without cmd parameter."""
        response = self.app.get('/api')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_response_content_type_headers(self):
        """Test that all API responses have proper content-type headers."""
        endpoints_to_test = [
            '/api?cmd=test',
            '/api?cmd=help',
            '/api?cmd=unknowncommand'
        ]
        
        for endpoint in endpoints_to_test:
            with self.subTest(endpoint=endpoint):
                response = self.app.get(endpoint)
                # All responses should be JSON
                self.assertEqual(response.headers.get('Content-Type'), 'application/json')


class TestLazyLibrarianAPIFormat(unittest.TestCase):
    """Test that our API format exactly matches LazyLibrarian expectations."""
    
    def setUp(self):
        """Set up test environment."""
        # Create real IndexerManager for integration testing
        self.indexer_manager = IndexerManager()
        
        # Add test data
        test_configs = [
            {
                'name': 'TestNewznab',
                'type': 'newznab', 
                'host': 'https://api.nzbgeek.info',
                'prov_apikey': 'test-api-key',
                'enabled': True,
                'categories': '7000,7020',
                'priority': 1,
                'altername': 'NZBGeek'
            },
            {
                'name': 'TestTorznab',
                'type': 'torznab',
                'host': 'https://torrentleech.org', 
                'prov_apikey': 'torznab-key',
                'enabled': True,
                'categories': '3000',
                'priority': 2,
                'altername': 'TorrentLeech'
            }
        ]
        
        for config_data in test_configs:
            indexer = IndexerConfig.from_dict(config_data)
            self.indexer_manager.add_or_update_indexer(indexer)
    
    def test_list_providers_response_format(self):
        """Test that listProviders response matches LazyLibrarian format exactly."""
        response = self.indexer_manager.list_providers_api_response()
        
        # Top level should have 'Data' key
        self.assertIn('Data', response)
        
        data = response['Data']
        
        # Should have all three provider type arrays
        required_arrays = ['Newznabs', 'Torznabs', 'RSS']
        for array_name in required_arrays:
            self.assertIn(array_name, data)
            self.assertIsInstance(data[array_name], list)
        
        # Check Newznab format
        newznabs = data['Newznabs']
        self.assertGreater(len(newznabs), 0)
        
        first_newznab = newznabs[0]
        required_fields = ['ENABLED', 'NAME', 'HOST', 'API', 'CATEGORIES', 'PRIORITY']
        
        for field in required_fields:
            self.assertIn(field, first_newznab)
        
        # Verify field types
        self.assertIsInstance(first_newznab['ENABLED'], bool)
        self.assertIsInstance(first_newznab['NAME'], str)
        self.assertIsInstance(first_newznab['HOST'], str)
        self.assertIsInstance(first_newznab['API'], str)
        self.assertIsInstance(first_newznab['CATEGORIES'], str)
        self.assertIsInstance(first_newznab['PRIORITY'], int)
        
        # Check Torznab format
        torznabs = data['Torznabs']
        self.assertGreater(len(torznabs), 0)
        
        first_torznab = torznabs[0]
        for field in required_fields:
            self.assertIn(field, first_torznab)
    
    def test_boolean_values_never_null(self):
        """Test that ENABLED field is never null/None."""
        response = self.indexer_manager.list_providers_api_response()
        
        all_providers = (
            response['Data']['Newznabs'] + 
            response['Data']['Torznabs']
        )
        
        for provider in all_providers:
            self.assertIsNotNone(provider['ENABLED'])
            self.assertIsInstance(provider['ENABLED'], bool)
    
    def test_string_fields_never_null(self):
        """Test that string fields are never null/None."""
        response = self.indexer_manager.list_providers_api_response()
        
        all_providers = (
            response['Data']['Newznabs'] + 
            response['Data']['Torznabs']
        )
        
        string_fields = ['NAME', 'HOST', 'API', 'CATEGORIES']
        
        for provider in all_providers:
            for field in string_fields:
                self.assertIsNotNone(provider[field])
                self.assertIsInstance(provider[field], str)


if __name__ == '__main__':
    unittest.main()