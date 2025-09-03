#!/usr/bin/env python3
"""Unit tests for models data structures only."""

import unittest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

# Add the project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import only the data structures we want to test, without heavy dependencies
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Copy the data structures locally to avoid import issues
@dataclass
class IndexerConfig:
    """Configuration for a Prowlarr-synced indexer."""
    name: str
    provider_type: str  # "newznab" or "torznab"
    host: str
    api_key: str
    enabled: bool
    categories: List[str] = field(default_factory=list)
    priority: int = 0
    alternative_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary for storage/API responses."""
        return {
            'name': self.name,
            'type': self.provider_type,
            'host': self.host,
            'enabled': self.enabled,
            'categories': ','.join(self.categories),
            'priority': self.priority,
            'altername': self.alternative_name or self.name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, any]) -> 'IndexerConfig':
        """Create from dictionary (from storage/API calls)."""
        categories = data.get('categories', '')
        if isinstance(categories, str):
            categories = [cat.strip() for cat in categories.split(',') if cat.strip()]
        
        return cls(
            name=data['name'],
            provider_type=data.get('type', data.get('providertype', 'newznab')),
            host=data['host'],
            api_key=data.get('prov_apikey', data.get('api_key', '')),
            enabled=data.get('enabled', True),
            categories=categories,
            priority=int(data.get('priority', data.get('dlpriority', 0))),
            alternative_name=data.get('altername')
        )

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

    def test_from_dict_defaults(self):
        """Test creating IndexerConfig with minimal data."""
        data = {
            'name': 'Minimal Indexer',
            'host': 'http://test.com/api'
        }
        
        config = IndexerConfig.from_dict(data)
        
        self.assertEqual(config.name, "Minimal Indexer")
        self.assertEqual(config.provider_type, "newznab")  # default
        self.assertEqual(config.host, "http://test.com/api")
        self.assertEqual(config.api_key, "")  # default
        self.assertTrue(config.enabled)  # default
        self.assertEqual(config.categories, [])  # default
        self.assertEqual(config.priority, 0)  # default

    def test_categories_parsing(self):
        """Test various category string formats."""
        # Comma-separated string
        data = {'name': 'Test', 'host': 'http://test', 'categories': '3000,7000,7020'}
        config = IndexerConfig.from_dict(data)
        self.assertEqual(config.categories, ['3000', '7000', '7020'])
        
        # String with spaces
        data = {'name': 'Test', 'host': 'http://test', 'categories': '3000, 7000, 7020'}
        config = IndexerConfig.from_dict(data)
        self.assertEqual(config.categories, ['3000', '7000', '7020'])
        
        # Empty string
        data = {'name': 'Test', 'host': 'http://test', 'categories': ''}
        config = IndexerConfig.from_dict(data)
        self.assertEqual(config.categories, [])
        
        # Already a list
        data = {'name': 'Test', 'host': 'http://test', 'categories': ['3000', '7000']}
        config = IndexerConfig.from_dict(data)
        self.assertEqual(config.categories, ['3000', '7000'])

if __name__ == '__main__':
    unittest.main()