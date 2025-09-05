"""Multi-indexer book search manager using Prowlarr-synced indexers."""

import time
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote, urljoin
from typing import List, Optional, Dict, Union, Callable
from threading import Event
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import downloader
from logger import setup_logger
from config import SUPPORTED_FORMATS, BOOK_LANGUAGE
from models import BookInfo, SearchFilters, indexer_manager, IndexerConfig

logger = setup_logger(__name__)

# Cache for search results to support book detail retrieval
_last_search_results: Optional[List['SearchResult']] = None

@dataclass
class SearchResult:
    """Represents a search result from a single indexer."""
    book: BookInfo
    indexer_name: str
    indexer_priority: int

def search_books(query: str, filters: SearchFilters) -> List[BookInfo]:
    """Search for books across all enabled Prowlarr indexers.

    Args:
        query: Search term (ISBN, title, author, etc.)
        filters: Search filters object

    Returns:
        List[BookInfo]: List of matching books aggregated from all indexers

    Raises:
        Exception: If no books found or all searches fail
    """
    enabled_indexers = indexer_manager.get_enabled_indexers()
    
    if not enabled_indexers:
        logger.warning("No enabled indexers found. Please configure indexers through Prowlarr.")
        raise Exception("No indexers configured. Please set up indexers in Prowlarr.")
    
    logger.info(f"Searching across {len(enabled_indexers)} indexers: {[i.name for i in enabled_indexers]}")
    
    all_results = []
    
    # Search each indexer in parallel
    with ThreadPoolExecutor(max_workers=min(len(enabled_indexers), 10)) as executor:
        future_to_indexer = {
            executor.submit(_search_single_indexer, indexer, query, filters): indexer
            for indexer in enabled_indexers
        }
        
        for future in as_completed(future_to_indexer):
            indexer = future_to_indexer[future]
            try:
                results = future.result()
                logger.info(f"Indexer {indexer.name} returned {len(results)} results")
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Search failed for indexer {indexer.name}: {e}")
                # Continue with other indexers
    
    if not all_results:
        raise Exception("No books found from any indexer. Please try another query.")
    
    # Sort results by indexer priority, then by format preference
    sorted_results = _rank_and_deduplicate_results(all_results)
    
    # Cache the search results for detail retrieval
    global _last_search_results
    _last_search_results = all_results
    
    logger.info(f"Returning {len(sorted_results)} deduplicated results")
    return sorted_results

def _search_single_indexer(indexer: IndexerConfig, query: str, filters: SearchFilters) -> List[SearchResult]:
    """Search a single indexer using Newznab/Torznab protocol."""
    try:
        # Build search URL
        search_url = _build_search_url(indexer, query, filters)
        logger.debug(f"Searching {indexer.name}: {search_url}")
        
        # Get search results
        xml_content = downloader.html_get_page(search_url)
        if not xml_content:
            logger.warning(f"No response from indexer {indexer.name}")
            return []
        
        # Parse XML results
        books = _parse_newznab_xml(xml_content, indexer.name)
        
        # Convert to SearchResult with indexer info
        return [
            SearchResult(book=book, indexer_name=indexer.name, indexer_priority=indexer.priority)
            for book in books
        ]
        
    except Exception as e:
        logger.error_trace(f"Error searching indexer {indexer.name}: {e}")
        return []

def _build_search_url(indexer: IndexerConfig, query: str, filters: SearchFilters) -> str:
    """Build Newznab/Torznab search URL for an indexer."""
    base_url = indexer.host.rstrip('/')
    
    # Build search parameters
    params = {
        't': 'search',  # Search type
        'q': query,     # Query string
        'apikey': indexer.api_key,
        'o': 'xml',     # Output format
        'extended': '1' # Extended attributes
    }
    
    # Add book categories if configured
    if indexer.categories:
        # Filter for book categories (3000=ebooks, 7000=audiobooks)
        book_categories = [cat for cat in indexer.categories if cat.startswith(('3', '7'))]
        if book_categories:
            params['cat'] = ','.join(book_categories)
    else:
        # Default to book categories
        params['cat'] = '3000,7000'
    
    # Handle ISBN search
    if filters.isbn:
        isbn_query = ' OR '.join([f'"{isbn}"' for isbn in filters.isbn])
        params['q'] = f"({isbn_query}) {query}".strip()
    
    # Add other filters
    if filters.author:
        author_terms = ' '.join(filters.author)
        params['q'] = f'{params["q"]} {author_terms}'.strip()
    
    # Build final URL
    param_string = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
    # Check if base_url already ends with /api (from Prowlarr)
    if base_url.endswith('/api'):
        search_url = f"{base_url}?{param_string}"
    else:
        search_url = f"{base_url}/api?{param_string}"
    
    return search_url

def _parse_newznab_xml(xml_content: str, indexer_name: str) -> List[BookInfo]:
    """Parse Newznab/Torznab XML response into BookInfo objects."""
    try:
        # Log first 500 chars of response for debugging
        logger.debug(f"XML response from {indexer_name} (first 500 chars): {xml_content[:500]}")
        
        root = ET.fromstring(xml_content)
        books = []
        
        # Find all items in the RSS/channel structure
        items = root.findall('.//item')
        
        # Debug: Log first item's full XML structure
        if items and logger.level <= 10:  # Only in DEBUG mode
            first_item_str = ET.tostring(items[0], encoding='unicode')[:1000]
            logger.debug(f"First item XML from {indexer_name}: {first_item_str}")
        
        for item in items:
            try:
                book = _parse_newznab_item(item, indexer_name)
                if book and _is_book_format_supported(book.format):
                    books.append(book)
            except Exception as e:
                logger.debug(f"Failed to parse item from {indexer_name}: {e}")
                continue
        
        return books
        
    except ET.ParseError as e:
        logger.error(f"XML parsing error for {indexer_name}: {e}")
        return []
    except Exception as e:
        logger.error_trace(f"Error parsing results from {indexer_name}: {e}")
        return []

def _parse_newznab_item(item: ET.Element, indexer_name: str) -> Optional[BookInfo]:
    """Parse a single Newznab item into a BookInfo object."""
    # Extract basic fields
    title = _get_element_text(item, 'title', '')
    description = _get_element_text(item, 'description', '')
    guid = _get_element_text(item, 'guid', '')
    link = _get_element_text(item, 'link', '')
    
    if not title:
        return None
    
    # Generate book ID from GUID or title
    book_id = guid or f"{indexer_name}_{hash(title)}"
    if book_id.startswith('http'):
        # Extract meaningful ID from URL
        book_id = book_id.split('/')[-1] or book_id
    
    # Extract extended attributes
    attrs = _extract_newznab_attributes(item)
    
    # Debug: Log what attributes we found
    if attrs:
        logger.debug(f"Attributes found for {title}: {attrs}")
    else:
        logger.debug(f"No attributes found for {title}")
    
    # Parse title and author from title field (common format: "Author - Title")
    parsed_title, parsed_author = _parse_title_author(title)
    
    # Extract size from attributes or description
    size_bytes = attrs.get('size', '0')
    size = _format_file_size(int(size_bytes)) if size_bytes.isdigit() else attrs.get('size', 'Unknown')
    
    # Extract format from title or attributes
    book_format = _extract_format_from_title(title)
    if not book_format:
        book_format = attrs.get('format', '').lower()
    
    # Build download URLs
    download_urls = []
    if link:
        download_urls.append(link)
    
    # Look for enclosure URLs
    enclosures = item.findall('enclosure')
    for enc in enclosures:
        url = enc.get('url')
        if url and url not in download_urls:
            download_urls.append(url)
    
    return BookInfo(
        id=book_id,
        title=parsed_title or title,
        author=parsed_author or attrs.get('author', ''),
        publisher=attrs.get('publisher', ''),
        year=attrs.get('year', ''),
        language=attrs.get('language', ''),
        format=book_format,
        size=size,
        download_urls=download_urls,
        indexer_name=indexer_name,
        info={'source': [indexer_name], 'category': [attrs.get('category', '')]}
    )

def _extract_newznab_attributes(item: ET.Element) -> Dict[str, str]:
    """Extract Newznab extended attributes from an item."""
    attrs = {}
    
    # Look for newznab:attr elements
    for attr in item.findall('.//{http://www.newznab.com/DTD/2010/feeds/attributes/}attr'):
        name = attr.get('name', '')
        value = attr.get('value', '')
        if name and value:
            attrs[name.lower()] = value
    
    # Also check for torznab attributes
    for attr in item.findall('.//{http://torznab.com/schemas/2015/feed}attr'):
        name = attr.get('name', '')
        value = attr.get('value', '')
        if name and value:
            attrs[name.lower()] = value
    
    return attrs

def _get_element_text(parent: ET.Element, tag: str, default: str = '') -> str:
    """Safely extract text from an XML element."""
    element = parent.find(tag)
    return element.text.strip() if element is not None and element.text else default

def _parse_title_author(title: str) -> tuple[str, str]:
    """Try to extract title and author from combined title string."""
    # Common patterns: "Author - Title", "Title by Author", etc.
    patterns = [
        r'^(.+?)\s*-\s*(.+)$',  # Author - Title
        r'^(.+?)\s+by\s+(.+)$',  # Title by Author
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            part1, part2 = match.groups()
            # Heuristic: longer part is usually the title
            if len(part2) > len(part1):
                return part2.strip(), part1.strip()  # Title, Author
            else:
                return part1.strip(), part2.strip()  # Title, Author
    
    return title, ''  # Return original title, no author

def _extract_format_from_title(title: str) -> str:
    """Extract file format from title string."""
    # Look for format indicators in brackets or at the end
    format_patterns = [
        r'\[(\w+)\]',  # [EPUB], [PDF], etc.
        r'\.(\w+)$',   # .epub, .pdf at end
        r'\((\w+)\)',  # (EPUB), (PDF), etc.
    ]
    
    for pattern in format_patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            fmt = match.group(1).lower()
            if fmt in SUPPORTED_FORMATS:
                return fmt
    
    return ''

def _format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/(1024**2):.1f} MB"
    else:
        return f"{size_bytes/(1024**3):.1f} GB"

def _is_book_format_supported(book_format: Optional[str]) -> bool:
    """Check if the book format is in the supported formats list."""
    if not book_format:
        return True  # Allow unknown formats through
    return book_format.lower() in SUPPORTED_FORMATS

def _rank_and_deduplicate_results(results: List[SearchResult]) -> List[BookInfo]:
    """Rank results by priority and remove duplicates."""
    if not results:
        return []
    
    # Sort by indexer priority (lower number = higher priority), then by format preference
    sorted_results = sorted(results, key=lambda r: (
        r.indexer_priority,
        SUPPORTED_FORMATS.index(r.book.format) if r.book.format in SUPPORTED_FORMATS else len(SUPPORTED_FORMATS),
        r.book.title
    ))
    
    # Simple deduplication by title + author combination
    seen = set()
    deduplicated = []
    
    for result in sorted_results:
        book = result.book
        # Create a key for deduplication
        key = (
            book.title.lower().strip(),
            (book.author or '').lower().strip(),
            book.format or ''
        )
        
        if key not in seen:
            seen.add(key)
            # Update book with indexer info
            book.indexer_name = result.indexer_name
            deduplicated.append(book)
    
    return deduplicated

def get_book_info(book_id: str) -> BookInfo:
    """Get detailed information for a specific book.
    
    For Prowlarr integration, we check our search results cache first,
    then fall back to creating minimal info if not found.

    Args:
        book_id: Book identifier

    Returns:
        BookInfo: Detailed book information
    """
    # Check if we have this book in our search results cache
    global _last_search_results
    if _last_search_results:
        for result in _last_search_results:
            if result.book.id == book_id:
                return result.book
    
    # If not found in cache, create minimal BookInfo
    # The ID might be a composite like "indexer_bookid" 
    logger.warning(f"Book {book_id} not found in search cache, creating minimal info")
    return BookInfo(
        id=book_id,
        title=f"Book {book_id}",
        description="Book details not available - please search again to get full information"
    )

def download_book(book_info: BookInfo, book_path: Path, 
                 progress_callback: Optional[Callable[[float], None]] = None, 
                 cancel_flag: Optional[Event] = None) -> bool:
    """Download a book from available indexer sources.

    Args:
        book_info: Book information with download URLs
        book_path: Path where to save the downloaded book
        progress_callback: Optional callback for download progress
        cancel_flag: Optional event to signal download cancellation

    Returns:
        bool: True if download successful
    """
    if not book_info.download_urls:
        logger.error(f"No download URLs available for {book_info.title}")
        return False
    
    for url in book_info.download_urls:
        try:
            logger.info(f"Downloading '{book_info.title}' from {book_info.indexer_name}: {url}")
            
            data = downloader.download_url(url, book_info.size or "", progress_callback, cancel_flag)
            if not data:
                raise Exception("No data received")
            
            logger.info(f"Download finished. Writing to {book_path}")
            with open(book_path, "wb") as f:
                f.write(data.getbuffer())
            
            logger.info(f"Successfully downloaded '{book_info.title}'")
            return True
            
        except Exception as e:
            logger.error_trace(f"Failed to download from {url}: {e}")
            continue
    
    logger.error(f"All download attempts failed for '{book_info.title}'")
    return False