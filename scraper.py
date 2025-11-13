"""
Dominican Culture Scraper using Firecrawl
Supports section-based scraping, category crawling, and single URL scraping
"""

from firecrawl import Firecrawl
import os
import re
import time
import yaml
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any, Set
from urllib.parse import urlparse
from dotenv import load_dotenv
from utils import (
    setup_canonical_logger,
    log_canonical,
    PerformanceTimer,
    create_safe_filename,
    save_json_file,
)

load_dotenv()


class Scraper:
    def __init__(self, config_path: str = "config.yaml"):
        self.logger = setup_canonical_logger(__name__)
        self.api_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:3002")
        self.firecrawl = Firecrawl(api_url=self.api_url)
        log_canonical(self.logger, "firecrawl_initialized",
                      api_url=self.api_url)

        self.config = self._load_config(config_path)
        self.base_url = self.config.get(
            "base_url", "https://www.cocinadominicana.com")
        self.sections = self.config.get("sections", {})
        self._create_output_directories()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _create_output_directories(self):
        output_dir_name = self.config.get("output_dir", "scraped_content")
        self.output_dir = Path(output_dir_name)
        self.output_dir.mkdir(exist_ok=True)

    def scrape_with_retry(
        self, url: str, max_retries: int = 3, base_delay: int = 2
    ) -> Optional[object]:
        with PerformanceTimer() as timer:
            for attempt in range(max_retries):
                try:
                    doc = self.firecrawl.scrape(url, formats=["markdown"])
                    log_canonical(
                        self.logger,
                        "scrape_success",
                        url=url,
                        attempt=attempt + 1,
                        duration_ms=timer.duration_ms,
                    )
                    return doc

                except Exception as e:
                    error_msg = str(e)
                    log_canonical(
                        self.logger,
                        "scrape_error",
                        url=url,
                        attempt=attempt + 1,
                        error=error_msg,
                    )

                    if attempt < max_retries - 1:
                        time.sleep(base_delay)

            log_canonical(
                self.logger,
                "scrape_failed",
                url=url,
                max_retries=max_retries,
                duration_ms=timer.duration_ms,
            )
            return None

    def _extract_urls_from_markdown(self, markdown_content: str) -> Set[str]:
        patterns = [
            r"\](https://www\.cocinadominicana\.com/([^)]+))\)",
            r"\((https://www\.cocinadominicana\.com/([^)]+))\)",
        ]

        all_urls = set()
        for pattern in patterns:
            matches = re.findall(pattern, markdown_content)
            for match in matches:
                if isinstance(match, tuple):
                    url = (
                        match[0]
                        if match[0].startswith("http")
                        else f"{self.base_url}/{match[0]}"
                    )
                else:
                    url = (
                        match
                        if match.startswith("http")
                        else f"{self.base_url}/{match}"
                    )
                all_urls.add(url)

        return all_urls

    def _matches_pattern(self, url: str, patterns: List[str]) -> bool:
        for pattern in patterns:
            if re.search(pattern, url):
                return True
        return False

    def _filter_urls_by_config(self, urls: Set[str]) -> List[str]:
        filters = self.config.get("filters", {})
        include_patterns = filters.get("include_patterns", [])
        exclude_patterns = filters.get("exclude_patterns", [])

        valid_urls = []
        for url in urls:
            if exclude_patterns and self._matches_pattern(url, exclude_patterns):
                continue

            if include_patterns and not self._matches_pattern(url, include_patterns):
                continue

            valid_urls.append(url)

        return sorted(valid_urls)

    def _filter_valid_article_urls(self, urls: Set[str], section_url: str) -> List[str]:
        excluded_paths = [
            "cultura/herencia",
            "cultura/tradiciones-costumbres",
            "cultura/celebraciones",
            "cultura/versus",
        ]

        valid_urls = []
        for url in urls:
            url_path = url.replace(self.base_url + "/", "")

            if (
                not url.endswith((".jpg", ".png", ".gif", ".jpeg"))
                and "/cultura/" not in url
                and "#" not in url
                and "dominicancooking.com" not in url
                and "wp-content" not in url
                and url_path
                and url_path not in excluded_paths
                and url != section_url
            ):
                valid_urls.append(url)

        return sorted(valid_urls)

    def discover_article_urls(self, section_url: str) -> List[str]:
        with PerformanceTimer() as timer:
            log_canonical(self.logger, "url_discovery_started",
                          section_url=section_url)

            doc = self.scrape_with_retry(section_url)
            if not doc:
                log_canonical(
                    self.logger,
                    "url_discovery_failed",
                    section_url=section_url,
                    reason="scrape_failed",
                )
                return []

            if not hasattr(doc, "markdown") or not getattr(doc, "markdown", None):
                log_canonical(
                    self.logger,
                    "url_discovery_failed",
                    section_url=section_url,
                    reason="no_markdown",
                )
                return []

            markdown_content = getattr(doc, "markdown")
            all_urls = self._extract_urls_from_markdown(markdown_content)
            article_urls = self._filter_valid_article_urls(
                all_urls, section_url)

            log_canonical(
                self.logger,
                "url_discovery_completed",
                section_url=section_url,
                urls_found=len(article_urls),
                duration_ms=timer.duration_ms,
            )
            return article_urls

    def auto_discover_urls(
        self, page_url: str, use_config_filters: bool = True
    ) -> List[str]:
        with PerformanceTimer() as timer:
            log_canonical(self.logger, "auto_discovery_started",
                          page_url=page_url)

            doc = self.scrape_with_retry(page_url)
            if not doc:
                log_canonical(
                    self.logger,
                    "auto_discovery_failed",
                    page_url=page_url,
                    reason="scrape_failed",
                )
                return []

            if not hasattr(doc, "markdown") or not getattr(doc, "markdown", None):
                log_canonical(
                    self.logger,
                    "auto_discovery_failed",
                    page_url=page_url,
                    reason="no_markdown",
                )
                return []

            markdown_content = getattr(doc, "markdown")
            all_urls = self._extract_urls_from_markdown(markdown_content)

            if use_config_filters:
                discovered_urls = self._filter_urls_by_config(all_urls)
            else:
                discovered_urls = sorted(all_urls)

            log_canonical(
                self.logger,
                "auto_discovery_completed",
                page_url=page_url,
                urls_found=len(discovered_urls),
                duration_ms=timer.duration_ms,
            )
            return discovered_urls

    def _extract_article_metadata(self, doc) -> Dict[str, str]:
        title = "Unknown Title"
        description = ""

        if hasattr(doc, "metadata"):
            metadata = getattr(doc, "metadata")
            if metadata:
                title = getattr(metadata, "title", "Unknown Title")
                description = getattr(metadata, "description", "")

        return {"title": title, "description": description}

    def scrape_article(self, url: str) -> Optional[Dict]:
        with PerformanceTimer() as timer:
            log_canonical(self.logger, "article_scrape_started", url=url)

            doc = self.scrape_with_retry(url)
            if not doc:
                log_canonical(
                    self.logger,
                    "article_scrape_failed",
                    url=url,
                    reason="scrape_failed",
                )
                return None

            if not hasattr(doc, "markdown") or not getattr(doc, "markdown", None):
                log_canonical(
                    self.logger, "article_scrape_failed", url=url, reason="no_content"
                )
                return None

            markdown_content = getattr(doc, "markdown")
            metadata = self._extract_article_metadata(doc)

            url_slug = url.replace(self.base_url + "/", "").replace("/", "_")
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
                "content": markdown_content,
            }

            log_canonical(
                self.logger,
                "article_scrape_completed",
                url=url,
                title=metadata["title"],
                word_count=word_count,
                duration_ms=timer.duration_ms,
            )
            return article_data

    def _get_next_doc_id(self) -> str:
        metadata_file = self.output_dir / "metadata.jsonl"
        if not metadata_file.exists():
            return "0001"
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                last_meta = json.loads(lines[-1])
                last_id = int(last_meta['doc_id'])
                return f"{last_id + 1:04d}"
        return "0001"

    def save_article(self, article_data: Dict, category: Optional[str] = None):
        if not article_data:
            return

        with PerformanceTimer() as timer:
            doc_id = self._get_next_doc_id()
            safe_filename = create_safe_filename(article_data["url_slug"])

            content_file = self.output_dir / f"{doc_id}_{safe_filename}.md"
            with open(content_file, "w", encoding="utf-8") as f:
                f.write("---\n")
                f.write(f"doc_id: {doc_id}\n")
                f.write(f'title: "{article_data["title"]}"\n')
                if article_data["description"]:
                    f.write(f'description: "{article_data["description"]}"\n')
                if category:
                    f.write(f"category: {category}\n")
                f.write(f"url: {article_data['url']}\n")
                f.write(f"scraped_at: {article_data['scraped_at']}\n")
                f.write(f"word_count: {article_data['word_count']}\n")
                f.write(f"char_count: {article_data['char_count']}\n")
                f.write("---\n\n")
                f.write(article_data["content"])

            metadata = {k: v for k, v in article_data.items() if k != "content"}
            metadata["doc_id"] = doc_id
            if category:
                metadata["category"] = category
            
            metadata_file = self.output_dir / "metadata.jsonl"
            with open(metadata_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(metadata) + '\n')

            log_canonical(
                self.logger,
                "article_save_completed",
                file_name=content_file.name,
                duration_ms=timer.duration_ms,
            )

    def _check_existing_file(self, url: str) -> bool:
        metadata_file = self.output_dir / "metadata.jsonl"
        if not metadata_file.exists():
            return False
        
        with open(metadata_file, 'r', encoding='utf-8') as f:
            for line in f:
                metadata = json.loads(line)
                if metadata.get('url') == url:
                    return True
        return False

    def _process_article_batch(
        self,
        article_urls: List[str],
        category: Optional[str] = None,
        skip_existing: bool = True,
    ) -> Dict[str, int]:
        scraped_count = 0
        failed_count = 0
        skipped_count = 0

        crawler_config = self.config.get("crawler", {})
        delay = crawler_config.get("delay_seconds", 0.5)

        for i, url in enumerate(article_urls, 1):
            if skip_existing and self._check_existing_file(url):
                log_canonical(
                    self.logger,
                    "article_skipped",
                    url=url,
                    reason="already_exists",
                    progress=f"{i}/{len(article_urls)}",
                )
                skipped_count += 1
                continue

            article_data = self.scrape_article(url)

            if article_data:
                self.save_article(article_data, category)
                scraped_count += 1
            else:
                failed_count += 1

            time.sleep(delay)

        return {
            "scraped": scraped_count,
            "failed": failed_count,
            "skipped": skipped_count,
        }

    def scrape_section(self, section_key: str):
        with PerformanceTimer() as timer:
            section_info = self.sections[section_key]
            log_canonical(
                self.logger,
                "section_processing_started",
                section=section_info["name"],
                section_key=section_key,
            )

            article_urls = self.discover_article_urls(section_info["url"])

            if not article_urls:
                log_canonical(
                    self.logger,
                    "section_processing_failed",
                    section=section_info["name"],
                    reason="no_articles",
                )
                return

            metrics = self._process_article_batch(
                article_urls, category=section_info["name"]
            )

            log_canonical(
                self.logger,
                "section_processing_completed",
                section=section_info["name"],
                articles_scraped=metrics["scraped"],
                articles_failed=metrics["failed"],
                articles_skipped=metrics["skipped"],
                total_articles=len(article_urls),
                duration_ms=timer.duration_ms,
            )

    def scrape_url(self, url: str, output_directory: str = "custom") -> Optional[Dict]:
        with PerformanceTimer() as timer:
            log_canonical(self.logger, "single_url_scrape_started", url=url)

            article_data = self.scrape_article(url)

            if article_data:
                self.save_article(article_data, category=None)
                log_canonical(
                    self.logger,
                    "single_url_scrape_completed",
                    url=url,
                    duration_ms=timer.duration_ms,
                )
                return article_data
            else:
                log_canonical(
                    self.logger,
                    "single_url_scrape_failed",
                    url=url,
                    duration_ms=timer.duration_ms,
                )
                return None

    def crawl_category(
        self,
        category_url: str,
        category_name: Optional[str] = None,
        max_depth: int = 1,
        skip_existing: bool = True,
    ) -> Dict[str, Any]:
        with PerformanceTimer() as timer:
            if not category_name:
                parsed_url = urlparse(category_url)
                category_name = (
                    parsed_url.path.strip("/").replace("/", "_") or "category"
                )

            safe_category_name = create_safe_filename(category_name)

            log_canonical(
                self.logger,
                "category_crawl_started",
                category_url=category_url,
                category_name=safe_category_name,
                max_depth=max_depth,
            )

            visited_urls = set()
            all_discovered_urls = []

            discovered_urls = self.auto_discover_urls(
                category_url, use_config_filters=True
            )
            all_discovered_urls.extend(discovered_urls)

            if max_depth > 1:
                for depth in range(2, max_depth + 1):
                    new_urls = []
                    for url in discovered_urls:
                        if url not in visited_urls:
                            visited_urls.add(url)
                            deeper_urls = self.auto_discover_urls(
                                url, use_config_filters=True
                            )
                            new_urls.extend(
                                [u for u in deeper_urls if u not in visited_urls]
                            )

                    all_discovered_urls.extend(new_urls)
                    discovered_urls = new_urls

                    if not new_urls:
                        break

            unique_urls = list(set(all_discovered_urls))

            log_canonical(
                self.logger,
                "category_urls_discovered",
                category_name=safe_category_name,
                total_urls=len(unique_urls),
            )

            metrics = self._process_article_batch(
                unique_urls, category=safe_category_name, skip_existing=skip_existing
            )

            result = {
                "category_name": safe_category_name,
                "category_url": category_url,
                "max_depth": max_depth,
                "urls_discovered": len(unique_urls),
                "articles_scraped": metrics["scraped"],
                "articles_failed": metrics["failed"],
                "articles_skipped": metrics["skipped"],
                "duration_ms": timer.duration_ms,
            }

            log_canonical(
                self.logger,
                "category_crawl_completed",
                category_name=safe_category_name,
                urls_discovered=len(unique_urls),
                articles_scraped=metrics["scraped"],
                duration_ms=timer.duration_ms,
            )

            return result

    def _initialize_scraping_session(self) -> Dict[str, Any]:
        start_time = datetime.now()
        session_info = {
            "start_time": start_time,
            "output_dir": self.output_dir.absolute(),
            "sections_count": len(self.sections),
        }

        log_canonical(
            self.logger,
            "scrape_session_started",
            start_time=start_time.isoformat(),
            output_dir=str(session_info["output_dir"]),
            sections_count=session_info["sections_count"],
        )

        return session_info

    def _process_all_sections(self) -> Dict[str, int]:
        total_scraped = 0
        total_failed = 0

        for section_key in self.sections:
            try:
                self.scrape_section(section_key)

            except Exception as e:
                log_canonical(
                    self.logger, "section_error", section_key=section_key, error=str(e)
                )
                total_failed += 1

        metadata_file = self.output_dir / "metadata.jsonl"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                total_scraped = sum(1 for _ in f)

        return {"total_scraped": total_scraped, "total_failed": total_failed}

    def _finalize_scraping_session(
        self, session_info: Dict[str, Any], metrics: Dict[str, int]
    ):
        end_time = datetime.now()
        duration = end_time - session_info["start_time"]

        log_canonical(
            self.logger,
            "scrape_session_completed",
            duration_seconds=int(duration.total_seconds()),
            total_articles_scraped=metrics["total_scraped"],
            total_sections_failed=metrics["total_failed"],
        )

        category_stats = {}
        metadata_file = self.output_dir / "metadata.jsonl"
        
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                for line in f:
                    metadata = json.loads(line)
                    category = metadata.get('category', 'uncategorized')
                    if category not in category_stats:
                        category_stats[category] = 0
                    category_stats[category] += 1

        summary = {
            "scraping_session": {
                "start_time": session_info["start_time"].isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration.total_seconds(),
                "total_articles_scraped": metrics["total_scraped"],
                "total_sections_failed": metrics["total_failed"],
            },
            "categories": category_stats,
        }

        summary_file = self.output_dir / "corpus_stats.json"
        save_json_file(summary, summary_file)

        log_canonical(self.logger, "summary_created",
                      summary_file=str(summary_file))

    def scrape_all_sections(self):
        session_info = self._initialize_scraping_session()
        metrics = self._process_all_sections()
        self._finalize_scraping_session(session_info, metrics)


if __name__ == "__main__":
    scraper = Scraper()
    scraper.scrape_all_sections()
