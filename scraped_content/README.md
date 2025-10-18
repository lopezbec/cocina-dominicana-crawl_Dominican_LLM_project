# Scraped Content Structure

This directory contains example files demonstrating the output structure of the Dominican Culture Scraper. Each scraped article generates two files:

## Directory Organization

```
scraped_content/
├── comparaciones/           # Cultural comparisons
├── cultura_origenes/        # Culture and origins
├── festividades_celebraciones/  # Festivities and celebrations
└── tradiciones_costumbres/  # Traditions and customs
```

## File Format

Each article produces:

1. **Markdown file (`.md`)**: Article content with frontmatter metadata
2. **JSON file (`.json`)**: Structured metadata for programmatic access

## Example Files

This repository includes minimal example files to demonstrate the expected output format. When you run the scraper, it will populate these directories with actual content from [Cocina Dominicana](https://www.cocinadominicana.com).

## Usage

Run the scraper to populate this directory:

```bash
python scraper.py
```

The scraper will:
- Skip existing files (resume capability)
- Organize content by category
- Generate both markdown and JSON formats
- Create a summary report (`scraping_summary.json`)
