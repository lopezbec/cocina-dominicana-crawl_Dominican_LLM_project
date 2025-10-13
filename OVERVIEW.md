# Project Overview: Dominican Cuisine Cultural Content Scraper

## 🎯 Project Summary

This is a comprehensive, production-ready web scraper designed to extract cultural articles from [cocinadominicana.com](https://www.cocinadominicana.com/cultura-dominicana). The scraper uses Firecrawl for ethical web scraping and implements robust error handling, progress tracking, and content organization.

## 📁 Project Structure

```
cocina-dominicana-crawl/
├── config.py              # Configuration management
├── models.py               # Data models with Pydantic
├── utils.py                # Utility functions
├── scraper.py              # Main scraper logic
├── main.py                 # CLI entry point
├── demo.py                 # Demo script for testing
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── .gitignore             # Git ignore rules
├── install.sh             # Installation script
├── Makefile               # Project automation
├── setup.py               # Package setup
├── README.md              # Comprehensive documentation
└── OVERVIEW.md            # This file
```

## 🔧 Core Components

### 1. Configuration System (`config.py`)
- **ScrapingConfig**: Dataclass with all scraping parameters
- **SECTIONS**: Dictionary mapping section keys to URLs and display names
- Environment variable loading with validation

### 2. Data Models (`models.py`)
- **ArticleMetadata**: Article information structure
- **ScrapedArticle**: Complete article with content and metadata
- **ScrapingStats**: Performance and statistics tracking
- **ProgressState**: Resume functionality support

### 3. Utilities (`utils.py`)
- Text processing and content extraction functions
- Date parsing from Spanish content
- Recommendation extraction using regex patterns
- Markdown frontmatter generation
- Progress state management
- Logging configuration

### 4. Scraper Engine (`scraper.py`)
- **DominicanCuisineScraper**: Main scraping class
- URL discovery through pagination
- Article content parsing and metadata extraction
- Error handling with exponential backoff
- Progress tracking and resume functionality
- Report generation (JSON index + README)

### 5. CLI Interface (`main.py`)
- Command-line argument parsing
- Section selection (individual or all)
- Configuration override options
- Error handling and user feedback

## 🌐 Target Website Analysis

### Sections Covered
1. **Cultura y Orígenes** (`/cultura/herencia`)
2. **Costumbres y Tradiciones** (`/cultura/tradiciones-costumbres`)
3. **Festividades y Celebraciones** (`/cultura/celebraciones`)
4. **En Comparación** (`/cultura/versus`)

### Content Structure
- **Main Pages**: Section overview with article previews
- **Pagination**: `/page/2`, `/page/3`, etc.
- **Articles**: Individual content with metadata
- **Comments**: User discussions (when available)

### Data Extraction
- Article titles and URLs
- Publish and review dates
- Word counts and recommendations
- Full content with minimal cleaning
- Complete comment sections

## 🏗️ Architecture Features

### Ethical Scraping
- Uses Firecrawl for responsible data extraction
- Configurable rate limiting (default: 2 seconds)
- Proper user agent identification
- Respect for website structure and robots.txt

### Error Handling
- **Retry Logic**: Up to 3 attempts with exponential backoff
- **Graceful Degradation**: Individual failures don't stop the process
- **Comprehensive Logging**: All activities logged to file and console
- **Progress Persistence**: Resume interrupted sessions

### Content Processing
- **Smart URL Filtering**: Excludes navigation, images, and external links
- **Pagination Detection**: Automatically follows "Next" links
- **Content Parsing**: Separates article content from comments/navigation
- **Metadata Extraction**: Parses dates, recommendations, and structured data

### Output Organization
```
topics/
├── cultura-y-origenes/
│   ├── el-colmado-dominicano/
│   │   ├── content.md        # Article with YAML frontmatter
│   │   └── comments.md       # Comments section
│   └── platos-dominicanos-poco-comunes/
├── costumbres-y-tradiciones/
├── festividades-y-celebraciones/
├── en-comparacion/
├── index.json               # Complete article catalog
├── progress.json            # Resume state
└── README.md               # Generated statistics
```

## 🚀 Quick Start

1. **Installation**
   ```bash
   ./install.sh
   ```

2. **Configuration**
   ```bash
   cp .env.example .env
   # Edit .env and add your Firecrawl API key
   ```

3. **Demo Run**
   ```bash
   make demo
   ```

4. **Full Scraping**
   ```bash
   make run
   ```

## 🎛️ Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `delay_between_requests` | 2.0 | Seconds between requests |
| `max_retries` | 3 | Retry attempts for failed requests |
| `max_pages_per_section` | 50 | Maximum pages to scrape per section |
| `timeout` | 30 | Request timeout in seconds |
| `preserve_progress` | True | Enable resume functionality |

## 📊 Output Format

### Article Frontmatter
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
```

### JSON Index Structure
```json
{
  "generated_at": "2025-01-12T10:30:00",
  "stats": {
    "total_articles": 150,
    "successful_scrapes": 148,
    "failed_scrapes": 2,
    "duration_seconds": 1200.5
  },
  "sections": {
    "cultura-y-origenes": {
      "display_name": "Cultura y Orígenes",
      "article_count": 42,
      "articles": [...]
    }
  }
}
```

## 🔍 Quality Assurance

### Testing
- Module import validation
- Configuration verification
- Demo script for quick testing
- Code quality checks with py_compile

### Monitoring
- Real-time progress bars
- Detailed logging (file + console)
- Statistics tracking
- Error categorization and reporting

### Resume Capability
- Progress state persistence
- Skip already-downloaded articles
- Resume from any interruption point
- Maintain consistency across sessions

## 📈 Performance Characteristics

### Scalability
- Handles large article collections (100+ articles per section)
- Memory-efficient processing (articles processed individually)
- Disk space optimization with compressed content

### Reliability
- Network timeout handling
- Rate limiting compliance
- Automatic retry with backoff
- Progress checkpointing

### Efficiency
- Smart URL filtering reduces unnecessary requests
- Content caching through Firecrawl
- Parallel processing where appropriate
- Optimal pagination detection

## 🔒 Ethical Considerations

### Compliance
- Respects robots.txt guidelines
- Uses proper rate limiting
- Identifies itself with appropriate user agent
- Follows website's terms of service

### Data Handling
- Preserves original content attribution
- Maintains source URL references
- Minimal content modification
- Respectful of intellectual property

## 🛠️ Development Notes

### Dependencies
- **firecrawl-py**: Ethical web scraping
- **pydantic**: Data validation and serialization
- **rich**: Terminal UI and progress visualization
- **python-slugify**: URL-safe filename generation
- **python-dotenv**: Environment management
- **PyYAML**: YAML frontmatter generation

### Code Quality
- Type hints throughout
- Comprehensive error handling
- Modular architecture
- Clear separation of concerns
- Extensive documentation

### Extensibility
- Easy to add new sections
- Configurable extraction rules
- Pluggable content processors
- Customizable output formats

## 📝 Future Enhancements

### Potential Improvements
- Multi-language content detection
- Image download and processing
- Recipe extraction from articles
- Advanced content analysis
- Database storage options
- Web interface for monitoring

### Optimization Opportunities
- Parallel section processing
- Content deduplication
- Advanced caching strategies
- Incremental updates
- Real-time notifications

---

**Built with ❤️ for preserving Dominican culinary culture and heritage.**