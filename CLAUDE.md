# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based web application that integrates with Prowlarr to search and download books from multiple indexers. It's designed to work with Calibre-Web-Automated for seamless library management.

## Key Architecture Components

### Core Services
- **app.py**: Flask web application with dual route support (/request prefix compatibility)
- **prowlarr_manager.py**: Handles multi-indexer book searches via Prowlarr integration
- **backend.py**: Background download processing and queue management
- **book_manager.py**: Book download orchestration and file management
- **models.py**: Data models for books, indexers, search filters, and API key management
- **network.py**: Network operations with proxy, DNS, and retry logic support

### Authentication & Security
- API key authentication for Prowlarr integration (stored in data/api_key.txt)
- Optional Calibre-Web user authentication via CWA_DB_PATH
- Automatic UUID-based API key generation on first startup

### Download Flow
1. Search requests go through Prowlarr to multiple indexers
2. Results are aggregated and prioritized by indexer priority and format preference
3. Downloads are queued and processed concurrently (MAX_CONCURRENT_DOWNLOADS)
4. Downloaded files are saved to INGEST_DIR for Calibre-Web-Automated processing

## Development Commands

### Running the Application
```bash
# Development mode
python app.py

# Production mode with gunicorn
gunicorn -w 4 -b 0.0.0.0:8084 app:app
```

### Running Tests
```bash
# Run all tests
python -m pytest testing/

# Run specific test file
python -m pytest testing/test_prowlarr_integration.py

# Run with verbose output
python -m pytest -v testing/
```

### Docker Development
```bash
# Build and run with docker-compose
docker compose up -d

# View logs
docker logs calibre-web-automated-book-downloader

# Generate debug archive
docker exec calibre-web-automated-book-downloader /app/genDebug.sh
```

## Environment Variables

Critical environment variables that affect behavior:
- `INGEST_DIR`: Where downloaded books are saved (default: /cwa-book-ingest)
- `CWA_DB_PATH`: Path to Calibre-Web database for authentication
- `FLASK_PORT`: Web interface port (default: 8084)
- `DEBUG`: Enable debug mode
- `USING_EXTERNAL_BYPASSER`: Use external CloudFlare bypasser service
- `MAX_CONCURRENT_DOWNLOADS`: Number of simultaneous downloads (default: 3)

## API Endpoints

### Main Routes (available with and without /request prefix)
- `GET /`: Web interface
- `GET /api/search`: Search for books
- `POST /api/download`: Queue a book download
- `GET /api/status`: Health check and queue status
- `GET /api/version`: Version information
- `POST /api/lazyLibrarian`: LazyLibrarian-compatible endpoint for Prowlarr

## Testing Approach

Tests are located in the `testing/` directory:
- Unit tests for models and API functionality
- Integration tests for Prowlarr communication
- E2E tests for full workflow validation

## Important Notes

- The application supports dual routes - all endpoints work with both `/` and `/request/` prefixes
- Prowlarr integration requires proper API key configuration in both systems
- Download queue is processed asynchronously in the background
- Cloudflare bypass functionality available through internal or external methods
- File formats are filtered based on SUPPORTED_FORMATS configuration