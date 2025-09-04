#!/usr/bin/env python3
"""Unit tests for API key management functionality."""

import unittest
import tempfile
import os
import uuid
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Add the project root to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment variables to avoid logging issues
os.environ['ENABLE_LOGGING'] = 'false'
os.environ['LOG_LEVEL'] = 'error'

# Import the APIKeyManager class
from models import APIKeyManager


class TestAPIKeyManager(unittest.TestCase):
    """Test APIKeyManager functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.api_key_file = Path(self.temp_dir) / "api_key.txt"
    
    def tearDown(self):
        """Clean up test environment."""
        if self.api_key_file.exists():
            self.api_key_file.unlink()
        os.rmdir(self.temp_dir)
    
    def test_create_api_key_manager_new_file(self):
        """Test creating APIKeyManager when no existing key file exists."""
        # Create manager with patched file path
        with patch.object(Path, 'exists', return_value=False), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch.object(Path, 'parent') as mock_parent:
            
            mock_parent.mkdir = lambda exist_ok: None
            
            manager = APIKeyManager()
            manager._api_key_file = self.api_key_file
            
            # Should generate a new UUID key
            api_key = manager.get_api_key()
            self.assertIsNotNone(api_key)
            self.assertEqual(len(api_key), 36)  # UUID format
            
            # Should be a valid UUID
            try:
                uuid.UUID(api_key)
            except ValueError:
                self.fail("Generated API key is not a valid UUID")
    
    def test_load_existing_api_key(self):
        """Test loading existing API key from file."""
        # Create a test UUID key
        test_key = str(uuid.uuid4())
        
        # Mock file operations to simulate existing file
        with patch.object(Path, 'exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=test_key)):
            
            manager = APIKeyManager()
            
            # Should load the existing key
            api_key = manager.get_api_key()
            self.assertEqual(api_key, test_key)
    
    def test_is_valid_api_key_correct(self):
        """Test API key validation with correct key."""
        with patch.object(Path, 'exists', return_value=False), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch.object(Path, 'parent') as mock_parent:
            
            mock_parent.mkdir = lambda exist_ok: None
            
            manager = APIKeyManager()
            api_key = manager.get_api_key()
            
            # Should validate correctly
            self.assertTrue(manager.is_valid_api_key(api_key))
    
    def test_is_valid_api_key_incorrect(self):
        """Test API key validation with incorrect key."""
        with patch.object(Path, 'exists', return_value=False), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch.object(Path, 'parent') as mock_parent:
            
            mock_parent.mkdir = lambda exist_ok: None
            
            manager = APIKeyManager()
            
            # Should reject incorrect key
            wrong_key = str(uuid.uuid4())
            self.assertFalse(manager.is_valid_api_key(wrong_key))
    
    def test_is_valid_api_key_empty(self):
        """Test API key validation with empty/None key."""
        with patch.object(Path, 'exists', return_value=False), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch.object(Path, 'parent') as mock_parent:
            
            mock_parent.mkdir = lambda exist_ok: None
            
            manager = APIKeyManager()
            
            # Should reject empty/None keys
            self.assertFalse(manager.is_valid_api_key(""))
            self.assertFalse(manager.is_valid_api_key(None))
    
    def test_thread_safety(self):
        """Test thread safety of API key operations."""
        import threading
        
        with patch.object(Path, 'exists', return_value=False), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch.object(Path, 'parent') as mock_parent:
            
            mock_parent.mkdir = lambda exist_ok: None
            
            manager = APIKeyManager()
            
            results = []
            
            def get_key():
                results.append(manager.get_api_key())
            
            # Create multiple threads
            threads = []
            for _ in range(10):
                thread = threading.Thread(target=get_key)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            # All threads should get the same key
            self.assertEqual(len(set(results)), 1)
            self.assertEqual(len(results), 10)
    
    def test_file_creation_error_handling(self):
        """Test error handling when file cannot be created."""
        # Simulate file creation failure
        with patch.object(Path, 'exists', return_value=False), \
             patch('builtins.open', side_effect=PermissionError("Cannot create file")), \
             patch.object(Path, 'parent') as mock_parent:
            
            mock_parent.mkdir = MagicMock(side_effect=PermissionError("Cannot create directory"))
            
            # Should not raise exception, but should still work in memory
            manager = APIKeyManager()
            api_key = manager.get_api_key()
            
            # Should still generate a valid key
            self.assertIsNotNone(api_key)
            self.assertEqual(len(api_key), 36)
    
    def test_file_read_error_handling(self):
        """Test error handling when existing file has invalid content."""
        # Simulate file with invalid content
        with patch.object(Path, 'exists', return_value=True), \
             patch('builtins.open', mock_open(read_data="")) as mock_file:
            
            # Should generate new key when existing file is empty/invalid
            manager = APIKeyManager()
            api_key = manager.get_api_key()
            
            # Should be a valid UUID (new key generated)
            try:
                uuid.UUID(api_key)
            except ValueError:
                self.fail("Should generate new valid UUID when existing file is invalid")


if __name__ == '__main__':
    unittest.main()