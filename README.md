# Dominican Culture Scraper 🇩🇴

A production-ready web scraper that collects Dominican culinary culture articles from [Cocina Dominicana](https://www.cocinadominicana.com) using the Firecrawl API. Features canonical logging, clean architecture, and comprehensive error handling.

## 🚀 Features

- **Canonical Logging**: Structured logging following Stripe's canonical log pattern for excellent observability
- **Clean Architecture**: Functions follow Single Responsibility Principle with <20 line limit
- **Rate Limiting**: Intelligent retry logic with exponential backoff
- **Resume Capability**: Automatically skips already scraped articles
- **Performance Monitoring**: Built-in timing for all operations
- **Robust Error Handling**: Comprehensive exception handling with detailed logging
- **File Organization**: Automatic directory structure creation and safe filename generation

## 📋 Requirements

- Python 3.8+
- Firecrawl API key (free tier available)
- Dependencies listed in `requirements.txt`

## 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/cristiandlahoz/cocina-dominicana-crawl.git
   cd cocina-dominicana-crawl
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your Firecrawl API key
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Firecrawl API Key (required)
# Get your free API key from https://firecrawl.dev
FIRECRAWL_API_KEY=your_api_key_here
```

### Scraping Sections

The scraper targets 4 main cultural sections:

1. **Cultura y Orígenes** (`cultura_origenes/`)
2. **Tradiciones y Costumbres** (`tradiciones_costumbres/`)  
3. **Festividades y Celebraciones** (`festividades_celebraciones/`)
4. **Comparaciones** (`comparaciones/`)

## 🎯 Usage

### Basic Usage

```bash
python scraper.py
```

### Programmatic Usage

```python
from scraper import DominicanCultureScraperV2

# Initialize scraper
scraper = DominicanCultureScraperV2()

# Scrape all sections
scraper.scrape_all_sections()

# Scrape specific section
scraper.scrape_section("cultura_origenes")

# Scrape individual article
article_data = scraper.scrape_article("https://www.cocinadominicana.com/article-url")
```

## 📁 Output Structure

```
scraped_content/
├── cultura_origenes/
│   ├── article-title.md
│   ├── article-title.json
│   └── ...
├── tradiciones_costumbres/
├── festividades_celebraciones/
├── comparaciones/
└── scraping_summary.json
```

### File Formats

**Markdown Files (`.md`)**
```markdown
---
title: "Article Title"
description: "Article description"
url: https://www.cocinadominicana.com/article-url
scraped_at: 2024-10-14T14:15:30.123456
word_count: 450
char_count: 2847
---

# Article Content
Article markdown content here...
```

**JSON Metadata (`.json`)**
```json
{
  "title": "Article Title",
  "description": "Article description", 
  "url": "https://www.cocinadominicana.com/article-url",
  "url_slug": "article_url_slug",
  "scraped_at": "2024-10-14T14:15:30.123456",
  "word_count": 450,
  "char_count": 2847
}
```

**Summary Report (`scraping_summary.json`)**
```json
{
  "scraping_session": {
    "start_time": "2024-10-14T14:15:30.123456",
    "end_time": "2024-10-14T14:45:30.123456", 
    "duration_seconds": 1800.0,
    "total_articles_scraped": 127,
    "total_sections_failed": 0
  },
  "sections": {
    "cultura_origenes": {
      "name": "Cultura y Orígenes",
      "url": "https://www.cocinadominicana.com/cultura/herencia",
      "articles_scraped": 42,
      "directory": "cultura_origenes"
    }
  }
}
```

## 📊 Logging and Monitoring

### Canonical Log Examples

The scraper implements structured logging with canonical log lines:

**Session Tracking**
```
2024-10-14T14:15:30 [INFO] scraper: scrape_session_started start_time="2024-10-14T14:15:30" sections_count=4 output_dir="/path/to/scraped_content"
2024-10-14T14:45:30 [INFO] scraper: scrape_session_completed duration_seconds=1800 total_articles_scraped=127 total_sections_failed=0
```

**Performance Monitoring**
```
2024-10-14T14:16:15 [INFO] scraper: article_scrape_completed url="https://..." title="Recipe Title" word_count=450 duration_ms=890
2024-10-14T14:20:30 [INFO] scraper: section_processing_completed section="Cultura y Orígenes" articles_scraped=32 duration_ms=45000
```

**Error Handling**
```
2024-10-14T14:17:45 [INFO] scraper: rate_limit_encountered wait_time=25 original_delay=20
2024-10-14T14:18:10 [INFO] scraper: scrape_retry url="https://..." attempt=2 max_retries=3
```

### Log Files

- **Console Output**: Real-time logging to terminal
- **File Logging**: Persistent logs saved to `scraping.log`
- **Structured Format**: Machine-readable logs for monitoring tools

## 🔄 Rate Limiting and Reliability

### Intelligent Rate Limiting
- Automatic detection of rate limit responses
- Dynamic wait times based on API responses
- 5-second buffer added to all delays
- Exponential backoff for retry attempts

### Error Recovery
- 3 retry attempts for failed requests
- Graceful handling of network timeouts
- Comprehensive error logging with context
- Resume capability for interrupted sessions

### Performance Optimization
- Built-in 3-second delay between article requests
- Efficient file existence checking
- Memory-efficient content processing
- Progress tracking with detailed metrics

## 🛠️ Development

### Code Architecture

The codebase follows Clean Code principles:

- **Single Responsibility**: Each function has one clear purpose
- **Function Size**: All functions ≤20 lines
- **Descriptive Naming**: Self-documenting code with minimal comments
- **Separation of Concerns**: Clear boundaries between operations

### Key Components

**Core Classes**
- `DominicanCultureScraperV2`: Main scraper orchestration
- `PerformanceTimer`: Context manager for operation timing

**Utility Functions**
- `setup_canonical_logger()`: Logger configuration
- `log_canonical()`: Structured logging implementation
- `create_safe_filename()`: Safe filename generation
- `save_json_file()`: JSON file operations

### Testing

```bash
# Validate syntax
python3 -m py_compile scraper.py utils.py

# Test import
python3 -c "from scraper import DominicanCultureScraperV2; print('Import successful')"

# Dry run (test configuration)
python3 -c "
from scraper import DominicanCultureScraperV2
scraper = DominicanCultureScraperV2()
print(f'Configured for {len(scraper.sections)} sections')
print(f'Output directory: {scraper.output_dir}')
"
```

## 📈 Performance Metrics

Typical performance characteristics:

- **Scraping Speed**: ~3 seconds per article (including rate limiting)
- **Memory Usage**: <50MB for typical sessions
- **Success Rate**: >95% with retry logic
- **Resume Efficiency**: 100% skip rate for existing files

## 🤝 Contributing

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

## 📝 License

This project is for educational and research purposes. Please respect the website's robots.txt and terms of service.

## 🆘 Troubleshooting

### Common Issues

**API Key Error**
```
ValueError: FIRECRAWL_API_KEY not found in environment
```
**Solution**: Ensure `.env` file exists with valid `FIRECRAWL_API_KEY`

**Rate Limiting**
```
rate_limit_encountered wait_time=25 original_delay=20
```
**Solution**: This is normal behavior - the scraper automatically handles rate limits

**Import Errors**
```
ModuleNotFoundError: No module named 'firecrawl'
```
**Solution**: Install dependencies with `pip install -r requirements.txt`

### Debug Mode

Enable verbose logging:
```python
from utils import setup_canonical_logger

# Setup debug logging
logger = setup_canonical_logger(__name__, level="DEBUG")
```

### Performance Issues

Monitor performance with log analysis:
```bash
# Analyze timing patterns
grep "duration_ms" scraping.log | tail -20

# Check success rates  
grep -c "scrape_success" scraping.log
grep -c "scrape_failed" scraping.log
```

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/cristiandlahoz/cocina-dominicana-crawl/issues)
- **Documentation**: This README
- **Logs**: Check `scraping.log` for detailed operation logs

---

**Built with ❤️ for preserving Dominican culinary culture**