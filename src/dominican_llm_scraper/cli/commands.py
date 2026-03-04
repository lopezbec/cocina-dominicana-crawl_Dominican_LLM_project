#!/usr/bin/env python3
import argparse
import yaml
import logging
from pathlib import Path
import sys

from dominican_llm_scraper.core.config_loader import (
    load_config,
    load_urls_config,
    update_url_processed_status,
)
from dominican_llm_scraper.core.crawler import Crawler
from dominican_llm_scraper.utils import log_canonical, setup_logging


def scrape_command(args):
    """Scrape URLs from config or command line arguments."""
    logger = logging.getLogger(__name__)

    # Determine URLs to scrape
    if args.urls:
        # URLs provided as command line arguments
        urls_to_scrape = args.urls
        log_canonical(logger, "scrape_started_from_args", url_count=len(urls_to_scrape))

        # Scrape each URL directly without config
        success_count = 0
        failed_count = 0

        for url in urls_to_scrape:
            print(f"\nScraping: {url}")

            # Load config from URL (preserves protocol)
            config = load_config(url)
            crawler = Crawler(config)

            result = crawler.scrape_url(url)

            if result:
                print(f"  Success: {result['title']} ({result['word_count']} words)")
                success_count += 1
            else:
                print("  Failed to scrape")
                failed_count += 1

        print("\n\nScraping completed:")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {failed_count}")

        log_canonical(
            logger,
            "scrape_completed_from_args",
            success_count=success_count,
            failed_count=failed_count,
        )

        return 0 if failed_count == 0 else 1

    elif args.urls_file:
        # Load URLs from custom file
        urls_file = Path(args.urls_file)
        if not urls_file.exists():
            print(f"Error: File not found: {args.urls_file}")
            return 1


        with open(urls_file, "r", encoding="utf-8") as f:
            urls_config = yaml.safe_load(f)

        urls_entries = urls_config.get("urls", [])
        log_canonical(logger, "scrape_started_from_file", file=args.urls_file, url_count=len(urls_entries))

    else:
        # Load URLs from config/urls.yml
        try:
            urls_entries = load_urls_config()
            log_canonical(logger, "scrape_started_from_config", url_count=len(urls_entries))
        except FileNotFoundError as e:
            print(str(e))
            return 1

    # Filter to unprocessed URLs (only if using config files)
    if not args.urls:
        if args.force:
            # Process all URLs
            urls_to_process = urls_entries
            print(f"\nProcessing all {len(urls_entries)} URLs (--force mode)")
        else:
            # Only process unprocessed URLs
            urls_to_process = [u for u in urls_entries if not u.get("processed", False)]
            processed_count = len(urls_entries) - len(urls_to_process)

            if processed_count > 0:
                print(f"\nSkipping {processed_count} already-processed URLs")

            if not urls_to_process:
                print("\nNo URLs to process (all marked as processed)")
                print("Use --force to reprocess all URLs")
                return 0

            print(f"Processing {len(urls_to_process)} unprocessed URLs")
    else:
        urls_to_process = urls_entries

    # Process each URL entry
    total_discovered = 0
    total_scraped = 0
    total_failed = 0
    total_skipped = 0
    crawler = None  # Initialize crawler variable

    for i, url_entry in enumerate(urls_to_process, 1):
        url = url_entry["url"]
        domain = url_entry["domain"]
        name = url_entry.get("name", "Unknown")
        max_depth = url_entry.get("max_depth", 2)

        print(f"\n{'=' * 70}")
        print(f"[{i}/{len(urls_to_process)}] Processing: {name}")
        print(f"  URL: {url}")
        print(f"  Domain: {domain}")
        print(f"  Max depth: {max_depth}")
        print(f"{'=' * 70}\n")

        # Load config from URL (preserves protocol)
        config = load_config(url)
        crawler = Crawler(config)

        # Crawl with discovery
        result = crawler.crawl_category(
            category_url=url,
            base_url=config.base_url,
            category_name=name,
            max_depth=max_depth,
            skip_existing=True,
        )

        total_discovered += result["urls_discovered"]
        total_scraped += result["articles_scraped"]
        total_failed += result["articles_failed"]
        total_skipped += result["articles_skipped"]

        print(f"\n  URLs discovered: {result['urls_discovered']}")
        print(f"  Articles scraped: {result['articles_scraped']}")
        print(f"  Articles skipped: {result['articles_skipped']}")
        print(f"  Articles failed: {result['articles_failed']}")

        # Mark URL as processed (if using config file and not --no-update)
        if not args.urls and not args.no_update:
            update_url_processed_status(url, processed=True)
            print("  ✓ Marked as processed in config/urls.yml")

    # Final summary
    print(f"\n{'=' * 70}")
    print("SCRAPING SESSION COMPLETED")
    print(f"{'=' * 70}")
    print(f"  URLs processed: {len(urls_to_process)}")
    print(f"  Total URLs discovered: {total_discovered}")
    print(f"  Total articles scraped: {total_scraped}")
    print(f"  Total articles skipped: {total_skipped}")
    print(f"  Total articles failed: {total_failed}")
    if crawler:
        print(f"  Output directory: {crawler.output_dir}")
    print(f"{'=' * 70}\n")

    log_canonical(
        logger,
        "scrape_session_completed",
        urls_processed=len(urls_to_process),
        total_discovered=total_discovered,
        total_scraped=total_scraped,
        total_skipped=total_skipped,
        total_failed=total_failed,
    )

    return 0 if total_failed == 0 else 1


def process_to_plaintext(args):
    """Process scraped markdown to plaintext."""
    from dominican_llm_scraper.core.processor import process_all_files
    from dominican_llm_scraper.core.config_loader import load_config

    # Load global config for processing settings
    config = load_config()

    input_dir = Path(args.input) if args.input else Path(config.get("output_dir", "data/raw"))
    output_dir = Path(args.output) if args.output else Path(config.get("plaintext_output_dir", "data/processed"))

    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist")
        print("Run scraping command first to generate content")
        return 1

    print("Processing content to plaintext")
    print(f"Input: {input_dir}")
    print(f"Output: {output_dir}\n")

    # Processing patterns are now in global config
    process_all_files(input_dir, output_dir, config, processing_patterns=None)
    return 0


def main():
    # Initialize logging FIRST, before any other imports or operations
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Multi-Domain Web Scraper using Firecrawl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Scrape all unprocessed URLs from config/urls.yml:
    %(prog)s scrape

  Scrape specific URLs:
    %(prog)s scrape https://example.com/page1 https://example.com/page2

  Scrape from custom URLs file:
    %(prog)s scrape --urls-file custom_urls.yml

  Force reprocess all URLs:
    %(prog)s scrape --force

  Process to plaintext:
    %(prog)s process
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape URLs with discovery")
    scrape_parser.add_argument("urls", nargs="*", help="URLs to scrape (bypasses config/urls.yml)")
    scrape_parser.add_argument("--urls-file", help="Custom URLs file (YAML format)")
    scrape_parser.add_argument("--force", action="store_true", help="Reprocess already-processed URLs")
    scrape_parser.add_argument("--no-update", action="store_true", help="Don't update processed status in config")
    scrape_parser.set_defaults(func=scrape_command)

    # Process command
    process_parser = subparsers.add_parser("process", help="Process scraped markdown to plain text")
    process_parser.add_argument("--input", help="Input directory (default: from config)")
    process_parser.add_argument("--output", help="Output directory (default: from config)")
    process_parser.set_defaults(func=process_to_plaintext)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        return args.func(args)

    except ValueError as e:
        print(str(e))
        return 1
    except FileNotFoundError as e:
        print(str(e))
        return 1
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
