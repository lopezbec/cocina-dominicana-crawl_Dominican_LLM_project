# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-10-30

### BREAKING CHANGES

- FIRECRAWL_API_KEY environment variable replaced with FIRECRAWL_API_URL
- Migrated from Firecrawl cloud API to local self-hosted instance
- Application now requires Docker and Docker Compose to run

### Added

- Local Firecrawl setup using Docker Compose
- Professional Makefile with 17 build automation targets
- Beautiful ASCII art banners for improved user experience
- Comprehensive local-setup.md guide with troubleshooting
- MIGRATION-SUMMARY.md documenting the complete migration process
- Makefile targets: setup, install, firecrawl-init, firecrawl-build, firecrawl-start, firecrawl-stop, firecrawl-restart, firecrawl-status, firecrawl-logs, firecrawl-clean, scrape, test, clean, clean-all, check-docker, check-python
- Docker volume exclusions in .gitignore (firecrawl-local/, postgres-data/, redis-data/)
- Performance tuning guide in documentation
- Docker setup instructions in .env.example

### Changed

- Scraper now connects to local Firecrawl at http://localhost:3002 instead of cloud API
- Reduced base delay from 20 seconds to 2 seconds
- Reduced inter-article delay from 3 seconds to 0.5 seconds (6x faster)
- Updated README.md with local Firecrawl architecture diagrams
- Updated system architecture to include Redis, PostgreSQL, and Playwright services
- Simplified .env.example for local setup configuration
- Updated all documentation to reflect local setup workflow

### Removed

- API key authentication requirement
- Rate limiting handler method (_handle_rate_limit_error)
- Complex retry logic with exponential backoff (50+ lines)
- Cloud API documentation and configuration
- Example scraped content files (README.md and JSON examples)
- Rate limiting flowcharts from documentation

### Performance Improvements

- Scraping speed: 0.5 seconds per article (previously 3 seconds, 6x faster)
- Rate limits: None (previously strict API limits)
- Cost: Free (previously paid/limited free tier)
- Code complexity: Reduced by 14% (removed 56 lines of rate limiting code)

### Documentation

- Added Makefile commands reference table
- Updated quick start guide to use make commands
- Added troubleshooting section for Docker services
- Replaced grep commands with ripgrep (rg) throughout documentation
- Added performance comparison tables
- Added Docker logs viewing instructions

### Configuration

New environment variables:
- FIRECRAWL_API_URL (default: http://localhost:3002)

Removed environment variables:
- FIRECRAWL_API_KEY

### Infrastructure

Services now running locally via Docker Compose:
- Firecrawl API (port 3002)
- PostgreSQL (port 5432)
- Redis (port 6379)
- Playwright service (port 3000)

### Migration Path

For users upgrading from 1.x:

1. Stop using cloud API key
2. Install Docker and Docker Compose
3. Run `make setup` for complete local setup
4. Update .env to use FIRECRAWL_API_URL instead of FIRECRAWL_API_KEY
5. Run `make test` to verify installation
6. Run `make scrape` to start scraping

See MIGRATION-SUMMARY.md for detailed migration instructions.

### Rollback Instructions

To revert to cloud API:

1. Restore scraper.py from git tag v1.x
2. Add FIRECRAWL_API_KEY to .env
3. Run `make clean-all` to remove local Firecrawl
4. Install cloud API version dependencies

---

## [1.0.0] - Previous Version

### Features

- Web scraping using Firecrawl cloud API
- Canonical logging system
- Clean architecture with <20 line functions
- Rate limiting with exponential backoff
- Resume capability for interrupted scrapes
- Structured JSON and Markdown output

### Infrastructure

- Python 3.8+ runtime
- Firecrawl cloud API integration
- API key authentication
- Rate limit handling (3 second delays)

---

## Version Comparison

| Feature | v1.0.0 (Cloud) | v2.0.0 (Local) |
|---------|----------------|----------------|
| Setup Time | Instant | 5-10 minutes (one-time) |
| Rate Limits | Yes (strict) | No |
| Cost | Paid/Limited free | Free |
| Speed per article | 3 seconds | 0.5 seconds |
| Dependencies | Python only | Docker + Python |
| Control | Limited | Full |
| API Key Required | Yes | No |
| Offline Capable | No | Yes |

---

For more details on specific changes, see the git commit history:
```bash
git log v1.0.0..v2.0.0
```
