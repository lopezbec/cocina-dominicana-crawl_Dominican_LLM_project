import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from firecrawl import Firecrawl

from dominican_llm_scraper.utils import LogContext, create_safe_filename, log_canonical


class Crawler:
    def __init__(self, config: Any = None):
        """Initialize crawler with optional config.

        Args:
            config: Optional SiteConfig. If None, uses global config for common settings.
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.api_url = os.getenv("FIRECRAWL_API_URL", "http://localhost:3002")
        self.firecrawl = Firecrawl(api_url=self.api_url)
        log_canonical(
            self.logger,
            "firecrawl_initialized",
            api_url=self.api_url,
        )

        self._create_output_directories()

    def _create_output_directories(self):
        """Create output directories for scraped content."""
        if self.config:
            output_dir_name = self.config.get("output_dir", "data/raw")
        else:
            output_dir_name = "data/raw"

        self.output_dir = Path(output_dir_name)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def scrape_with_retry(
        self,
        url: str,
        max_retries: Optional[int] = None,
        base_delay: Optional[int] = None,
    ) -> Optional[object]:
        """Scrape URL with exponential backoff retry logic."""
        _max_retries = (
            max_retries
            if max_retries is not None
            else (self.config.crawler.get("max_retries", 3) if self.config else 3)
        )
        _base_delay = (
            base_delay
            if base_delay is not None
            else (self.config.crawler.get("base_retry_delay", 2) if self.config else 2)
        )

        for attempt in range(_max_retries):
            try:
                doc = self.firecrawl.scrape(url, formats=["markdown"])
                log_canonical(
                    self.logger,
                    "scrape_success",
                    url=url,
                    attempt=attempt + 1,
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

                if attempt < _max_retries - 1:
                    time.sleep(_base_delay)

        log_canonical(
            self.logger,
            "scrape_failed",
            url=url,
            max_retries=_max_retries,
        )
        return None

    def _is_valid_url(self, url: str, base_url: Optional[str] = None) -> bool:
        """Simple validation to detect malformed URLs.

        Args:
            url: URL to validate
            base_url: Optional base URL for domain checking
        """
        # Check 1: No trailing )
        if url.endswith(")"):
            return False

        # Check 2: Path must not contain the domain (if base_url provided)
        if base_url:
            path = url.replace(base_url, "")
            parsed = urlparse(base_url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]

            if domain in path:
                return False

        return True

    def _extract_urls_from_markdown(
        self, markdown_content: str, base_url: str, source_url: str = "unknown"
    ) -> Set[str]:
        """Extract URLs from markdown content with detailed tracking of source and context.

        Args:
            markdown_content: Markdown content to extract URLs from
            base_url: Base URL for the domain
            source_url: Source URL for tracking
        """
        # Get patterns from config if available, otherwise generate from base_url
        if self.config and self.config.get("_auto_url_patterns"):
            patterns = self.config.get("_auto_url_patterns", [])
        else:
            patterns = [
                rf"\]({re.escape(base_url)}/([^)]+))\)",
                rf"\(({re.escape(base_url)}/([^)]+))\)",
            ]

        all_urls = set()
        malformed_urls = []

        for pattern_index, pattern in enumerate(patterns, 1):
            matches = re.findall(pattern, markdown_content)
            for match in matches:
                # Extract URL from match (handle both tuple and string)
                url = match[0] if isinstance(match, tuple) else match

                # VALIDATION - LOG WITH DETAILED TRACKING
                if not self._is_valid_url(url, base_url):
                    log_canonical(
                        self.logger,
                        "malformed_url_detected",
                        url=url,
                        source_url=source_url,
                        pattern_index=pattern_index,
                    )
                    malformed_urls.append(url)

                    # Detailed log file with full context
                    malformed_log = Path("malformed_urls_detailed.log")
                    with open(malformed_log, "a", encoding="utf-8") as f:
                        f.write(f"{'=' * 80}\n")
                        f.write(f"TIMESTAMP: {datetime.now().isoformat()}\n")
                        f.write(f"MALFORMED_URL: {url}\n")
                        f.write(f"SOURCE_URL: {source_url}\n")
                        f.write(f"PATTERN_INDEX: {pattern_index}\n")
                        f.write(f"PATTERN: {pattern}\n")
                        f.write(f"MATCH: {match}\n")

                        # Find and show context around the URL
                        url_index = markdown_content.find(url)
                        if url_index != -1:
                            context_start = max(0, url_index - 100)
                            context_end = min(len(markdown_content), url_index + len(url) + 100)
                            context = markdown_content[context_start:context_end]
                            f.write(f"CONTEXT:\n{context}\n")
                        else:
                            f.write("CONTEXT: URL not found in markdown content (may have been constructed)\n")

                        f.write(f"{'=' * 80}\n\n")

                    # Simple log for backward compatibility
                    simple_log = Path("malformed_urls.log")
                    with open(simple_log, "a", encoding="utf-8") as f:
                        f.write(f"{url}\n")

                all_urls.add(url)  # Still add it - we're just observing

        if malformed_urls:
            log_canonical(
                self.logger,
                "url_extraction_summary",
                source_url=source_url,
                total_urls=len(all_urls),
                malformed_count=len(malformed_urls),
            )

        # Save full markdown source for inspection
        if malformed_urls:
            source_dir = Path("markdown_sources")
            source_dir.mkdir(exist_ok=True)

            # Create safe filename from source URL
            safe_source_name = source_url.replace("https://", "").replace("http://", "").replace("/", "_")
            safe_source_name = re.sub(r"[^\w\-_.]", "_", safe_source_name)
            source_file = source_dir / f"{safe_source_name}.md"

            with open(source_file, "w", encoding="utf-8") as f:
                f.write(f"# Source URL: {source_url}\n")
                f.write(f"# Extracted at: {datetime.now().isoformat()}\n")
                f.write(f"# Total URLs found: {len(all_urls)}\n")
                f.write(f"# Malformed URLs found: {len(malformed_urls)}\n")
                f.write(f"\n{'=' * 80}\n\n")
                f.write(markdown_content)

        return all_urls

    def _matches_pattern(self, url: str, patterns: List[str]) -> bool:
        """Check if URL matches any of the given regex patterns."""
        for pattern in patterns:
            if re.search(pattern, url):
                return True
        return False

    def _filter_urls_by_config(self, urls: Set[str]) -> List[str]:
        """Filter URLs based on config include/exclude patterns."""
        if not self.config:
            return sorted(urls)

        filters = self.config.filters.to_dict() if hasattr(self.config, "filters") else {}
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

    def _filter_valid_article_urls(self, urls: Set[str], section_url: str, base_url: str) -> List[str]:
        """Filter URLs to keep only valid article URLs."""
        valid_urls = []
        for url in urls:
            url_path = url.replace(base_url + "/", "")

            should_exclude = False

            if url.endswith((".jpg", ".png", ".gif", ".jpeg")):
                should_exclude = True
            elif "#" in url:
                should_exclude = True
            elif url == section_url:
                should_exclude = True

            # Apply config filters if available
            if self.config:
                filters = self.config.filters.to_dict() if hasattr(self.config, "filters") else {}
                exclude_patterns = filters.get("exclude_patterns", [])
                if exclude_patterns and self._matches_pattern(url, exclude_patterns):
                    should_exclude = True

            if not should_exclude and url_path:
                valid_urls.append(url)

        return sorted(valid_urls)

    def discover_article_urls(self, section_url: str, base_url: str) -> List[str]:
        """Discover article URLs from a section page.

        Args:
            section_url: URL of the section page to discover from
            base_url: Base URL for the domain
        """
        log_canonical(self.logger, "url_discovery_started", section_url=section_url)

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
        all_urls = self._extract_urls_from_markdown(markdown_content, base_url, source_url=section_url)
        article_urls = self._filter_valid_article_urls(all_urls, section_url, base_url)

        log_canonical(
            self.logger,
            "url_discovery_completed",
            section_url=section_url,
            urls_found=len(article_urls),
        )
        return article_urls

    def auto_discover_urls(self, page_url: str, base_url: str, use_config_filters: bool = True) -> List[str]:
        """Automatically discover URLs from a page.

        Args:
            page_url: URL to discover links from
            base_url: Base URL for the domain
            use_config_filters: Whether to apply config-based filtering
        """
        log_canonical(self.logger, "auto_discovery_started", page_url=page_url)

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
        all_urls = self._extract_urls_from_markdown(markdown_content, base_url, source_url=page_url)

        if use_config_filters:
            discovered_urls = self._filter_urls_by_config(all_urls)
        else:
            discovered_urls = sorted(all_urls)

        log_canonical(
            self.logger,
            "auto_discovery_completed",
            page_url=page_url,
            urls_found=len(discovered_urls),
        )
        return discovered_urls

    def _extract_article_metadata(self, doc) -> Dict[str, str]:
        """Extract metadata from scraped document."""
        title = "Unknown Title"
        description = ""

        if hasattr(doc, "metadata"):
            metadata = getattr(doc, "metadata")
            if metadata:
                title = getattr(metadata, "title", "Unknown Title")
                description = getattr(metadata, "description", "")

        return {"title": title, "description": description}

    def scrape_article(self, url: str) -> Optional[Dict]:
        """Scrape a single article and return its data."""
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
            log_canonical(self.logger, "article_scrape_failed", url=url, reason="no_content")
            return None

        markdown_content = getattr(doc, "markdown")
        metadata = self._extract_article_metadata(doc)

        # Extract domain from URL
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]

        base_url = f"{parsed.scheme}://{parsed.netloc}"
        url_slug = url.replace(base_url + "/", "").replace("/", "_")
        word_count = len(markdown_content.split())
        char_count = len(markdown_content)

        article_data = {
            "title": metadata["title"],
            "description": metadata["description"],
            "url": url,
            "url_slug": url_slug,
            "domain": domain,
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
        )
        return article_data

    def _get_next_doc_id(self) -> str:
        """Get next available document ID."""
        metadata_file = self.output_dir / "metadata.jsonl"
        if not metadata_file.exists():
            return "0001"

        with open(metadata_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                last_meta = json.loads(lines[-1])
                last_id = int(last_meta["doc_id"])
                return f"{last_id + 1:04d}"
        return "0001"

    def save_article(self, article_data: Dict, category: Optional[str] = None):
        """Save scraped article to disk."""
        if not article_data:
            return

        doc_id = self._get_next_doc_id()
        safe_filename = create_safe_filename(article_data["url_slug"])

        # Use domain from article_data
        domain_slug = article_data["domain"].replace(".", "_")
        content_filename = f"{doc_id}_{domain_slug}_{safe_filename}.md"
        content_file = self.output_dir / content_filename

        with open(content_file, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write(f"doc_id: {doc_id}\n")
            f.write(f"domain: {article_data['domain']}\n")
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
        with open(metadata_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(metadata) + "\n")

        log_canonical(
            self.logger,
            "article_save_completed",
            file_name=content_file.name,
        )

    def _check_existing_file(self, url: str) -> bool:
        """Check if URL has already been scraped."""
        metadata_file = self.output_dir / "metadata.jsonl"
        if not metadata_file.exists():
            return False

        with open(metadata_file, "r", encoding="utf-8") as f:
            for line in f:
                metadata = json.loads(line)
                if metadata.get("url") == url:
                    return True
        return False

    def _process_article_batch(
        self,
        article_urls: List[str],
        category: Optional[str] = None,
        skip_existing: Optional[bool] = None,
    ) -> Dict[str, int]:
        """Process a batch of article URLs.

        Args:
            article_urls: List of URLs to scrape
            category: Optional category name for articles
            skip_existing: Whether to skip already-scraped URLs
        """
        _skip_existing = (
            skip_existing
            if skip_existing is not None
            else (self.config.crawler.get("skip_existing", True) if self.config else True)
        )

        scraped_count = 0
        failed_count = 0
        skipped_count = 0

        delay = self.config.crawler.get("delay_seconds", 5) if self.config else 5

        for i, url in enumerate(article_urls, 1):
            if _skip_existing and self._check_existing_file(url):
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

    def scrape_url(self, url: str, output_directory: str = "custom") -> Optional[Dict]:
        """Scrape a single URL without discovery.

        Args:
            url: URL to scrape
            output_directory: Unused, kept for compatibility
        """
        with LogContext.new_session(session_type="scrape_url", url=url):
            log_canonical(self.logger, "single_url_scrape_started", url=url)

            article_data = self.scrape_article(url)

            if article_data:
                self.save_article(article_data, category=None)
                log_canonical(
                    self.logger,
                    "single_url_scrape_completed",
                    url=url,
                )
                return article_data
            else:
                log_canonical(
                    self.logger,
                    "single_url_scrape_failed",
                    url=url,
                )
                return None

    def crawl_category(
        self,
        category_url: str,
        base_url: str,
        category_name: Optional[str] = None,
        max_depth: Optional[int] = None,
        skip_existing: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Crawl a category URL and scrape all discovered articles.

        Args:
            category_url: URL to start crawling from
            base_url: Base URL for the domain
            category_name: Optional category name
            max_depth: Maximum crawl depth
            skip_existing: Whether to skip already-scraped URLs
        """
        _max_depth = (
            max_depth if max_depth is not None else (self.config.crawler.get("max_depth", 1) if self.config else 1)
        )
        _skip_existing = (
            skip_existing
            if skip_existing is not None
            else (self.config.crawler.get("skip_existing", True) if self.config else True)
        )

        with LogContext.new_session(session_type="crawl_category", category_url=category_url):
            if not category_name:
                parsed_url = urlparse(category_url)
                category_name = parsed_url.path.strip("/").replace("/", "_") or "category"

            safe_category_name = create_safe_filename(category_name)

            log_canonical(
                self.logger,
                "category_crawl_started",
                category_url=category_url,
                category_name=safe_category_name,
                max_depth=_max_depth,
            )

            visited_urls = set()
            all_discovered_urls = []

            discovered_urls = self.auto_discover_urls(category_url, base_url, use_config_filters=True)
            all_discovered_urls.extend(discovered_urls)

            if _max_depth > 1:
                for depth in range(2, _max_depth + 1):
                    new_urls = []
                    for url in discovered_urls:
                        if url not in visited_urls:
                            visited_urls.add(url)
                            deeper_urls = self.auto_discover_urls(url, base_url, use_config_filters=True)
                            new_urls.extend([u for u in deeper_urls if u not in visited_urls])

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
                unique_urls, category=safe_category_name, skip_existing=_skip_existing
            )

            result = {
                "category_name": safe_category_name,
                "category_url": category_url,
                "max_depth": _max_depth,
                "urls_discovered": len(unique_urls),
                "articles_scraped": metrics["scraped"],
                "articles_failed": metrics["failed"],
                "articles_skipped": metrics["skipped"],
            }

            log_canonical(
                self.logger,
                "category_crawl_completed",
                category_name=safe_category_name,
                urls_discovered=len(unique_urls),
                articles_scraped=metrics["scraped"],
            )

            return result
