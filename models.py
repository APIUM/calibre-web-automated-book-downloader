"""Data structures and models used across the application."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime, timedelta
from threading import Lock, Event
from pathlib import Path
import queue
import time
import uuid
from env import INGEST_DIR, STATUS_TIMEOUT
import json

class QueueStatus(str, Enum):
    """Enum for possible book queue statuses."""
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    AVAILABLE = "available"
    ERROR = "error"
    DONE = "done"
    CANCELLED = "cancelled"

@dataclass
class QueueItem:
    """Queue item with priority and metadata."""
    book_id: str
    priority: int
    added_time: float
    
    def __lt__(self, other):
        """Compare items for priority queue (lower priority number = higher precedence)."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.added_time < other.added_time

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
            enabled=str(data.get('enabled', 'true')).lower() == 'true',
            categories=categories,
            priority=int(data.get('priority', data.get('dlpriority', 0))),
            alternative_name=data.get('altername')
        )

@dataclass
class BookInfo:
    """Data class representing book information."""
    id: str
    title: str
    preview: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[str] = None
    language: Optional[str] = None
    format: Optional[str] = None
    size: Optional[str] = None
    info: Optional[Dict[str, List[str]]] = None
    download_urls: List[str] = field(default_factory=list)
    download_path: Optional[str] = None
    priority: int = 0
    progress: Optional[float] = None
    indexer_name: Optional[str] = None  # Track which indexer found this book

class BookQueue:
    """Thread-safe book queue manager with priority support and cancellation."""
    def __init__(self) -> None:
        self._queue: queue.PriorityQueue[QueueItem] = queue.PriorityQueue()
        self._lock = Lock()
        self._status: dict[str, QueueStatus] = {}
        self._book_data: dict[str, BookInfo] = {}
        self._status_timestamps: dict[str, datetime] = {}  # Track when each status was last updated
        self._status_timeout = timedelta(seconds=STATUS_TIMEOUT)  # 1 hour timeout
        self._cancel_flags: dict[str, Event] = {}  # Cancellation flags for active downloads
        self._active_downloads: dict[str, bool] = {}  # Track currently downloading books
    
    def add(self, book_id: str, book_data: BookInfo, priority: int = 0) -> None:
        """Add a book to the queue with specified priority.
        
        Args:
            book_id: Unique identifier for the book
            book_data: Book information
            priority: Priority level (lower number = higher priority)
        """
        with self._lock:
            # Don't add if already exists and not in error/done state
            if book_id in self._status and self._status[book_id] not in [QueueStatus.ERROR, QueueStatus.DONE, QueueStatus.CANCELLED]:
                return
                
            book_data.priority = priority
            queue_item = QueueItem(book_id, priority, time.time())
            self._queue.put(queue_item)
            self._book_data[book_id] = book_data
            self._update_status(book_id, QueueStatus.QUEUED)
    
    def get_next(self) -> Optional[Tuple[str, Event]]:
        """Get next book ID from queue with cancellation flag.
        
        Returns:
            Tuple of (book_id, cancel_flag) or None if queue is empty
        """
        try:
            queue_item = self._queue.get_nowait()
            book_id = queue_item.book_id
            
            with self._lock:
                # Check if book was cancelled while in queue
                if book_id in self._status and self._status[book_id] == QueueStatus.CANCELLED:
                    return self.get_next()  # Recursively get next non-cancelled item
                
                # Create cancellation flag for this download
                cancel_flag = Event()
                self._cancel_flags[book_id] = cancel_flag
                self._active_downloads[book_id] = True
                
            return book_id, cancel_flag
        except queue.Empty:
            return None
            
    def _update_status(self, book_id: str, status: QueueStatus) -> None:
        """Internal method to update status and timestamp."""
        self._status[book_id] = status
        self._status_timestamps[book_id] = datetime.now()
            
    def update_status(self, book_id: str, status: QueueStatus) -> None:
        """Update status of a book in the queue."""
        with self._lock:
            self._update_status(book_id, status)
            
            # Clean up active download tracking when finished
            if status in [QueueStatus.AVAILABLE, QueueStatus.ERROR, QueueStatus.DONE, QueueStatus.CANCELLED]:
                self._active_downloads.pop(book_id, None)
                self._cancel_flags.pop(book_id, None)
    
    def update_download_path(self, book_id: str, download_path: str) -> None:
        """Update the download path of a book in the queue."""
        with self._lock:
            if book_id in self._book_data:
                self._book_data[book_id].download_path = download_path
                
    def update_progress(self, book_id: str, progress: float) -> None:
        """Update download progress for a book."""
        with self._lock:
            if book_id in self._book_data:
                self._book_data[book_id].progress = progress
            
    def get_status(self) -> Dict[QueueStatus, Dict[str, BookInfo]]:
        """Get current queue status."""
        self.refresh()
        with self._lock:
            result: Dict[QueueStatus, Dict[str, BookInfo]] = {status: {} for status in QueueStatus}
            for book_id, status in self._status.items():
                if book_id in self._book_data:
                    result[status][book_id] = self._book_data[book_id]
            return result
            
    def get_queue_order(self) -> List[Dict[str, any]]:
        """Get current queue order for display."""
        with self._lock:
            queue_items = []
            
            # Get items from priority queue without removing them
            temp_items = []
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    temp_items.append(item)
                    if item.book_id in self._book_data:
                        book_info = self._book_data[item.book_id]
                        queue_items.append({
                            'id': item.book_id,
                            'title': book_info.title,
                            'author': book_info.author,
                            'priority': item.priority,
                            'added_time': item.added_time,
                            'status': self._status.get(item.book_id, QueueStatus.QUEUED)
                        })
                except queue.Empty:
                    break
            
            # Put items back in queue
            for item in temp_items:
                self._queue.put(item)
                
            return sorted(queue_items, key=lambda x: (x['priority'], x['added_time']))
            
    def cancel_download(self, book_id: str) -> bool:
        """Cancel a download and mark it as cancelled.
        
        Args:
            book_id: Book identifier to cancel
            
        Returns:
            bool: True if cancellation was successful
        """
        with self._lock:
            current_status = self._status.get(book_id)
            
            if current_status == QueueStatus.DOWNLOADING:
                # Signal active download to stop
                if book_id in self._cancel_flags:
                    self._cancel_flags[book_id].set()
                self._update_status(book_id, QueueStatus.CANCELLED)
                return True
            elif current_status == QueueStatus.QUEUED:
                # Remove from queue and mark as cancelled
                self._update_status(book_id, QueueStatus.CANCELLED)
                return True
            
            return False
            
    def set_priority(self, book_id: str, new_priority: int) -> bool:
        """Change the priority of a queued book.
        
        Args:
            book_id: Book identifier
            new_priority: New priority level (lower = higher priority)
            
        Returns:
            bool: True if priority was successfully changed
        """
        with self._lock:
            if book_id not in self._status or self._status[book_id] != QueueStatus.QUEUED:
                return False
                
            # Remove book from queue and re-add with new priority
            temp_items = []
            found = False
            
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    if item.book_id == book_id:
                        # Create new item with updated priority
                        new_item = QueueItem(book_id, new_priority, item.added_time)
                        temp_items.append(new_item)
                        found = True
                        # Update book data priority
                        if book_id in self._book_data:
                            self._book_data[book_id].priority = new_priority
                    else:
                        temp_items.append(item)
                except queue.Empty:
                    break
            
            # Put all items back
            for item in temp_items:
                self._queue.put(item)
                
            return found
            
    def reorder_queue(self, book_priorities: Dict[str, int]) -> bool:
        """Bulk reorder queue by setting new priorities.
        
        Args:
            book_priorities: Dict mapping book_id to new priority
            
        Returns:
            bool: True if reordering was successful
        """
        with self._lock:
            # Extract all items from queue
            all_items = []
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    # Update priority if specified
                    if item.book_id in book_priorities:
                        new_priority = book_priorities[item.book_id]
                        item = QueueItem(item.book_id, new_priority, item.added_time)
                        # Update book data priority
                        if item.book_id in self._book_data:
                            self._book_data[item.book_id].priority = new_priority
                    all_items.append(item)
                except queue.Empty:
                    break
            
            # Put all items back with updated priorities
            for item in all_items:
                self._queue.put(item)
                
            return True
            
    def get_active_downloads(self) -> List[str]:
        """Get list of currently active download book IDs."""
        with self._lock:
            return list(self._active_downloads.keys())
            
    def clear_completed(self) -> int:
        """Remove all completed, errored, or cancelled books from tracking.
        
        Returns:
            int: Number of books removed
        """
        with self._lock:
            to_remove = []
            for book_id, status in self._status.items():
                if status in [QueueStatus.DONE, QueueStatus.ERROR, QueueStatus.CANCELLED]:
                    to_remove.append(book_id)
            
            removed_count = len(to_remove)
            for book_id in to_remove:
                self._status.pop(book_id, None)
                self._status_timestamps.pop(book_id, None)
                self._book_data.pop(book_id, None)
                self._cancel_flags.pop(book_id, None)
                self._active_downloads.pop(book_id, None)
                
            return removed_count
        
    def refresh(self) -> None:
        """Remove any books that are done downloading or have stale status."""
        with self._lock:
            current_time = datetime.now()
            
            # Create a list of items to remove to avoid modifying dict during iteration
            to_remove = []
            
            for book_id, status in self._status.items():
                path = self._book_data[book_id].download_path
                if path and not Path(path).exists():
                    self._book_data[book_id].download_path = None
                    path = None
                
                # Check for completed downloads
                if status == QueueStatus.AVAILABLE:
                    if not path:
                        self._update_status(book_id, QueueStatus.DONE)
                
                # Check for stale status entries
                last_update = self._status_timestamps.get(book_id)
                if last_update and (current_time - last_update) > self._status_timeout:
                    if status in [QueueStatus.DONE, QueueStatus.ERROR, QueueStatus.AVAILABLE, QueueStatus.CANCELLED]:
                        to_remove.append(book_id)
            
            # Remove stale entries
            for book_id in to_remove:
                del self._status[book_id]
                del self._status_timestamps[book_id]
                if book_id in self._book_data:
                    del self._book_data[book_id]

    def set_status_timeout(self, hours: int) -> None:
        """Set the status timeout duration in hours."""
        with self._lock:
            self._status_timeout = timedelta(hours=hours)


class APIKeyManager:
    """Thread-safe API key manager."""
    def __init__(self):
        self._lock = Lock()
        self._api_key: Optional[str] = None
        self._api_key_file = Path("data/api_key.txt")
        self._load_api_key()
    
    def _load_api_key(self) -> None:
        """Load API key from file or generate new one."""
        try:
            if self._api_key_file.exists():
                with open(self._api_key_file, 'r') as f:
                    self._api_key = f.read().strip()
                    if self._api_key:
                        from logger import setup_logger
                        logger = setup_logger(__name__)
                        logger.info(f"Loaded existing API key")
                        return
            
            # Generate new API key if file doesn't exist or is empty
            self._generate_new_api_key()
        except Exception as e:
            from logger import setup_logger
            logger = setup_logger(__name__)
            logger.error(f"Failed to load API key: {e}")
            self._generate_new_api_key()
    
    def _generate_new_api_key(self) -> None:
        """Generate a new UUID-based API key."""
        try:
            self._api_key = str(uuid.uuid4())
            
            # Ensure data directory exists
            self._api_key_file.parent.mkdir(exist_ok=True)
            
            # Save to file
            with open(self._api_key_file, 'w') as f:
                f.write(self._api_key)
            
            from logger import setup_logger
            logger = setup_logger(__name__)
            logger.info(f"Generated new API key and saved to {self._api_key_file}")
            
        except Exception as e:
            from logger import setup_logger
            logger = setup_logger(__name__)
            logger.error(f"Failed to generate API key: {e}")
            # Fallback to a temporary UUID if file operations fail
            self._api_key = str(uuid.uuid4())
    
    def get_api_key(self) -> str:
        """Get the current API key."""
        with self._lock:
            return self._api_key or "fallback-key"
    
    def is_valid_api_key(self, provided_key: str) -> bool:
        """Check if the provided API key is valid."""
        with self._lock:
            return self._api_key and provided_key == self._api_key

class IndexerManager:
    """Thread-safe indexer configuration manager."""
    def __init__(self):
        self._lock = Lock()
        self._indexers: Dict[str, IndexerConfig] = {}
        self._config_file = Path("data/indexers.json")
        self._load_config()
    
    def _load_config(self) -> None:
        """Load indexer configurations from file."""
        try:
            if self._config_file.exists():
                with open(self._config_file, 'r') as f:
                    data = json.load(f)
                    for name, config_data in data.items():
                        self._indexers[name] = IndexerConfig.from_dict(config_data)
        except Exception as e:
            from logger import setup_logger
            logger = setup_logger(__name__)
            logger.error(f"Failed to load indexer config: {e}")
    
    def _save_config(self) -> None:
        """Save indexer configurations to file."""
        try:
            self._config_file.parent.mkdir(exist_ok=True)
            data = {name: config.to_dict() for name, config in self._indexers.items()}
            with open(self._config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            from logger import setup_logger
            logger = setup_logger(__name__)
            logger.error(f"Failed to save indexer config: {e}")
    
    def add_or_update_indexer(self, indexer: IndexerConfig) -> None:
        """Add or update an indexer configuration."""
        with self._lock:
            self._indexers[indexer.name] = indexer
            self._save_config()
    
    def remove_indexer(self, name: str) -> None:
        """Remove an indexer configuration."""
        with self._lock:
            if name in self._indexers:
                del self._indexers[name]
                self._save_config()
    
    def get_indexer(self, name: str) -> Optional[IndexerConfig]:
        """Get a specific indexer configuration."""
        with self._lock:
            return self._indexers.get(name)
    
    def get_all_indexers(self) -> Dict[str, IndexerConfig]:
        """Get all indexer configurations."""
        with self._lock:
            return self._indexers.copy()
    
    def get_enabled_indexers(self) -> List[IndexerConfig]:
        """Get all enabled indexer configurations sorted by priority."""
        with self._lock:
            enabled = [config for config in self._indexers.values() if config.enabled]
            return sorted(enabled, key=lambda x: x.priority)
    
    def list_providers_api_response(self) -> Dict[str, any]:
        """Generate LazyLibrarian-style API response for listProviders."""
        with self._lock:
            # Separate indexers by type for proper LazyLibrarian format
            newznabs = []
            torznabs = []
            
            for config in self._indexers.values():
                # Match LazyLibrarian's exact field structure
                provider_data = {
                    "NAME": config.name,
                    "DISPNAME": config.alternative_name or "",
                    "ENABLED": "1" if config.enabled else "",
                    "HOST": config.host,
                    "API": config.api_key or "",
                    "GENERALSEARCH": "",
                    "BOOKSEARCH": "",
                    "MAGSEARCH": "",
                    "AUDIOSEARCH": "",
                    "COMICSEARCH": "",
                    "BOOKCAT": ','.join(config.categories) if config.categories else "7000,7020",
                    "MAGCAT": "",
                    "AUDIOCAT": "",
                    "COMICCAT": "",
                    "EXTENDED": "1",
                    "UPDATED": "",
                    "MANUAL": "",
                    "APILIMIT": "0",
                    "APICOUNT": "0",
                    "RATELIMIT": "0",
                    "DLPRIORITY": str(config.priority) if config.priority is not None else "0",
                    "DLTYPES": "",
                    "LASTUSED": "0"
                }
                
                if config.provider_type.lower() == 'torznab':
                    torznabs.append(provider_data)
                else:  # Default to newznab
                    newznabs.append(provider_data)
            
            # Use lowercase keys without Data wrapper to match LazyLibrarian
            return {
                "newznab": newznabs,
                "torznab": torznabs
            }

# Global instances
book_queue = BookQueue()
api_key_manager = APIKeyManager()
indexer_manager = IndexerManager()

@dataclass
class SearchFilters:
    isbn: Optional[List[str]] = None
    author: Optional[List[str]] = None
    title: Optional[List[str]] = None
    lang: Optional[List[str]] = None
    sort: Optional[str] = None
    content: Optional[List[str]] = None
    format: Optional[List[str]] = None