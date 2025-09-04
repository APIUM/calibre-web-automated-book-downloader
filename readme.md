# 📚 Calibre-Web-Automated-Book-Downloader

![Calibre-Web Automated Book Downloader](static/media/logo.png 'Calibre-Web Automated Book Downloader')

An intuitive web interface for searching and requesting book downloads from multiple sources via Prowlarr integration. Designed to work seamlessly with [Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated), this project streamlines the process of downloading books and preparing them for integration into your Calibre library.

## ✨ Features

- 🌐 User-friendly web interface for book search and download
- 🔗 **Prowlarr Integration**: Search across multiple indexers simultaneously
- 🔄 Automated download to your specified ingest folder  
- 🔌 Seamless integration with Calibre-Web-Automated
- 📖 Support for multiple book formats (epub, mobi, azw3, fb2, djvu, cbz, cbr)
- 🏷️ **LazyLibrarian Compatible**: Works as a drop-in replacement in Prowlarr
- ⚡ Concurrent download management with retry logic
- 🐳 Docker-based deployment for quick setup

## 🖼️ Screenshots

![Main search interface Screenshot](README_images/search.png 'Main search interface')

![Details modal Screenshot placeholder](README_images/details.png 'Details modal')

![Download queue Screenshot placeholder](README_images/downloading.png 'Download queue')

## 🚀 Quick Start

### Prerequisites

- Docker
- Docker Compose
- A running instance of [Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated) (recommended)

### Installation Steps

1. Get the docker-compose.yml:

   ```bash
   curl -O https://raw.githubusercontent.com/calibrain/calibre-web-automated-book-downloader/refs/heads/main/docker-compose.yml
   ```

2. Start the service:

   ```bash
   docker compose up -d
   ```

3. Access the web interface at `http://localhost:8084`

## 🔗 Prowlarr Integration

This application integrates seamlessly with [Prowlarr](https://prowlarr.com/) to provide multi-indexer book searching. Prowlarr manages all indexer configurations centrally, eliminating the need for manual setup.

### Setting up Prowlarr Integration

1. **In Prowlarr**: Go to Settings → Apps → Add Application
2. **Select**: LazyLibrarian (this app is fully compatible)
3. **Configure**:
   - **Name**: `Calibre-Web-Book-Downloader` 
   - **Prowlarr Server**: `http://prowlarr:9696` (adjust to your setup)
   - **Application Server**: `http://calibre-web-automated-book-downloader:8084`
   - **API Key**: Use the API key displayed in the application logs during startup
   - **Sync Categories**: Books (3000, 7000, 7020, etc.)
   - **Sync Level**: Full Sync (recommended)

4. **Test**: Click "Test" - should show green checkmark
5. **Save**: Prowlarr will automatically sync all your indexers!

### How It Works

- **Indexer Sync**: Prowlarr automatically configures all enabled book indexers in this app
- **Multi-Source Search**: Searches run across all indexers simultaneously for better results  
- **Priority-Based**: Results ranked by indexer priority and format preference
- **Automatic Updates**: When you add/remove indexers in Prowlarr, changes sync automatically

## 🔐 API Key Setup

### Automatic API Key Generation

The application automatically generates a UUID-based API key on first startup:

- **API Key Location**: Stored in `data/api_key.txt` within the container
- **Key Display**: API key is shown in the application logs during startup
- **Prowlarr Configuration**: Use this API key when setting up the Prowlarr integration
- **Security**: Each installation generates a unique API key automatically

### Finding Your API Key

1. **Check Application Logs**: The API key is displayed when the application starts
   ```bash
   docker logs calibre-web-automated-book-downloader
   ```
   Look for the line: `API Key for Prowlarr integration: <your-uuid-key>`

2. **Direct File Access**: API key is stored in the container's data directory
   ```bash
   docker exec calibre-web-automated-book-downloader cat data/api_key.txt
   ```

### Additional Authentication (Optional)

You can also enable Calibre-Web user authentication for the web interface:

To enable additional web interface authentication, set the `CWA_DB_PATH` environment variable to point to your Calibre-Web's `app.db` file:

```yaml
services:
  calibre-web-automated-book-downloader:
    environment:
      CWA_DB_PATH: /auth/app.db  # Enable web interface authentication
    volumes:
      - /path/to/calibre-web/app.db:/auth/app.db:ro  # Mount Calibre-Web DB
```

**Note**: The API key is always required for Prowlarr integration regardless of web interface authentication settings.

## ⚙️ Configuration

### Environment Variables

#### Application Settings

| Variable          | Description             | Default Value      |
| ----------------- | ----------------------- | ------------------ |
| `FLASK_PORT`      | Web interface port      | `8084`             |
| `FLASK_HOST`      | Web interface binding   | `0.0.0.0`          |
| `DEBUG`           | Debug mode toggle       | `false`            |
| `INGEST_DIR`      | Book download directory | `/cwa-book-ingest` |
| `TZ`              | Container timezone      | `UTC`              |
| `UID`             | Runtime user ID         | `1000`             |
| `GID`             | Runtime group ID        | `100`              |
| `CWA_DB_PATH`     | Calibre-Web's database  | None               |
| `ENABLE_LOGGING`  | Enable log file         | `true`             |
| `LOG_LEVEL`       | Log level to use        | `info`             |

If you wish to enable authentication, you must set `CWA_DB_PATH` to point to Calibre-Web's `app.db`, in order to match the username and password.

If logging is enabled, log folder default location is `/var/log/cwa-book-downloader`
Available log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Higher levels show fewer messages.

#### Download Settings

| Variable               | Description                                               | Default Value                     |
| ---------------------- | --------------------------------------------------------- | --------------------------------- |
| `MAX_RETRY`            | Maximum retry attempts for failed downloads               | `3`                               |
| `DEFAULT_SLEEP`        | Retry delay (seconds)                                     | `5`                               |
| `MAIN_LOOP_SLEEP_TIME` | Processing loop delay (seconds)                           | `5`                               |
| `SUPPORTED_FORMATS`    | Supported book formats                                    | `epub,mobi,azw3,fb2,djvu,cbz,cbr` |
| `BOOK_LANGUAGE`        | Preferred language for books                              | `en`                              |
| `USE_BOOK_TITLE`       | Use book title as filename instead of ID                  | `false`                           |
| `MAX_CONCURRENT_DOWNLOADS` | Maximum simultaneous downloads                        | `3`                               |
| `DOWNLOAD_PROGRESS_UPDATE_INTERVAL` | Progress update frequency (seconds)           | `5`                               |

If you change `BOOK_LANGUAGE`, you can add multiple comma separated languages, such as `en,fr,ru` etc.  

#### Network Settings

| Variable               | Description                     | Default Value           |
| ---------------------- | ------------------------------- | ----------------------- |
| `HTTP_PROXY`           | HTTP proxy URL                  | ``                      |
| `HTTPS_PROXY`          | HTTPS proxy URL                 | ``                      |
| `CUSTOM_DNS`           | Custom DNS IP                   | ``                      |
| `USE_DOH`              | Use DNS over HTTPS              | `false`                 |

For proxy configuration, you can specify URLs in the following format:
```bash
# Basic proxy
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080

# Proxy with authentication
HTTP_PROXY=http://username:password@proxy.example.com:8080
HTTPS_PROXY=http://username:password@proxy.example.com:8080
```


The `CUSTOM_DNS` setting supports two formats:

1. **Custom DNS Servers**: A comma-separated list of DNS server IP addresses
   - Example: `127.0.0.53,127.0.1.53` (useful for PiHole)
   - Supports both IPv4 and IPv6 addresses in the same string

2. **Preset DNS Providers**: Use one of these predefined options:
   - `google` - Google DNS
   - `quad9` - Quad9 DNS
   - `cloudflare` - Cloudflare DNS
   - `opendns` - OpenDNS

For users experiencing ISP-level website blocks (such as Virgin Media in the UK), using alternative DNS providers like Cloudflare may help bypass these restrictions

If a `CUSTOM_DNS` is specified from the preset providers, you can also set a `USE_DOH=true` to force using DNS over HTTPS,
which might also help in certain network situations. Note that only `google`, `quad9`, `cloudflare` and `opendns` are 
supported for now, and any other value in `CUSTOM_DNS` will make the `USE_DOH` flag ignored.

Try something like this :
```bash
CUSTOM_DNS=cloudflare
USE_DOH=true
```

#### Custom configuration

| Variable               | Description                                                 | Default Value           |
| ---------------------- | ----------------------------------------------------------- | ----------------------- |
| `CUSTOM_SCRIPT`        | Path to an executable script that tuns after each download  | ``                      |

If `CUSTOM_SCRIPT` is set, it will be executed after each successful download but before the file is moved to the ingest directory. This allows for custom processing like format conversion or validation.

The script is called with the full path of the downloaded file as its argument. Important notes:
- The script must preserve the original filename for proper processing
- The file can be modified or even deleted if needed
- The file will be moved to `/cwa-book-ingest` after the script execution (if not deleted)

You can specify these configuration in this format :
```
environment:
  - CUSTOM_SCRIPT=/scripts/process-book.sh

volumes:
  - local/scripts/custom_script.sh:/scripts/process-book.sh
```

### Volume Configuration

```yaml
volumes:
  - /your/local/path:/cwa-book-ingest
  - /cwa/config/path/app.db:/auth/app.db:ro
```
**Note** - If your library volume is on a cifs share, you will get a "database locked" error until you add **nobrl** to your mount line in your fstab file. e.g. //192.168.1.1/Books /media/books cifs credentials=.smbcredentials,uid=1000,gid=1000,iocharset=utf8,**nobrl** - See https://github.com/crocodilestick/Calibre-Web-Automated/issues/64#issuecomment-2712769777

Mount should align with your Calibre-Web-Automated ingest folder.

## 🏗️ Architecture

The application consists of a single service:

1. **calibre-web-automated-bookdownloader**: Main application providing web interface and download functionality

## 🏥 Health Monitoring

Built-in health checks monitor:

- Web interface availability  
- Download service status
- Prowlarr integration connectivity

Checks run every 30 seconds with a 30-second timeout and 3 retries.
You can enable by adding this to your compose :
```
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD pyrequests http://localhost:8084/request/api/status || exit 1
```

## 📝 Logging

Logs are available in:

- Container: `/var/logs/cwa-book-downloader.log`
- Docker logs: Access via `docker logs`

## 🤝 Contributing

Contributions are welcome! Feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Important Disclaimers

### Copyright Notice

While this tool can access various sources including those that might contain copyrighted material, it is designed for legitimate use only. Users are responsible for:

- Ensuring they have the right to download requested materials
- Respecting copyright laws and intellectual property rights
- Using the tool in compliance with their local regulations

### Duplicate Downloads Warning

Please note that the current version:

- Does not check for existing files in the download directory
- Does not verify if books already exist in your Calibre database
- Exercise caution when requesting multiple books to avoid duplicates

## 💬 Support

For issues or questions, please file an issue on the GitHub repository.

