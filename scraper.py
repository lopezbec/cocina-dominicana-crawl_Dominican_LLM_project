"""
Dominican Culture Scraper using Firecrawl
Includes rate limiting and retry logic
"""

from firecrawl import Firecrawl
import os
import re
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
from utils import setup_canonical_logger, log_canonical, PerformanceTimer, create_safe_filename, save_json_file

load_dotenv()


class DominicanCultureScraperV2:
    def __init__(self):
        self.logger = setup_canonical_logger(__name__)
        self.api_key = os.getenv("FIRECRAWL_API_KEY")
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY not found in environment")

        self.firecrawl = Firecrawl(api_key=self.api_key)
        self.base_url = "https://www.cocinadominicana.com"
        self._initialize_sections()
        self._create_output_directories()

    def _initialize_sections(self):
        """Initialize scraping sections configuration."""
        self.sections = {
            "cultura_origenes": {
                "name": "Cultura y Orígenes",
                "url": f"{self.base_url}/cultura/herencia",
                "directory": "cultura_origenes"
            },
            "tradiciones_costumbres": {
                "name": "Tradiciones y Costumbres",
                "url": f"{self.base_url}/cultura/tradiciones-costumbres",
                "directory": "tradiciones_costumbres"
            },
            "festividades_celebraciones": {
                "name": "Festividades y Celebraciones",
                "url": f"{self.base_url}/cultura/celebraciones",
                "directory": "festividades_celebraciones"
            },
            "comparaciones": {
                "name": "Comparaciones",
                "url": f"{self.base_url}/cultura/versus",
                "directory": "comparaciones"
            }
        }

    def _create_output_directories(self):
        """Create output directory structure."""
        self.output_dir = Path("scraped_content")
        self.output_dir.mkdir(exist_ok=True)

        for section_info in self.sections.values():
            section_dir = self.output_dir / section_info["directory"]
            section_dir.mkdir(exist_ok=True)

    def _handle_rate_limit_error(self, error_msg: str, base_delay: int) -> int:
        """Handle rate limit error and return wait time."""
        wait_time = base_delay
        if "retry after" in error_msg:
            try:
                match = re.search(r'retry after (\d+)s', error_msg)
                if match:
                    wait_time = int(match.group(1))
            except:
                pass

        final_wait = wait_time + 5
        log_canonical(self.logger, "rate_limit_encountered",
                      wait_time=final_wait, original_delay=wait_time)
        time.sleep(final_wait)
        return final_wait

    def scrape_with_retry(self, url: str, max_retries: int = 3, base_delay: int = 20) -> Optional[object]:
        """Safely scrape with rate-limiting and retry logic."""
        with PerformanceTimer() as timer:
            for attempt in range(max_retries):
                try:
                    doc = self.firecrawl.scrape(url, formats=["markdown"])
                    log_canonical(self.logger, "scrape_success",
                                  url=url, attempt=attempt + 1, duration_ms=timer.duration_ms)
                    return doc

                except Exception as e:
                    error_msg = str(e)

                    if "Rate Limit Exceeded" in error_msg:
                        self._handle_rate_limit_error(error_msg, base_delay)

                        if attempt < max_retries - 1:
                            log_canonical(self.logger, "scrape_retry",
                                          url=url, attempt=attempt + 2, max_retries=max_retries)
                            continue

                    log_canonical(self.logger, "scrape_error",
                                  url=url, attempt=attempt + 1, error=error_msg)

                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)

            log_canonical(self.logger, "scrape_failed",
                          url=url, max_retries=max_retries, duration_ms=timer.duration_ms)
            return None

    def _extract_urls_from_markdown(self, markdown_content: str) -> set:
        """Extract URLs from markdown content using regex patterns."""
        patterns = [
            r'\](https://www\.cocinadominicana\.com/([^)]+))\)',
            r'\((https://www\.cocinadominicana\.com/([^)]+))\)',
        ]

        all_urls = set()
        for pattern in patterns:
            matches = re.findall(pattern, markdown_content)
            for match in matches:
                if isinstance(match, tuple):
                    url = match[0] if match[0].startswith('http') else f"{self.base_url}/{match[0]}"
                else:
                    url = match if match.startswith('http') else f"{self.base_url}/{match}"
                all_urls.add(url)

        return all_urls

    def _filter_valid_article_urls(self, urls: set, section_url: str) -> List[str]:
        """Filter URLs to get only valid article URLs."""
        excluded_paths = [
            'cultura/herencia', 'cultura/tradiciones-costumbres',
            'cultura/celebraciones', 'cultura/versus'
        ]

        valid_urls = []
        for url in urls:
            url_path = url.replace(self.base_url + '/', '')

            if (not url.endswith(('.jpg', '.png', '.gif', '.jpeg')) and
                    '/cultura/' not in url and
                    '#' not in url and
                    'dominicancooking.com' not in url and
                    'wp-content' not in url and
                    url_path and
                    url_path not in excluded_paths and
                    url != section_url):
                valid_urls.append(url)

        return sorted(valid_urls)

    def discover_article_urls(self, section_url: str) -> List[str]:
        """Extract all article URLs from a section page."""
        with PerformanceTimer() as timer:
            log_canonical(self.logger, "url_discovery_started", section_url=section_url)

            doc = self.scrape_with_retry(section_url)
            if not doc:
                log_canonical(self.logger, "url_discovery_failed",
                              section_url=section_url, reason="scrape_failed")
                return []

            if not hasattr(doc, 'markdown') or not getattr(doc, 'markdown', None):
                log_canonical(self.logger, "url_discovery_failed",
                              section_url=section_url, reason="no_markdown")
                return []

            markdown_content = getattr(doc, 'markdown')
            all_urls = self._extract_urls_from_markdown(markdown_content)
            article_urls = self._filter_valid_article_urls(all_urls, section_url)

            log_canonical(self.logger, "url_discovery_completed",
                          section_url=section_url, urls_found=len(article_urls),
                          duration_ms=timer.duration_ms)
            return article_urls

    def _extract_article_metadata(self, doc) -> Dict[str, str]:
        """Extract metadata from scraped document."""
        title = "Unknown Title"
        description = ""

        if hasattr(doc, 'metadata'):
            metadata = getattr(doc, 'metadata')
            if metadata:
                title = getattr(metadata, 'title', 'Unknown Title')
                description = getattr(metadata, 'description', '')

        return {"title": title, "description": description}

    def scrape_article(self, url: str) -> Optional[Dict]:
        """Scrape an individual article."""
        with PerformanceTimer() as timer:
            log_canonical(self.logger, "article_scrape_started", url=url)

            doc = self.scrape_with_retry(url)
            if not doc:
                log_canonical(self.logger, "article_scrape_failed",
                              url=url, reason="scrape_failed")
                return None

            if not hasattr(doc, 'markdown') or not getattr(doc, 'markdown', None):
                log_canonical(self.logger, "article_scrape_failed",
                              url=url, reason="no_content")
                return None

            markdown_content = getattr(doc, 'markdown')
            metadata = self._extract_article_metadata(doc)

            url_slug = url.replace(self.base_url + '/', '').replace('/', '_')
            word_count = len(markdown_content.split())
            char_count = len(markdown_content)

            article_data = {
                "title": metadata["title"],
                "description": metadata["description"],
                "url": url,
                "url_slug": url_slug,
                "scraped_at": datetime.now().isoformat(),
                "word_count": word_count,
                "char_count": char_count,
                "content": markdown_content
            }

            log_canonical(self.logger, "article_scrape_completed",
                          url=url, title=metadata["title"], word_count=word_count,
                          duration_ms=timer.duration_ms)
            return article_data

    def save_article(self, article_data: Dict, section_directory: str):
        """Save article to file."""
        if not article_data:
            return

        with PerformanceTimer() as timer:
            section_dir = self.output_dir / section_directory
            safe_filename = create_safe_filename(article_data['url_slug'])

            content_file = section_dir / f"{safe_filename}.md"
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write("---\n")
                f.write(f"title: \"{article_data['title']}\"\n")
                if article_data['description']:
                    f.write(f"description: \"{article_data['description']}\"\n")
                f.write(f"url: {article_data['url']}\n")
                f.write(f"scraped_at: {article_data['scraped_at']}\n")
                f.write(f"word_count: {article_data['word_count']}\n")
                f.write(f"char_count: {article_data['char_count']}\n")
                f.write("---\n\n")
                f.write(article_data['content'])

            metadata_file = section_dir / f"{safe_filename}.json"
            metadata = {k: v for k, v in article_data.items() if k != 'content'}
            save_json_file(metadata, metadata_file)

            log_canonical(self.logger, "article_save_completed",
                          filename=content_file.name, duration_ms=timer.duration_ms)

    def _check_existing_file(self, url: str, section_info: Dict) -> bool:
        """Check if an article file already exists."""
        url_slug = url.replace(self.base_url + '/', '').replace('/', '_')
        safe_filename = create_safe_filename(url_slug)
        section_dir = self.output_dir / section_info['directory']
        content_file = section_dir / f"{safe_filename}.md"
        return content_file.exists()

    def _process_article_batch(self, article_urls: List[str], section_info: Dict) -> Dict[str, int]:
        """Process a batch of articles for a section."""
        scraped_count = 0
        failed_count = 0
        skipped_count = 0

        for i, url in enumerate(article_urls, 1):
            if self._check_existing_file(url, section_info):
                log_canonical(self.logger, "article_skipped",
                              url=url, reason="already_exists", progress=f"{i}/{len(article_urls)}")
                skipped_count += 1
                continue

            article_data = self.scrape_article(url)

            if article_data:
                self.save_article(article_data, section_info['directory'])
                scraped_count += 1
            else:
                failed_count += 1

            time.sleep(3)

        return {
            "scraped": scraped_count,
            "failed": failed_count,
            "skipped": skipped_count
        }

    def scrape_section(self, section_key: str):
        """Scrape all articles from a section."""
        with PerformanceTimer() as timer:
            section_info = self.sections[section_key]
            log_canonical(self.logger, "section_processing_started",
                          section=section_info['name'], section_key=section_key)

            article_urls = self.discover_article_urls(section_info['url'])

            if not article_urls:
                log_canonical(self.logger, "section_processing_failed",
                              section=section_info['name'], reason="no_articles")
                return

            metrics = self._process_article_batch(article_urls, section_info)

            log_canonical(self.logger, "section_processing_completed",
                          section=section_info['name'],
                          articles_scraped=metrics["scraped"],
                          articles_failed=metrics["failed"],
                          articles_skipped=metrics["skipped"],
                          total_articles=len(article_urls),
                          duration_ms=timer.duration_ms)

    def _initialize_scraping_session(self) -> Dict[str, Any]:
        """Initialize the scraping session and return session info."""
        start_time = datetime.now()
        session_info = {
            "start_time": start_time,
            "output_dir": self.output_dir.absolute(),
            "sections_count": len(self.sections)
        }

        log_canonical(self.logger, "scrape_session_started",
                      start_time=start_time.isoformat(),
                      output_dir=str(session_info["output_dir"]),
                      sections_count=session_info["sections_count"])

        return session_info

    def _process_all_sections(self) -> Dict[str, int]:
        """Process all sections and return metrics."""
        total_scraped = 0
        total_failed = 0

        for section_key in self.sections:
            try:
                self.scrape_section(section_key)
                section_dir = self.output_dir / self.sections[section_key]['directory']
                md_files = list(section_dir.glob("*.md"))
                total_scraped += len(md_files)

            except Exception as e:
                log_canonical(self.logger, "section_error",
                              section_key=section_key, error=str(e))
                total_failed += 1

        return {"total_scraped": total_scraped, "total_failed": total_failed}

    def _finalize_scraping_session(self, session_info: Dict[str, Any], metrics: Dict[str, int]):
        """Finalize scraping session and create summary."""
        end_time = datetime.now()
        duration = end_time - session_info["start_time"]

        log_canonical(self.logger, "scrape_session_completed",
                      duration_seconds=int(duration.total_seconds()),
                      total_articles_scraped=metrics["total_scraped"],
                      total_sections_failed=metrics["total_failed"])

        summary = {
            "scraping_session": {
                "start_time": session_info["start_time"].isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration.total_seconds(),
                "total_articles_scraped": metrics["total_scraped"],
                "total_sections_failed": metrics["total_failed"]
            },
            "sections": {}
        }

        for section_key, section_info in self.sections.items():
            section_dir = self.output_dir / section_info['directory']
            md_files = list(section_dir.glob("*.md"))
            summary["sections"][section_key] = {
                "name": section_info['name'],
                "url": section_info['url'],
                "articles_scraped": len(md_files),
                "directory": section_info['directory']
            }

        summary_file = self.output_dir / "scraping_summary.json"
        save_json_file(summary, summary_file)

        log_canonical(self.logger, "summary_created",
                      summary_file=str(summary_file))

    def scrape_all_sections(self):
        """Scrape all sections."""
        session_info = self._initialize_scraping_session()
        metrics = self._process_all_sections()
        self._finalize_scraping_session(session_info, metrics)


if __name__ == "__main__":
    scraper = DominicanCultureScraperV2()
    scraper.scrape_all_sections()
