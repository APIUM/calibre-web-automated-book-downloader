#!/usr/bin/env python3
"""Unit tests for Prowlarr integration functionality."""

import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the modules we're testing
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import IndexerConfig, IndexerManager, BookInfo, SearchFilters
import prowlarr_manager

class TestIndexerConfig(unittest.TestCase):
    """Test IndexerConfig data class functionality."""
    
    def test_create_indexer_config(self):
        """Test creating an IndexerConfig instance."""
        config = IndexerConfig(
            name="Test Indexer",
            provider_type="newznab",
            host="http://localhost:9696/1/api",
            api_key="test-key",
            enabled=True,
            categories=["3000", "7000"],
            priority=10
        )
        
        self.assertEqual(config.name, "Test Indexer")
        self.assertEqual(config.provider_type, "newznab")
        self.assertEqual(config.host, "http://localhost:9696/1/api")
        self.assertEqual(config.api_key, "test-key")
        self.assertTrue(config.enabled)
        self.assertEqual(config.categories, ["3000", "7000"])
        self.assertEqual(config.priority, 10)
    
    def test_to_dict(self):
        """Test converting IndexerConfig to dictionary."""
        config = IndexerConfig(
            name="Test Indexer",
            provider_type="torznab",
            host="http://localhost:9696/1/api",
            api_key="test-key",
            enabled=False,
            categories=["3000", "7000"],
            priority=5,
            alternative_name="Test Alt"
        )
        
        result = config.to_dict()
        expected = {
            'name': 'Test Indexer',
            'type': 'torznab',
            'host': 'http://localhost:9696/1/api',
            'enabled': False,
            'categories': '3000,7000',
            'priority': 5,
            'altername': 'Test Alt'
        }
        
        self.assertEqual(result, expected)
    
    def test_from_dict(self):
        """Test creating IndexerConfig from dictionary."""
        data = {
            'name': 'Test Indexer',
            'providertype': 'newznab',
            'host': 'http://localhost:9696/1/api',
            'prov_apikey': 'test-key',
            'enabled': 'true',
            'categories': '3000,7000',
            'dlpriority': '15',
            'altername': 'Test Alt'
        }
        
        config = IndexerConfig.from_dict(data)
        
        self.assertEqual(config.name, "Test Indexer")
        self.assertEqual(config.provider_type, "newznab")
        self.assertEqual(config.host, "http://localhost:9696/1/api")
        self.assertEqual(config.api_key, "test-key")
        self.assertTrue(config.enabled)
        self.assertEqual(config.categories, ["3000", "7000"])
        self.assertEqual(config.priority, 15)
        self.assertEqual(config.alternative_name, "Test Alt")


class TestIndexerManager(unittest.TestCase):
    """Test IndexerManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test config
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "indexers.json"
        
        # Create manager with custom config file
        self.manager = IndexerManager()
        self.manager._config_file = self.config_file
        self.manager._indexers = {}
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_add_indexer(self):
        """Test adding an indexer configuration."""
        config = IndexerConfig(
            name="Test Indexer",
            provider_type="newznab",
            host="http://localhost:9696/1/api",
            api_key="test-key",
            enabled=True,
            categories=["3000"],
            priority=10
        )
        
        self.manager.add_or_update_indexer(config)
        
        # Check that indexer was added
        self.assertIn("Test Indexer", self.manager._indexers)
        retrieved = self.manager.get_indexer("Test Indexer")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Test Indexer")
    
    def test_get_enabled_indexers(self):
        """Test getting only enabled indexers sorted by priority."""
        configs = [
            IndexerConfig("Indexer1", "newznab", "http://test1", "key1", True, [], 20),
            IndexerConfig("Indexer2", "torznab", "http://test2", "key2", False, [], 10),
            IndexerConfig("Indexer3", "newznab", "http://test3", "key3", True, [], 5),
        ]
        
        for config in configs:
            self.manager.add_or_update_indexer(config)
        
        enabled = self.manager.get_enabled_indexers()
        
        # Should only return enabled indexers, sorted by priority
        self.assertEqual(len(enabled), 2)
        self.assertEqual(enabled[0].name, "Indexer3")  # priority 5
        self.assertEqual(enabled[1].name, "Indexer1")  # priority 20
    
    def test_list_providers_api_response(self):
        """Test generating LazyLibrarian-style API response."""
        config = IndexerConfig(
            name="Test Indexer",
            provider_type="newznab",
            host="http://localhost:9696/1/api",
            api_key="test-key",
            enabled=True,
            categories=["3000", "7000"],
            priority=10,
            alternative_name="Test Alt"
        )
        
        self.manager.add_or_update_indexer(config)
        
        response = self.manager.list_providers_api_response()
        
        expected = {
            'Test Indexer': {
                'name': 'Test Indexer',
                'type': 'newznab',
                'host': 'http://localhost:9696/1/api',
                'enabled': True,
                'categories': '3000,7000',
                'priority': 10,
                'altername': 'Test Alt'
            }
        }
        
        self.assertEqual(response, expected)


class TestProwlarrManager(unittest.TestCase):
    """Test prowlarr_manager functionality."""
    
    @patch('prowlarr_manager.indexer_manager')
    def test_search_books_no_indexers(self, mock_manager):
        """Test search when no indexers are enabled."""
        mock_manager.get_enabled_indexers.return_value = []
        
        filters = SearchFilters()
        
        with self.assertRaises(Exception) as context:
            prowlarr_manager.search_books("test query", filters)
        
        self.assertIn("No indexers configured", str(context.exception))
    
    def test_build_search_url(self):
        """Test building search URLs for indexers."""
        indexer = IndexerConfig(
            name="Test Indexer",
            provider_type="newznab",
            host="http://localhost:9696/1/api",
            api_key="test-key",
            enabled=True,
            categories=["3000", "7000"]
        )
        
        filters = SearchFilters()
        url = prowlarr_manager._build_search_url(indexer, "test query", filters)
        
        self.assertIn("http://localhost:9696/1/api", url)
        self.assertIn("t=search", url)
        self.assertIn("q=test%20query", url)
        self.assertIn("apikey=test-key", url)
        self.assertIn("cat=3000,7000", url)
    
    def test_build_search_url_with_isbn(self):
        """Test building search URL with ISBN filter."""
        indexer = IndexerConfig(
            name="Test Indexer",
            provider_type="newznab",
            host="http://localhost:9696/1/api",
            api_key="test-key",
            enabled=True,
            categories=["3000"]
        )
        
        filters = SearchFilters(isbn=["9781234567890", "0123456789"])
        url = prowlarr_manager._build_search_url(indexer, "test", filters)
        
        # Should contain ISBN search terms
        self.assertIn("9781234567890", url)
        self.assertIn("0123456789", url)
    
    def test_parse_title_author(self):
        """Test parsing title and author from combined strings."""
        # Test "Author - Title" format
        title, author = prowlarr_manager._parse_title_author("Stephen King - The Shining")
        self.assertEqual(title, "The Shining")
        self.assertEqual(author, "Stephen King")
        
        # Test "Title by Author" format
        title, author = prowlarr_manager._parse_title_author("The Shining by Stephen King")
        self.assertEqual(title, "The Shining")
        self.assertEqual(author, "Stephen King")
        
        # Test no recognizable pattern
        title, author = prowlarr_manager._parse_title_author("Just a Title")
        self.assertEqual(title, "Just a Title")
        self.assertEqual(author, "")
    
    def test_extract_format_from_title(self):
        """Test extracting file format from titles."""
        self.assertEqual(prowlarr_manager._extract_format_from_title("Book Title [EPUB]"), "epub")
        self.assertEqual(prowlarr_manager._extract_format_from_title("Book Title.pdf"), "pdf")
        self.assertEqual(prowlarr_manager._extract_format_from_title("Book Title (MOBI)"), "mobi")
        self.assertEqual(prowlarr_manager._extract_format_from_title("Book Title"), "")
    
    def test_format_file_size(self):
        """Test file size formatting."""
        self.assertEqual(prowlarr_manager._format_file_size(500), "500 B")
        self.assertEqual(prowlarr_manager._format_file_size(1500), "1.5 KB")
        self.assertEqual(prowlarr_manager._format_file_size(1500000), "1.4 MB")
        self.assertEqual(prowlarr_manager._format_file_size(1500000000), "1.4 GB")


class TestProwlarrAPIEndpoints(unittest.TestCase):
    """Test the Prowlarr API endpoints in app.py."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Import after setting up paths
        from app import app
        self.app = app
        self.client = self.app.test_client()
    
    def test_api_help_endpoint(self):
        """Test the API help endpoint."""
        response = self.client.get('/api?cmd=help')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('listProviders', data)
        self.assertIn('changeProvider', data)
        self.assertIn('test', data)
    
    def test_api_test_endpoint(self):
        """Test the API connectivity test endpoint."""
        response = self.client.get('/api?cmd=test')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'OK')
        self.assertIn('version', data)
        self.assertIn('api', data)
    
    @patch('app.indexer_manager')
    def test_list_providers_endpoint(self, mock_manager):
        """Test the listProviders API endpoint."""
        mock_manager.list_providers_api_response.return_value = {
            'Test Indexer': {
                'name': 'Test Indexer',
                'type': 'newznab',
                'host': 'http://test',
                'enabled': True,
                'categories': '3000',
                'priority': 10,
                'altername': 'Test Indexer'
            }
        }
        
        response = self.client.get('/api?cmd=listProviders')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertIn('Test Indexer', data)
        self.assertEqual(data['Test Indexer']['type'], 'newznab')
    
    @patch('app.indexer_manager')
    def test_change_provider_endpoint(self, mock_manager):
        """Test the changeProvider API endpoint."""
        response = self.client.get('/api?cmd=changeProvider&name=TestIndexer&host=http://test&prov_apikey=testkey')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'OK')
        
        # Verify indexer_manager was called
        mock_manager.add_or_update_indexer.assert_called_once()
    
    def test_change_provider_missing_params(self):
        """Test changeProvider with missing required parameters."""
        response = self.client.get('/api?cmd=changeProvider&name=TestIndexer')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('Missing required parameters', data['error'])


if __name__ == '__main__':
    unittest.main()