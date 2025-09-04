#!/usr/bin/env python3
"""Unit tests for API format compatibility based on LazyLibrarian format."""

import unittest
import json
import os
import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables to avoid issues
os.environ['ENABLE_LOGGING'] = 'false'
os.environ['LOG_LEVEL'] = 'error'

from models import IndexerConfig, IndexerManager


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
            },
            {
                'name': 'DisabledIndexer',
                'type': 'newznab',
                'host': 'https://disabled.example.com',
                'prov_apikey': 'disabled-key',
                'enabled': False,  # Test disabled indexer
                'categories': '7000',
                'priority': 3,
                'altername': None
            }
        ]
        
        for config_data in test_configs:
            indexer = IndexerConfig.from_dict(config_data)
            self.indexer_manager.add_or_update_indexer(indexer)
    
    def test_list_providers_response_format(self):
        """Test that listProviders response matches LazyLibrarian format exactly."""
        response = self.indexer_manager.list_providers_api_response()
        
        print("API Response:")
        print(json.dumps(response, indent=2))
        
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
            print(f"Provider: {provider['NAME']}, ENABLED: {provider['ENABLED']} (type: {type(provider['ENABLED'])})")
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
                print(f"Provider: {provider['NAME']}, {field}: '{provider[field]}' (type: {type(provider[field])})")
                self.assertIsNotNone(provider[field])
                self.assertIsInstance(provider[field], str)
    
    def test_provider_separation_by_type(self):
        """Test that providers are correctly separated into Newznabs and Torznabs."""
        response = self.indexer_manager.list_providers_api_response()
        
        # Should have both types
        self.assertGreater(len(response['Data']['Newznabs']), 0)
        self.assertGreater(len(response['Data']['Torznabs']), 0)
        
        # Total should match what we added
        total_providers = len(response['Data']['Newznabs']) + len(response['Data']['Torznabs'])
        self.assertEqual(total_providers, 3)  # 2 newznab (including disabled) + 1 torznab
    
    def test_disabled_indexers_included(self):
        """Test that disabled indexers are included with ENABLED=false."""
        response = self.indexer_manager.list_providers_api_response()
        
        all_providers = (
            response['Data']['Newznabs'] + 
            response['Data']['Torznabs']
        )
        
        disabled_providers = [p for p in all_providers if not p['ENABLED']]
        self.assertEqual(len(disabled_providers), 1)
        self.assertEqual(disabled_providers[0]['NAME'], 'DisabledIndexer')
    
    def test_categories_format(self):
        """Test that categories are properly formatted as comma-separated string."""
        response = self.indexer_manager.list_providers_api_response()
        
        all_providers = (
            response['Data']['Newznabs'] + 
            response['Data']['Torznabs']
        )
        
        for provider in all_providers:
            categories = provider['CATEGORIES']
            self.assertIsInstance(categories, str)
            # Should be comma-separated if multiple categories
            if ',' in categories:
                category_list = categories.split(',')
                for cat in category_list:
                    self.assertRegex(cat.strip(), r'^\d+$')  # Should be numeric
    
    def test_priority_is_integer(self):
        """Test that priority is always an integer."""
        response = self.indexer_manager.list_providers_api_response()
        
        all_providers = (
            response['Data']['Newznabs'] + 
            response['Data']['Torznabs']
        )
        
        for provider in all_providers:
            priority = provider['PRIORITY']
            self.assertIsInstance(priority, int)
            self.assertGreaterEqual(priority, 0)


class TestIndexerConfig(unittest.TestCase):
    """Test IndexerConfig creation and validation."""
    
    def test_from_dict_creation(self):
        """Test creating IndexerConfig from dictionary."""
        config_data = {
            'name': 'TestProvider',
            'type': 'newznab',
            'host': 'https://test.example.com',
            'prov_apikey': 'test-key',
            'enabled': 'true',  # String boolean
            'categories': '7000,7020',
            'priority': '5',  # String number
            'altername': 'Alternative Name'
        }
        
        config = IndexerConfig.from_dict(config_data)
        
        self.assertEqual(config.name, 'TestProvider')
        self.assertEqual(config.provider_type, 'newznab')
        self.assertEqual(config.host, 'https://test.example.com')
        self.assertEqual(config.api_key, 'test-key')
        self.assertTrue(config.enabled)  # Should be converted to boolean
        self.assertEqual(config.categories, ['7000', '7020'])
        self.assertEqual(config.priority, 5)  # Should be converted to int
        self.assertEqual(config.alternative_name, 'Alternative Name')
    
    def test_from_dict_with_missing_optional_fields(self):
        """Test creating IndexerConfig with minimal required fields."""
        config_data = {
            'name': 'MinimalProvider',
            'host': 'https://minimal.example.com'
        }
        
        config = IndexerConfig.from_dict(config_data)
        
        self.assertEqual(config.name, 'MinimalProvider')
        self.assertEqual(config.provider_type, 'newznab')  # Default
        self.assertEqual(config.host, 'https://minimal.example.com')
        self.assertEqual(config.api_key, '')  # Default
        self.assertTrue(config.enabled)  # Default
        self.assertEqual(config.categories, [])  # Default
        self.assertEqual(config.priority, 0)  # Default
        self.assertIsNone(config.alternative_name)  # Default
    
    def test_boolean_conversion(self):
        """Test that string booleans are properly converted."""
        test_cases = [
            ('true', True),
            ('True', True),
            ('TRUE', True),
            ('false', False),
            ('False', False),
            ('FALSE', False),
            ('', False),  # Empty string should be False
            ('yes', False),  # Anything else should be False
            ('1', False),  # Numbers as strings should be False
        ]
        
        for input_val, expected in test_cases:
            with self.subTest(input_val=input_val):
                config_data = {
                    'name': 'TestProvider',
                    'host': 'https://test.example.com',
                    'enabled': input_val
                }
                
                config = IndexerConfig.from_dict(config_data)
                self.assertEqual(config.enabled, expected)


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)