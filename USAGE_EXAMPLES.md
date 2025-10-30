# Usage Examples

Quick reference guide for common scraping scenarios.

## Prerequisites

Ensure Firecrawl services are running:

```bash
make firecrawl-start
make test
```

## Common Scenarios

### 1. Scrape All Configured Sections

Run the default scraper with all sections defined in config.yaml:

```bash
make scrape
```

Or directly:

```bash
python scraper.py
python cli.py scrape-all
```

### 2. Scrape a Single Recipe or Article

Scrape one specific URL:

```bash
make scrape-url URL="https://www.cocinadominicana.com/batata-asada"
```

Or with custom output directory:

```bash
python cli.py scrape "https://www.cocinadominicana.com/batata-asada" --output recipes
```

### 3. Crawl an Entire Category

Automatically discover and scrape all articles from a category page:

```bash
make scrape-category URL="https://www.cocinadominicana.com/cocina"
```

With custom depth and name:

```bash
python cli.py crawl "https://www.cocinadominicana.com/cocina" --depth 2 --name cocina_techniques
```

Depth explanation:
- `--depth 1`: Scrape only articles linked directly from the category page
- `--depth 2`: Also scrape articles linked from those articles
- `--depth 3`: Go one level deeper (use with caution)

### 4. Batch Scraping from URL List

Create a file with URLs to scrape:

```bash
cat > my_recipes.txt << EOF
https://www.cocinadominicana.com/batata-asada
https://www.cocinadominicana.com/mangu
https://www.cocinadominicana.com/sancocho
https://www.cocinadominicana.com/moro-de-guandules
EOF
```

Scrape all URLs:

```bash
make scrape-list FILE=my_recipes.txt
```

Or with custom output:

```bash
python cli.py scrape-list my_recipes.txt --output favorite_recipes
```

### 5. Discover URLs Without Scraping

Preview what would be scraped from a page:

```bash
make scrape-discover URL="https://www.cocinadominicana.com/inicia"
```

Save discovered URLs to a file:

```bash
python cli.py discover "https://www.cocinadominicana.com/inicia" --save discovered_urls.txt
```

Then review and scrape selected URLs:

```bash
python cli.py scrape-list discovered_urls.txt
```

## Advanced Usage

### Custom Configuration

Edit `config.yaml` to customize behavior:

```yaml
crawler:
  max_depth: 3
  delay_seconds: 1.0
  skip_existing: false

filters:
  exclude_patterns:
    - "suscribete"
    - "contactanos"
```

### Re-scrape Existing Content

By default, existing files are skipped. To force re-scraping:

```bash
python cli.py crawl "https://www.cocinadominicana.com/cocina" --no-skip
```

### Disable URL Filtering

Discover all URLs without config-based filtering:

```bash
python cli.py discover "https://www.cocinadominicana.com/inicia" --no-filter
```

## Programmatic Usage

### Python Script Example

```python
from scraper import Scraper

scraper = Scraper(config_path="config.yaml")

article = scraper.scrape_url(
    "https://www.cocinadominicana.com/batata-asada",
    output_directory="recipes"
)

if article:
    print(f"Scraped: {article['title']}")
    print(f"Words: {article['word_count']}")

result = scraper.crawl_category(
    category_url="https://www.cocinadominicana.com/cocina",
    category_name="cocina",
    max_depth=2,
    skip_existing=True
)

print(f"Discovered {result['urls_discovered']} URLs")
print(f"Scraped {result['articles_scraped']} articles")

urls = scraper.auto_discover_urls(
    "https://www.cocinadominicana.com/inicia",
    use_config_filters=True
)

print(f"Found {len(urls)} URLs")
for url in urls[:5]:
    print(f"  - {url}")
```

## Output Locations

Scraped content is organized by method:

```
scraped_content/
├── cultura_origenes/          # Section-based scraping
├── tradiciones_costumbres/    # Section-based scraping
├── cocina/                    # Category crawling
│   └── crawl_summary.json
├── custom/                    # Single URL scraping (default)
├── recipes/                   # Single URL scraping (custom name)
├── batch/                     # Batch scraping (default)
└── scraping_summary.json      # Section-based summary
```

## Performance Tips

### Adjust Scraping Speed

Edit `config.yaml`:

```yaml
crawler:
  delay_seconds: 0.3
```

Lower values = faster scraping (but more resource intensive)

### Monitor Progress

Watch logs in real-time:

```bash
tail -f scraping.log
```

Filter for specific events:

```bash
rg "article_scrape_completed" scraping.log
rg "duration_ms" scraping.log | tail -20
```

### Check Service Health

```bash
make firecrawl-status
make firecrawl-logs
```

## Troubleshooting

### No URLs Discovered

Check if filters are too restrictive:

```bash
python cli.py discover "https://www.cocinadominicana.com/cocina" --no-filter
```

### Slow Scraping

Reduce delay in config.yaml:

```yaml
crawler:
  delay_seconds: 0.3
```

### Services Not Running

```bash
make firecrawl-start
make test
```

## Stop Services

When finished scraping:

```bash
make firecrawl-stop
```

## Clean Up

Remove scraped content:

```bash
make clean
```

Remove everything including Firecrawl:

```bash
make clean-all
```
