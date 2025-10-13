import os
import re
import time
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse
from datetime import datetime
import logging

from firecrawl import FirecrawlApp
from rich.console import Console
from rich.progress import Progress, TaskID

from config import ScrapingConfig, SECTIONS
from models import ArticleMetadata, ScrapedArticle, ScrapingStats, ProgressState
from utils import (
    setup_logging, create_safe_filename, extract_word_count,
    extract_dates_from_text, extract_recommendations, save_progress,
    load_progress, create_markdown_frontmatter, wait_with_backoff
)

class DominicanCuisineScraper:
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.logger = setup_logging()
        self.console = Console()
        self.firecrawl = FirecrawlApp(api_key=config.firecrawl_api_key)
        
        self.output_path = Path(config.output_dir)
        self.output_path.mkdir(exist_ok=True)
        
        self.progress_file = self.output_path / "progress.json"
        progress_data = load_progress(str(self.progress_file))
        self.state = ProgressState(**progress_data) if progress_data else ProgressState()
        
        self.stats = ScrapingStats(
            total_articles=0,
            successful_scrapes=0,
            failed_scrapes=0,
            sections_completed=[],
            duration_seconds=0.0
        )

    def discover_article_urls(self, section_key: str) -> List[str]:
        """Discover all article URLs in a section through pagination."""
        section_info = SECTIONS[section_key]
        base_url = urljoin(self.config.base_url, section_info["url"])
        
        all_urls = []
        page = 1
        
        self.logger.info(f"Discovering articles in section: {section_info['display_name']}")
        
        while page <= self.config.max_pages_per_section:
            if page == 1:
                page_url = base_url
            else:
                page_url = f"{base_url}/page/{page}"
            
            try:
                self.logger.info(f"Fetching page {page}: {page_url}")
                
                scrape_result = self.firecrawl.scrape_url(
                    page_url,
                    params={
                        'formats': ['markdown'],
                        'timeout': self.config.timeout
                    }
                )
                
                if not scrape_result.get('success'):
                    self.logger.warning(f"Failed to scrape page {page}: {page_url}")
                    break
                
                markdown_content = scrape_result.get('markdown', '')
                page_urls = self.extract_article_urls_from_page(markdown_content, section_key)
                
                if not page_urls:
                    self.logger.info(f"No articles found on page {page}, stopping pagination")
                    break
                
                all_urls.extend(page_urls)
                self.logger.info(f"Found {len(page_urls)} articles on page {page}")
                
                if not self.has_next_page(markdown_content):
                    self.logger.info(f"No next page found, stopping at page {page}")
                    break
                
                page += 1
                time.sleep(self.config.delay_between_requests)
                
            except Exception as e:
                self.logger.error(f"Error fetching page {page} of {section_key}: {e}")
                break
        
        unique_urls = list(dict.fromkeys(all_urls))
        self.logger.info(f"Discovered {len(unique_urls)} unique articles in {section_info['display_name']}")
        
        return unique_urls

    def extract_article_urls_from_page(self, markdown_content: str, section_key: str) -> List[str]:
        """Extract article URLs from a section page."""
        urls = []
        
        link_pattern = r'\[([^\]]+)\]\((https://www\.cocinadominicana\.com/[^)]+)\)'
        matches = re.findall(link_pattern, markdown_content)
        
        for title, url in matches:
            if self.is_article_url(url, section_key):
                urls.append(url)
        
        return urls

    def is_article_url(self, url: str, section_key: str) -> bool:
        """Check if a URL is an article URL."""
        exclude_patterns = [
            '/page/',
            '/cultura-dominicana',
            '/cultura/herencia',
            '/cultura/tradiciones-costumbres',
            '/cultura/celebraciones', 
            '/cultura/versus',
            '/inicia',
            '/recetas',
            '/suscribete',
            '/sobre',
            '#',
            'facebook.com',
            'instagram.com',
            'youtube.com',
            'pinterest.com',
            'whatsapp.com',
            'mailto:',
            '.jpg',
            '.png',
            '.pdf'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url:
                return False
        
        return url.startswith('https://www.cocinadominicana.com/') and len(url.split('/')) >= 4

    def has_next_page(self, markdown_content: str) -> bool:
        """Check if there's a next page link in the content."""
        next_patterns = [
            r'\[Next page\]',
            r'\[Siguiente\]',
            r'\[\d+\]\([^)]*page/\d+\)',
            r'página siguiente'
        ]
        
        for pattern in next_patterns:
            if re.search(pattern, markdown_content, re.IGNORECASE):
                return True
        
        return False

    def scrape_article(self, url: str, section_key: str) -> Optional[ScrapedArticle]:
        """Scrape a single article."""
        if url in self.state.completed_urls:
            self.logger.info(f"Skipping already completed article: {url}")
            return None
        
        for attempt in range(self.config.max_retries):
            try:
                self.logger.info(f"Scraping article (attempt {attempt + 1}): {url}")
                
                scrape_result = self.firecrawl.scrape_url(
                    url,
                    params={
                        'formats': ['markdown'],
                        'timeout': self.config.timeout
                    }
                )
                
                if not scrape_result.get('success'):
                    raise Exception(f"Firecrawl scraping failed: {scrape_result}")
                
                markdown_content = scrape_result.get('markdown', '')
                
                if not markdown_content:
                    raise Exception("No content retrieved")
                
                article = self.parse_article_content(markdown_content, url, section_key)
                
                if article:
                    self.state.completed_urls.append(url)
                    self.save_progress()
                    return article
                
            except Exception as e:
                self.logger.error(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < self.config.max_retries - 1:
                    wait_with_backoff(attempt, self.config.delay_between_requests, self.config.retry_backoff_factor)
        
        self.state.failed_urls.append(url)
        self.save_progress()
        return None

    def parse_article_content(self, markdown_content: str, url: str, section_key: str) -> Optional[ScrapedArticle]:
        """Parse article content and extract metadata."""
        try:
            title_match = re.search(r'^#\s+(.+?)$', markdown_content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else "Unknown Title"
            
            dates = extract_dates_from_text(markdown_content)
            
            content_start = markdown_content.find('\n', markdown_content.find(title)) if title_match else 0
            
            comments_start = self.find_comments_section(markdown_content)
            
            if comments_start != -1:
                content = markdown_content[content_start:comments_start].strip()
                comments = markdown_content[comments_start:].strip()
            else:
                content = markdown_content[content_start:].strip()
                comments = ""
            
            metadata = ArticleMetadata(
                title=title,
                url=url,
                publish_date=dates.get("publish_date"),
                review_date=dates.get("review_date"),
                word_count=extract_word_count(content),
                recommendations=extract_recommendations(content),
                section=section_key,
                slug=create_safe_filename(title)
            )
            
            return ScrapedArticle(
                metadata=metadata,
                content=content,
                comments=comments,
                scraped_at=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing article content for {url}: {e}")
            return None

    def find_comments_section(self, content: str) -> int:
        """Find where the comments section starts."""
        comment_indicators = [
            "## Commentarios",
            "## Comments", 
            "Comentarios",
            "wpDiscuz",
            "Load More Comments",
            "View all comments",
            "Insert",
            "Move Comment"
        ]
        
        for indicator in comment_indicators:
            pos = content.find(indicator)
            if pos != -1:
                return pos
        
        return -1

    def save_article(self, article: ScrapedArticle) -> None:
        """Save article to filesystem."""
        section_dir = self.output_path / article.metadata.section
        section_dir.mkdir(exist_ok=True)
        
        article_dir = section_dir / article.metadata.slug
        article_dir.mkdir(exist_ok=True)
        
        content_file = article_dir / "content.md"
        frontmatter = create_markdown_frontmatter({
            "title": article.metadata.title,
            "url": article.metadata.url,
            "publish_date": article.metadata.publish_date,
            "review_date": article.metadata.review_date,
            "word_count": article.metadata.word_count,
            "recommendations": article.metadata.recommendations,
            "section": article.metadata.section,
            "scraped_at": article.scraped_at.isoformat()
        })
        
        with open(content_file, 'w', encoding='utf-8') as f:
            f.write(frontmatter + article.content)
        
        if article.comments:
            comments_file = article_dir / "comments.md"
            with open(comments_file, 'w', encoding='utf-8') as f:
                f.write(f"# Comments for: {article.metadata.title}\n\n")
                f.write(article.comments)

    def scrape_section(self, section_key: str) -> None:
        """Scrape all articles in a section."""
        section_info = SECTIONS[section_key]
        self.logger.info(f"Starting to scrape section: {section_info['display_name']}")
        
        urls = self.discover_article_urls(section_key)
        self.state.total_found += len(urls)
        
        with Progress() as progress:
            task = progress.add_task(f"Scraping {section_info['display_name']}", total=len(urls))
            
            for url in urls:
                article = self.scrape_article(url, section_key)
                
                if article:
                    self.save_article(article)
                    self.stats.successful_scrapes += 1
                    self.state.total_scraped += 1
                    self.logger.info(f"Successfully scraped: {article.metadata.title}")
                else:
                    self.stats.failed_scrapes += 1
                    self.logger.error(f"Failed to scrape: {url}")
                
                progress.advance(task)
                time.sleep(self.config.delay_between_requests)
        
        self.stats.sections_completed.append(section_key)

    def scrape_all_sections(self) -> None:
        """Scrape all sections."""
        start_time = time.time()
        
        self.logger.info("Starting comprehensive scraping of Dominican cuisine content")
        
        for section_key in SECTIONS.keys():
            if section_key not in self.stats.sections_completed:
                self.state.current_section = section_key
                self.scrape_section(section_key)
                self.save_progress()
        
        end_time = time.time()
        self.stats.duration_seconds = end_time - start_time
        self.stats.total_articles = self.stats.successful_scrapes + self.stats.failed_scrapes
        
        self.generate_reports()

    def save_progress(self) -> None:
        """Save current progress state."""
        if self.config.preserve_progress:
            save_progress(str(self.progress_file), self.state.dict())

    def generate_reports(self) -> None:
        """Generate final reports and index."""
        self.logger.info("Generating reports and index...")
        
        self.generate_json_index()
        self.generate_readme()
        
        self.logger.info(f"Scraping completed successfully!")
        self.logger.info(f"Total articles: {self.stats.total_articles}")
        self.logger.info(f"Successful: {self.stats.successful_scrapes}")
        self.logger.info(f"Failed: {self.stats.failed_scrapes}")
        self.logger.info(f"Duration: {self.stats.duration_seconds:.2f} seconds")

    def generate_json_index(self) -> None:
        """Generate a JSON index of all scraped articles."""
        index = {
            "generated_at": datetime.now().isoformat(),
            "stats": self.stats.dict(),
            "sections": {}
        }
        
        for section_key in SECTIONS.keys():
            section_dir = self.output_path / section_key
            if section_dir.exists():
                articles = []
                for article_dir in section_dir.iterdir():
                    if article_dir.is_dir():
                        content_file = article_dir / "content.md"
                        if content_file.exists():
                            with open(content_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if content.startswith('---'):
                                    end = content.find('---', 3)
                                    if end != -1:
                                        import yaml
                                        try:
                                            metadata = yaml.safe_load(content[3:end])
                                            articles.append(metadata)
                                        except:
                                            pass
                
                index["sections"][section_key] = {
                    "display_name": SECTIONS[section_key]["display_name"],
                    "article_count": len(articles),
                    "articles": articles
                }
        
        index_file = self.output_path / "index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)

    def generate_readme(self) -> None:
        """Generate README with scraping statistics and summaries."""
        readme_content = f"""# Dominican Cuisine Cultural Content Scraper

## Scraping Statistics

- **Total Articles**: {self.stats.total_articles}
- **Successfully Scraped**: {self.stats.successful_scrapes}
- **Failed Scrapes**: {self.stats.failed_scrapes}
- **Duration**: {self.stats.duration_seconds:.2f} seconds
- **Scraped At**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Section Summary

"""

        for section_key, section_info in SECTIONS.items():
            section_dir = self.output_path / section_key
            article_count = 0
            if section_dir.exists():
                article_count = len([d for d in section_dir.iterdir() if d.is_dir()])
            
            readme_content += f"### {section_info['display_name']}\n"
            readme_content += f"- **Articles scraped**: {article_count}\n"
            readme_content += f"- **Location**: `{section_key}/`\n\n"

        readme_content += """## Project Structure

```
topics/
├── cultura-y-origenes/
│   ├── article-1/
│   │   ├── content.md
│   │   └── comments.md
│   └── article-2/
│       ├── content.md
│       └── comments.md
├── costumbres-y-tradiciones/
├── festividades-y-celebraciones/
├── en-comparacion/
├── index.json
├── progress.json
└── README.md
```

## Usage

Each article is stored in its own directory with:
- `content.md`: Article content with YAML frontmatter containing metadata
- `comments.md`: Comments section (if available)

The `index.json` file contains a complete catalog of all scraped articles with metadata.

## Data Quality

All articles include:
- Title and original URL
- Publish and review dates (when available)
- Word count
- Any recommendations mentioned
- Full article content with minimal cleaning
- Complete comment sections

Generated by Dominican Cuisine Scraper v1.0
"""

        readme_file = self.output_path / "README.md"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)