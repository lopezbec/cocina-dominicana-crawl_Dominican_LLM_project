# Multi-Site Web Scraper 🌐

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![API](https://img.shields.io/badge/Firecrawl-API-FF6B6B?style=for-the-badge&logo=fire&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Production-success?style=for-the-badge)

**Production-Ready Multi-Site Web Scraper**

*Flexible, environment-driven scraper supporting multiple domains with canonical logging, clean architecture, and robust error handling*

</div>

## Platform Requirements

> **This application runs Firecrawl locally using Docker Compose - no API key required**

### System Architecture

```mermaid
graph TB
    A[core.cli] --> B[Firecrawl API:3002]
    A --> C[Config System]
    C --> D[Global Config]
    C --> E[Site Configs]
    B --> F[Redis:6379]
    B --> G[PostgreSQL:5432]
    B --> H[Content Extraction]
    A --> I[File System]
    I --> J[scraped_content/]
    J --> K[Markdown Files with Domain]
    J --> L[metadata.jsonl]
    
    style A fill:#3776AB,stroke:#fff,stroke-width:2px,color:#fff
    style B fill:#FF6B6B,stroke:#fff,stroke-width:2px,color:#fff
    style J fill:#28a745,stroke:#fff,stroke-width:2px,color:#fff
```

## Dependencies

### Core Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Service orchestration |
| Python | 3.9+ | Runtime environment |
| uv | Latest | Fast Python package manager |
| firecrawl-py | Latest | API client library |
| python-dotenv | Latest | Environment variable management |
| pyyaml | Latest | Configuration file parsing |

### Local Firecrawl Stack
The application runs Firecrawl locally via Docker:

| Service | Port | Purpose |
|---------|------|---------|
| Firecrawl API | 3002 | Web scraping engine |
| Redis | 6379 | Job queue management |
| PostgreSQL | 5432 | Job state persistence |

### Compatibility Matrix

```mermaid
gantt
    title Platform Support
    dateFormat X
    axisFormat %s
    
    section Operating Systems
    macOS     : 0, 1
    Linux     : 0, 1  
    Windows   : 0, 1
    
    section Python Versions
    Python 3.8  : 0, 1
    Python 3.9  : 0, 1
    Python 3.10 : 0, 1
    Python 3.11 : 0, 1
    Python 3.12 : 0, 1
```

## Installation & Setup

### Prerequisites

- **Docker** and **Docker Compose** installed ([Get Docker](https://docs.docker.com/get-docker/))
- **Python 3.9+**
- **uv** package manager ([Get uv](https://docs.astral.sh/uv/))
- **4GB RAM minimum** (8GB recommended)

### Quick Start

```bash
git clone https://github.com/cristiandlahoz/cocina-dominicana-crawl.git
cd cocina-dominicana-crawl

make setup

make test

CRAWL_DOMAIN=cocinadominicana.com make scrape

make firecrawl-stop
```

### Detailed Setup

#### Step 1: Clone Repository

```bash
git clone https://github.com/cristiandlahoz/cocina-dominicana-crawl.git
cd cocina-dominicana-crawl
```

#### Step 2: Install uv Package Manager

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use Homebrew
brew install uv

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Step 3: Run Complete Setup

```bash
make setup
```

This command will:
- Sync Python dependencies using uv
- Clone and initialize Firecrawl
- Build Docker images (5-10 minutes first time)
- Start all services (API, Redis, PostgreSQL, Playwright)

#### Step 4: Configure Environment

Create `.env` from template and set required CRAWL_DOMAIN:

```bash
cp .env.example .env
# Add to .env:
CRAWL_DOMAIN=cocinadominicana.com
```

Or set inline with commands:

```bash
CRAWL_DOMAIN=cocinadominicana.com make scrape
```

#### Step 5: Verify Services

```bash
make test
```

Expected: JSON response with scraped content from example.com

#### Step 6: Run Scraper

```bash
CRAWL_DOMAIN=cocinadominicana.com make scrape
```

#### Step 7: Stop Services When Done

```bash
make firecrawl-stop
```

### Makefile Commands

View all available commands:

```bash
make help
```

Common commands:

| Command | Description |
|---------|-------------|
| `make setup` | Complete first-time setup |
| `make setup-site DOMAIN=example.com` | Setup new site configuration |
| `make list-sites` | List configured sites |
| `make firecrawl-start` | Start Firecrawl services |
| `make firecrawl-stop` | Stop Firecrawl services |
| `make firecrawl-restart` | Restart all services |
| `make firecrawl-status` | Show service status |
| `make firecrawl-logs` | Follow API logs |
| `make scrape` | Run all configured sections (requires CRAWL_DOMAIN) |
| `make scrape-url URL=<url>` | Scrape a single URL (requires CRAWL_DOMAIN) |
| `make scrape-category URL=<url>` | Crawl category and scrape articles (requires CRAWL_DOMAIN) |
| `make scrape-list FILE=<file>` | Scrape URLs from file (requires CRAWL_DOMAIN) |
| `make scrape-discover URL=<url>` | Discover URLs without scraping (requires CRAWL_DOMAIN) |
| `make test` | Test Firecrawl endpoint |
| `make clean` | Remove scraped content |
| `make clean-all` | Remove everything including Firecrawl |

**Note**: All scraping commands require the `CRAWL_DOMAIN` environment variable:

```bash
CRAWL_DOMAIN=cocinadominicana.com make scrape
CRAWL_DOMAIN=example.com make scrape-url URL=https://example.com/article
```

## Features

Production-ready multi-site scraper with enterprise-grade reliability:

### Core Capabilities

- **Multi-Site Support**: Scrape multiple domains with site-specific configurations
- **Environment-Driven**: CRAWL_DOMAIN variable controls which site to scrape
- **Two-Level Configuration**: Global defaults with site-specific overrides
- **Auto-Generated Patterns**: URL extraction patterns automatically generated from base_url
- **Local Firecrawl**: No API keys, no rate limits, full control
- **Flexible Scraping**: Single URL, category crawl, batch processing, or section-based
- **Smart URL Discovery**: Automatic link extraction with configurable filtering
- **Canonical Logging**: Structured logging following Stripe's canonical log pattern
- **Clean Architecture**: Functions follow Single Responsibility Principle
- **Fast Scraping**: 6x faster than cloud API (0.5s vs 3s per article)
- **Resume Capability**: Automatically skips already scraped articles
- **Performance Monitoring**: Built-in timing for all operations
- **Robust Error Handling**: Comprehensive exception handling with detailed logging
- **File Organization**: Domain-aware filename generation with global doc IDs
- **Docker-based**: Easy setup with docker-compose, no complex configuration
- **CLI Interface**: User-friendly command-line interface with multiple commands
- **YAML Configuration**: Easy site setup and customization

### Adding New Sites

Create a new site configuration easily:

```bash
make setup-site DOMAIN=example.com
```

Or manually:

1. Create `sites/example_com/config.yml`
2. Create `sites/example_com/processing_patterns.yml`
3. Configure base_url, filters, and crawler settings
4. Run: `CRAWL_DOMAIN=example.com make scrape`

See `sites/README.md` for detailed instructions.

### Data Model

```mermaid
erDiagram
    ARTICLE {
        string title
        string description
        string url
        string url_slug
        datetime scraped_at
        int word_count
        int char_count
    }
    
    SECTION {
        string name
        string url
        string directory
        int articles_count
    }
    
    SESSION {
        datetime start_time
        datetime end_time
        float duration_seconds
        int total_articles
    }
    
    SECTION ||--o{ ARTICLE : contains
    SESSION ||--o{ SECTION : processes
```

## Usage

### Environment Variable (REQUIRED)

All scraping commands require the `CRAWL_DOMAIN` environment variable:

```bash
# Set in .env file
echo "CRAWL_DOMAIN=cocinadominicana.com" >> .env

# Or set inline with commands
CRAWL_DOMAIN=cocinadominicana.com make scrape
```

The scraper will validate the domain exists in `sites/` and show helpful errors if not set.

### Command-Line Interface

The scraper provides a flexible CLI for different scraping scenarios:

#### Scrape All Configured Sections

```bash
CRAWL_DOMAIN=cocinadominicana.com make scrape
# Or directly:
CRAWL_DOMAIN=cocinadominicana.com uv run python -m core.cli scrape-all
```

#### Scrape Single URL

```bash
CRAWL_DOMAIN=cocinadominicana.com make scrape-url URL="https://www.cocinadominicana.com/batata-asada"
# Or directly:
CRAWL_DOMAIN=cocinadominicana.com uv run python -m core.cli scrape "https://www.cocinadominicana.com/batata-asada"
```

#### Crawl Category Page

Automatically discover and scrape all articles from a category page:

```bash
CRAWL_DOMAIN=cocinadominicana.com make scrape-category URL="https://www.cocinadominicana.com/cocina" DEPTH=2
# Or directly:
CRAWL_DOMAIN=cocinadominicana.com uv run python -m core.cli crawl "https://www.cocinadominicana.com/cocina" --depth 2
```

#### Scrape Multiple URLs from File

Create a file with URLs (one per line):

```bash
echo "https://www.cocinadominicana.com/batata-asada" > urls.txt
echo "https://www.cocinadominicana.com/mangu" >> urls.txt

CRAWL_DOMAIN=cocinadominicana.com make scrape-list FILE=urls.txt
```

#### Discover URLs with Interactive Menu

Discover URLs and choose what to do with them through an interactive menu:

```bash
CRAWL_DOMAIN=cocinadominicana.com make scrape-discover URL="https://www.cocinadominicana.com/cocina"
```

#### Process to Plain Text

Convert scraped markdown to plain text:

```bash
CRAWL_DOMAIN=cocinadominicana.com uv run python -m core.cli process
```

### CLI Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `scrape-all` | Scrape all configured sections | `CRAWL_DOMAIN=example.com uv run python -m core.cli scrape-all` |
| `scrape <url>` | Scrape single URL | `CRAWL_DOMAIN=example.com uv run python -m core.cli scrape <url>` |
| `crawl <url>` | Crawl category and scrape articles | `CRAWL_DOMAIN=example.com uv run python -m core.cli crawl <url> --depth 2` |
| `scrape-list <file>` | Scrape URLs from file | `CRAWL_DOMAIN=example.com uv run python -m core.cli scrape-list urls.txt` |
| `discover <url>` | Discover URLs with interactive menu | `CRAWL_DOMAIN=example.com uv run python -m core.cli discover <url>` |
| `process` | Process to plain text | `CRAWL_DOMAIN=example.com uv run python -m core.cli process` |

### Configuration

The scraper uses a two-level configuration system:

#### Global Configuration (`config.yml`)

Default settings for all sites:

```yaml
filters:
  exclude_patterns:
    - "wp-content"
    - "wp-json"
    - "\\.(jpg|png|gif)$"

crawler:
  max_depth: 2
  delay_seconds: 0.5
  skip_existing: true
  max_retries: 3
```

#### Site-Specific Configuration (`sites/{domain}/config.yml`)

Override defaults for specific sites:

```yaml
base_url: "https://www.example.com"
output_dir: "scraped_content"

filters:
  include_patterns:
    - "example\\.com/.*"
  exclude_patterns:
    - "category/excluded"

crawler:
  max_depth: 3
  delay_seconds: 1.0
```

#### Processing Patterns (`sites/{domain}/processing_patterns.yml`)

Site-specific text processing rules:

```yaml
navigation_patterns:
  - "Skip to content"
  - "Main menu"

footer_markers:
  - "© Copyright"
  - "All rights reserved"
```

### Programmatic Usage

```python
from core.config_loader import load_config
from core.crawler import Crawler
from core.processor import ContentProcessor

config = load_config()
crawler = Crawler(config)

crawler.scrape_all_sections()

article_data = crawler.scrape_url("https://www.example.com/article")

result = crawler.crawl_category(
    category_url="https://www.example.com/category",
    category_name="category",
    max_depth=2
)
```

## Output Structure

```
scraped_content/
├── 0001_cocinadominicana_com_batata-asada.md
├── 0002_cocinadominicana_com_mangu.md
├── 0003_example_com_article-title.md
├── metadata.jsonl
└── scraping_summary.json
```

### Filename Format

Files are named with a global document ID and domain:

```
{doc_id}_{domain_slug}_{url_slug}.md
```

Examples:
- `0001_cocinadominicana_com_batata-asada.md`
- `0042_example_com_getting-started.md`

### File Formats

**Markdown Files (`.md`)**

```markdown
---
doc_id: 1020
domain: cocinadominicana.com
title: "Article Title"
description: "Article description"
url: https://www.cocinadominicana.com/article-url
scraped_at: 2025-12-11T14:15:30.123456
word_count: 450
char_count: 2847
---

# Article Content
Article markdown content here...
```

**Metadata JSONL (`metadata.jsonl`)**

Each line is a JSON object for one article:

```json
{"title": "Article Title", "description": "Article description", "url": "https://...", "url_slug": "article-url", "domain": "cocinadominicana.com", "scraped_at": "2025-12-11T14:15:30.123456", "word_count": 450, "char_count": 2847, "doc_id": "1020"}
```

## Performance Tuning

### Worker Configuration

Edit `firecrawl.env` to adjust scraping speed:

```bash
NUM_WORKERS_PER_QUEUE=8
```

| Workers | Speed | Resource Usage | Use Case |
|---------|-------|----------------|----------|
| 4 | Slow | Low | Limited resources |
| 8 | Normal | Medium | Default, balanced |
| 16 | Fast | High | Good hardware |
| 32 | Very Fast | Very High | Server-grade |

After changes:
```bash
docker-compose restart firecrawl-api
```

### Performance Comparison

| Metric | Cloud API | Local Setup |
|--------|-----------|-------------|
| Rate Limits | Yes (strict) | No |
| Cost | Paid/Limited free | Free |
| Speed per article | ~3 seconds | ~0.5 seconds |
| Setup time | Instant | 5 minutes |
| Control | Limited | Full |

## Logging and Monitoring

### Canonical Log Pattern

The scraper implements structured logging with canonical log lines for excellent observability:

**Session Tracking**

```
2025-12-11T14:15:30 [INFO] core.crawler: firecrawl_initialized api_url="http://localhost:3002" domain="cocinadominicana.com"
2025-12-11T14:15:30 [INFO] core.crawler: single_url_scrape_started url="https://..."
2025-12-11T14:15:31 [INFO] core.crawler: article_scrape_completed url="https://..." title="Recipe Title" word_count=450
```

**Performance Monitoring**

```
2025-12-11T14:15:31 [INFO] core.crawler: scrape_success url="https://..." attempt=1
2025-12-11T14:15:31 [INFO] core.crawler: article_save_completed file_name="1020_cocinadominicana_com_batata-asada.md"
```

**Docker Service Logs**

```bash
docker-compose logs -f firecrawl-api

docker-compose logs -f redis

docker-compose logs -f postgres
```

### Log Files

- **Console Output**: Real-time logging to terminal
- **File Logging**: Persistent logs saved to `scraping.log`
- **Structured Format**: Machine-readable logs for monitoring tools
- **Docker Logs**: Service logs via `docker-compose logs`

## Reliability

### Error Recovery

- 3 retry attempts for failed requests
- Graceful handling of network timeouts
- Comprehensive error logging with context
- Resume capability for interrupted sessions

### Performance Characteristics

| Metric | Value |
|--------|-------|
| Scraping Speed | ~0.5 seconds per article |
| Memory Usage | <50MB for typical sessions |
| Success Rate | >95% with retry logic |
| Resume Efficiency | 100% skip rate for existing files |

## Development

### Code Architecture

The codebase follows Clean Code principles with a modular structure:

```
core/
├── __init__.py          # Package exports
├── cli.py               # Command-line interface
├── config_loader.py     # Configuration management
├── crawler.py           # Web scraping logic
└── processor.py         # Post-processing

sites/
├── cocinadominicana_com/
│   ├── config.yml       # Site-specific config
│   └── processing_patterns.yml  # Text processing rules
└── README.md            # Site setup guide

templates/
├── site_config.yml      # Template for new sites
└── processing_patterns.yml

config.yml               # Global defaults
```

### Design Principles

- **Single Responsibility**: Each module has one clear purpose
- **Configuration-Driven**: Site behavior controlled via YAML
- **Environment-Driven**: Domain selection via CRAWL_DOMAIN
- **Separation of Concerns**: Clear boundaries between config, crawling, and processing
- **Type Safety**: Full type annotations throughout

### Testing

```bash
# Validate syntax
uv run python3 -m py_compile core/*.py

# Test environment validation
env -u CRAWL_DOMAIN uv run python -m core.cli scrape https://example.com
# Should show error message with available sites

# Test with valid domain
CRAWL_DOMAIN=cocinadominicana.com uv run python -m core.cli --help

# Test scraping single URL
CRAWL_DOMAIN=cocinadominicana.com uv run python -m core.cli scrape https://www.cocinadominicana.com/batata-asada
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow Clean Code principles (functions ≤20 lines)
4. Add canonical logging for new operations
5. Test your changes thoroughly
6. Commit with conventional commit format
7. Push and create a Pull Request

### Commit Format

```bash
git commit -m "feat: add new scraping section

- Implement new section discovery logic
- Add canonical logging for section operations  
- Include performance metrics tracking"
```

## Troubleshooting

### Common Issues

**Services Won't Start**

```bash
docker-compose logs -f

docker-compose down -v && docker-compose up -d
```

**API Not Responding**

```bash
curl http://localhost:3002/test

docker-compose restart firecrawl-api
```

**Port Already in Use**

Edit `docker-compose.yml` and change port mappings:
```yaml
ports:
  - "3003:3002"
```

**Import Errors**

```
ModuleNotFoundError: No module named 'yaml'
```

**Solution**: Sync dependencies with `uv sync` or `make setup`

**Missing CRAWL_DOMAIN**

```
ERROR: CRAWL_DOMAIN environment variable not set
```

**Solution**: Set the environment variable:
```bash
export CRAWL_DOMAIN=cocinadominicana.com
# Or add to .env file
echo "CRAWL_DOMAIN=cocinadominicana.com" >> .env
```

**Invalid Domain**

```
ERROR: Site configuration not found for domain 'example.com'
```

**Solution**: Check available sites with `make list-sites` or create new site with `make setup-site DOMAIN=example.com`

**For detailed troubleshooting, see `local-setup.md`**

### Debug Mode

Enable verbose logging:

```python
from utils import setup_canonical_logger

logger = setup_canonical_logger(__name__, level="DEBUG")
```

### Performance Analysis

Monitor performance with log analysis:

```bash
rg "duration_ms" scraping.log | tail -20

rg -c "scrape_success" scraping.log
rg -c "scrape_failed" scraping.log

docker stats
```

## License

This project is for educational and research purposes. Please respect the website's robots.txt and terms of service.

## Support

- **Issues**: [GitHub Issues](https://github.com/cristiandlahoz/cocina-dominicana-crawl/issues)
- **Documentation**: This README
- **Logs**: Check `scraping.log` for detailed operation logs

---

## Acknowledgment

This project has been partially supported by the Ministerio de Educación Superior, Ciencia y Tecnología (MESCyT) of the Dominican Republic through the FONDOCYT grant. The authors gratefully acknowledge this support.

Any opinions, findings, conclusions, or recommendations expressed in this material are those of the authors and do not necessarily reflect the views of MESCyT.

---

**Built for preserving Dominican culinary culture**
