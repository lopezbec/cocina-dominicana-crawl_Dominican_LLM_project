# Dominican Cuisine Cultural Content Scraper

A comprehensive, production-ready web scraper for extracting cultural articles from [cocinadominicana.com](https://www.cocinadominicana.com/cultura-dominicana) using Firecrawl.

## Features

- **Comprehensive Coverage**: Scrapes all four main cultural sections
- **Ethical Scraping**: Uses Firecrawl with proper rate limiting and retry logic
- **Robust Error Handling**: Continues processing even if individual articles fail
- **Progress Tracking**: Resume interrupted scraping sessions
- **Rich Metadata**: Extracts titles, dates, word counts, and recommendations
- **Organized Output**: Creates structured markdown files with frontmatter
- **Pagination Handling**: Automatically discovers and processes paginated content
- **Statistics & Reporting**: Generates comprehensive reports and JSON index

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Get a Firecrawl API key from [firecrawl.dev](https://firecrawl.dev)
4. Copy `.env.example` to `.env` and add your API key:
   ```bash
   cp .env.example .env
   # Edit .env and add your FIRECRAWL_API_KEY
   ```

## Usage

### Basic Usage
```bash
# Scrape all sections
python main.py

# Scrape specific section
python main.py --section cultura-y-origenes

# Custom output directory
python main.py --output-dir my_content

# Resume interrupted session
python main.py --resume
```

### Advanced Options
```bash
python main.py \
  --section all \
  --output-dir topics \
  --delay 3.0 \
  --max-pages 25 \
  --log-level DEBUG
```

## Configuration

Key configuration options in `config.py`:

- `delay_between_requests`: Delay between requests (default: 2.0 seconds)
- `max_retries`: Maximum retry attempts for failed requests (default: 3)
- `max_pages_per_section`: Maximum pages to scrape per section (default: 50)
- `timeout`: Request timeout in seconds (default: 30)

## Output Structure

```
topics/
├── cultura-y-origenes/
│   ├── el-colmado-dominicano/
│   │   ├── content.md
│   │   └── comments.md
│   └── platos-dominicanos-poco-comunes/
│       ├── content.md
│       └── comments.md
├── costumbres-y-tradiciones/
├── festividades-y-celebraciones/
├── en-comparacion/
├── index.json
├── progress.json
└── README.md
```

## Article Format

Each article includes YAML frontmatter with metadata:

```yaml
---
title: El Colmado Dominicano
url: https://www.cocinadominicana.com/colmado-dominicano
publish_date: 5 Ene 2002
review_date: 20 Ago 2025
word_count: 847
recommendations:
  - "Lleva tu jarro de metal debajo del brazo con orgullo"
section: cultura-y-origenes
scraped_at: 2025-01-12T10:30:00
---

Article content follows here...
```

## Sections Covered

The scraper extracts content from four main cultural sections:

1. **Cultura y Orígenes** (`cultura-y-origenes/`)
   - Cultural knowledge, facts, and tips about Dominican culinary heritage
   - URL: `/cultura/herencia`

2. **Costumbres y Tradiciones** (`costumbres-y-tradiciones/`)
   - Dominican customs and traditions around food and culture
   - URL: `/cultura/tradiciones-costumbres`

3. **Festividades y Celebraciones** (`festividades-y-celebraciones/`)
   - Food and customs for Christmas, New Year, Mother's Day, birthdays, Lent, and Easter
   - URL: `/cultura/celebraciones`

4. **En Comparación** (`en-comparacion/`)
   - Comparisons between Dominican food and other countries' cuisines
   - URL: `/cultura/versus`

## Error Handling

The scraper includes comprehensive error handling:

- **Retry Logic**: Failed requests are retried up to 3 times with exponential backoff
- **Graceful Degradation**: Individual article failures don't stop the entire process
- **Progress Persistence**: Resume interrupted sessions with `--resume`
- **Detailed Logging**: All activities and errors are logged to `scraping.log`

## Rate Limiting

The scraper respects the website with:

- Configurable delays between requests (default: 2 seconds)
- Exponential backoff for retries
- Proper user agent identification
- Timeout handling

## Monitoring Progress

The scraper provides real-time progress updates and generates:

- **Console Output**: Rich progress bars and status updates
- **Log Files**: Detailed logging in `scraping.log`
- **Progress File**: `progress.json` for resuming sessions
- **Final Reports**: Statistics and article index

## Best Practices

1. **Start Small**: Test with a single section first
2. **Monitor Resources**: Check your Firecrawl API usage
3. **Respect Rate Limits**: Don't reduce delays too aggressively
4. **Review Results**: Check the generated content for quality
5. **Backup Progress**: The `progress.json` file enables resuming

## Data Extraction

For each article, the scraper extracts and preserves:

- **Title**: Article headline
- **Review Date**: When the article was last updated
- **Publish Date**: Original publication date
- **Original URL**: Source link
- **Word Count**: Approximate word count of the content
- **Recommendations**: Any recommendations mentioned in the article
- **Full Content**: Complete article text with minimal cleaning
- **Comments**: Complete comment section when available

## File Organization

Articles are organized in a hierarchical structure:

```
topics/
├── [section-name]/
│   ├── [article-slug]/
│   │   ├── content.md      # Article with frontmatter
│   │   └── comments.md     # Comments (if available)
│   └── [another-article]/
├── index.json              # Complete catalog
├── progress.json           # Progress tracking
└── README.md              # Generated statistics
```

## Troubleshooting

### Common Issues

**API Key Errors**: Ensure your Firecrawl API key is valid and in the `.env` file

**Network Timeouts**: Increase the timeout value in `config.py`

**Missing Content**: Some articles may have different structures; check logs for specifics

**Rate Limiting**: If you encounter rate limits, increase the delay between requests

### Debug Mode

Run with debug logging for detailed information:
```bash
python main.py --log-level DEBUG
```

### Resume Functionality

If scraping is interrupted, you can resume where you left off:
```bash
python main.py --resume
```

The scraper automatically saves progress and skips already-downloaded articles.

## Technical Architecture

### Core Components

- **`config.py`**: Configuration management and section definitions
- **`models.py`**: Pydantic models for data validation and structure
- **`utils.py`**: Utility functions for text processing and file operations
- **`scraper.py`**: Main scraping logic with Firecrawl integration
- **`main.py`**: Command-line interface and entry point

### Key Features

- **Pagination Detection**: Automatically discovers and follows pagination links
- **Content Parsing**: Intelligent extraction of article content vs. navigation/ads
- **Metadata Extraction**: Parses dates, recommendations, and other structured data
- **Error Recovery**: Robust error handling with retry mechanisms
- **Progress Persistence**: State management for long-running scraping sessions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with a small subset of articles
5. Submit a pull request

## License

This project is for educational and research purposes. Please respect the website's robots.txt and terms of service.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error details  
3. Open an issue with detailed information about your problem

## Dependencies

- **firecrawl-py**: Ethical web scraping with Firecrawl
- **pydantic**: Data validation and settings management
- **rich**: Rich terminal UI and progress bars
- **python-slugify**: URL-safe filename generation
- **python-dotenv**: Environment variable management
- **PyYAML**: YAML frontmatter generation
- **beautifulsoup4**: HTML parsing utilities
- **requests**: HTTP client library

---

**Built with ❤️ for preserving Dominican culinary culture and heritage.**