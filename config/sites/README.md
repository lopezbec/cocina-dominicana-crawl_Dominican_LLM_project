# Site Configurations

This directory contains site-specific configurations for the multi-site web scraper.

## Directory Structure

Each site has its own directory named after the domain (with dots replaced by underscores):

```
sites/
├── cocinadominicana_com/
│   ├── config.yml
│   └── processing_patterns.yml
├── example_com/
│   ├── config.yml
│   └── processing_patterns.yml
└── README.md (this file)
```

## Adding a New Site

### Option 1: Using Make (Recommended)

```bash
make setup-site DOMAIN=example.com
```

This will create a new directory with template files that you can customize.

### Option 2: Manual Setup

1. Create a new directory for your domain:
```bash
mkdir sites/example_com
```

2. Copy the template files:
```bash
cp templates/site_config.yml sites/example_com/config.yml
cp templates/processing_patterns.yml sites/example_com/processing_patterns.yml
```

3. Edit `sites/example_com/config.yml`:
   - Update `domain` and `base_url`
   - Configure `filters` for URL patterns
   - Optionally add `sections` for predefined crawl targets

4. Edit `sites/example_com/processing_patterns.yml` (optional):
   - Add site-specific navigation patterns to remove
   - Add footer markers
   - Configure excluded article paths

## Configuration Files

### config.yml

Required site-specific configuration:

```yaml
domain: "example.com"
base_url: "https://www.example.com"

filters:
  include_patterns:
    - "example\\.com/.*"
  exclude_patterns:
    - "ads"
    - "tracking"

# Optional: Predefined sections to scrape
sections:
  blog:
    name: "Blog Posts"
    url: "https://www.example.com/blog"
```

### processing_patterns.yml

Optional post-processing configuration:

```yaml
# Regex patterns to remove during plaintext conversion
navigation_patterns:
  - "Subscribe to our newsletter.*"
  - "Follow us on.*"

# Text markers that indicate start of footer content
footer_markers:
  - "About the Author"
  - "Related Posts"

# URL paths to exclude from article filtering
excluded_article_paths:
  - "category/sponsored"
```

## Usage

Once configured, use the site with:

```bash
# Set the domain
export CRAWL_DOMAIN=example.com

# Or inline
CRAWL_DOMAIN=example.com make crawl
CRAWL_DOMAIN=example.com uv run python -m core.cli scrape-all
```

## Configuration Inheritance

Site configurations are merged with global defaults from `config.yml`:

1. Global config is loaded first (crawler settings, default filters)
2. Site config overrides/extends global settings
3. Lists (like `exclude_patterns`) are concatenated
4. Other values are overridden

## Tips

- Start with minimal configuration and add filters as needed
- Test with a single URL first: `scrape <url>`
- Use `discover` command to see what URLs will be scraped
- Check `scraping.log` for detailed execution information
