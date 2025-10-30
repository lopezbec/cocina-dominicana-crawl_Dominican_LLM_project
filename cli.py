#!/usr/bin/env python3
"""
Command-line interface for Dominican Culture Scraper
Provides flexible scraping options: single URL, category crawl, batch scraping, and section-based scraping
"""

import argparse
import sys
from pathlib import Path
from typing import List
from scraper import Scraper
from utils import setup_canonical_logger, log_canonical


def scrape_single_url(args):
    logger = setup_canonical_logger(__name__)
    log_canonical(logger, "cli_scrape_url_started", url=args.url)
    
    scraper = Scraper(config_path=args.config)
    
    output_dir = args.output or "custom"
    result = scraper.scrape_url(args.url, output_directory=output_dir)
    
    if result:
        print(f"\nSuccessfully scraped: {args.url}")
        print(f"Title: {result['title']}")
        print(f"Word count: {result['word_count']}")
        print(f"Saved to: {scraper.output_dir / output_dir}")
        log_canonical(logger, "cli_scrape_url_success", url=args.url)
        return 0
    else:
        print(f"\nFailed to scrape: {args.url}")
        log_canonical(logger, "cli_scrape_url_failed", url=args.url)
        return 1


def crawl_category(args):
    logger = setup_canonical_logger(__name__)
    log_canonical(logger, "cli_crawl_started", url=args.url, depth=args.depth)
    
    scraper = Scraper(config_path=args.config)
    
    result = scraper.crawl_category(
        category_url=args.url,
        category_name=args.name,
        max_depth=args.depth,
        skip_existing=not args.no_skip
    )
    
    print(f"\nCategory crawl completed: {result['category_name']}")
    print(f"URLs discovered: {result['urls_discovered']}")
    print(f"Articles scraped: {result['articles_scraped']}")
    print(f"Articles skipped: {result['articles_skipped']}")
    print(f"Articles failed: {result['articles_failed']}")
    print(f"Duration: {result['duration_ms'] / 1000:.2f}s")
    print(f"Saved to: {scraper.output_dir / result['category_name']}")
    
    log_canonical(logger, "cli_crawl_completed", 
                  category=result['category_name'],
                  urls_discovered=result['urls_discovered'],
                  articles_scraped=result['articles_scraped'])
    
    return 0


def scrape_list(args):
    logger = setup_canonical_logger(__name__)
    
    urls_file = Path(args.file)
    if not urls_file.exists():
        print(f"Error: File not found: {args.file}")
        return 1
    
    with open(urls_file, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    if not urls:
        print(f"Error: No URLs found in {args.file}")
        return 1
    
    log_canonical(logger, "cli_scrape_list_started", file=args.file, url_count=len(urls))
    
    scraper = Scraper(config_path=args.config)
    output_dir = args.output or "batch"
    
    success_count = 0
    failed_count = 0
    
    print(f"\nScraping {len(urls)} URLs from {args.file}...")
    
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Scraping: {url}")
        result = scraper.scrape_url(url, output_directory=output_dir)
        
        if result:
            print(f"  Success: {result['title']} ({result['word_count']} words)")
            success_count += 1
        else:
            print(f"  Failed to scrape")
            failed_count += 1
    
    print(f"\n\nBatch scraping completed:")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Saved to: {scraper.output_dir / output_dir}")
    
    log_canonical(logger, "cli_scrape_list_completed",
                  total_urls=len(urls),
                  success_count=success_count,
                  failed_count=failed_count)
    
    return 0 if failed_count == 0 else 1


def scrape_all_sections(args):
    logger = setup_canonical_logger(__name__)
    log_canonical(logger, "cli_scrape_all_started")
    
    scraper = Scraper(config_path=args.config)
    scraper.scrape_all_sections()
    
    print("\nAll sections scraped successfully")
    print(f"Results saved to: {scraper.output_dir}")
    
    log_canonical(logger, "cli_scrape_all_completed")
    return 0


def discover_urls(args):
    logger = setup_canonical_logger(__name__)
    log_canonical(logger, "cli_discover_started", url=args.url)
    
    scraper = Scraper(config_path=args.config)
    urls = scraper.auto_discover_urls(args.url, use_config_filters=not args.no_filter)
    
    print(f"\nDiscovered {len(urls)} URLs from {args.url}:\n")
    
    for url in urls:
        print(url)
    
    if args.save:
        output_file = Path(args.save)
        with open(output_file, 'w', encoding='utf-8') as f:
            for url in urls:
                f.write(f"{url}\n")
        print(f"\nURLs saved to: {output_file}")
    
    log_canonical(logger, "cli_discover_completed", url=args.url, urls_found=len(urls))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Dominican Culture Scraper - Flexible web scraping tool using Firecrawl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Scrape a single URL:
    %(prog)s scrape https://www.cocinadominicana.com/batata-asada
  
  Crawl a category with depth 2:
    %(prog)s crawl https://www.cocinadominicana.com/cocina --depth 2 --name cocina
  
  Scrape URLs from a file:
    %(prog)s scrape-list urls.txt --output recipes
  
  Discover URLs without scraping:
    %(prog)s discover https://www.cocinadominicana.com/inicia --save discovered_urls.txt
  
  Scrape all configured sections:
    %(prog)s scrape-all
        """
    )
    
    parser.add_argument(
        '--config',
        default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    scrape_parser = subparsers.add_parser(
        'scrape',
        help='Scrape a single URL'
    )
    scrape_parser.add_argument('url', help='URL to scrape')
    scrape_parser.add_argument(
        '--output',
        help='Output directory name (default: custom)'
    )
    scrape_parser.set_defaults(func=scrape_single_url)
    
    crawl_parser = subparsers.add_parser(
        'crawl',
        help='Crawl a category page and scrape discovered articles'
    )
    crawl_parser.add_argument('url', help='Category URL to crawl')
    crawl_parser.add_argument(
        '--depth',
        type=int,
        default=1,
        help='Maximum crawl depth (default: 1)'
    )
    crawl_parser.add_argument(
        '--name',
        help='Category name for output directory (auto-detected if not provided)'
    )
    crawl_parser.add_argument(
        '--no-skip',
        action='store_true',
        help='Re-scrape existing files instead of skipping them'
    )
    crawl_parser.set_defaults(func=crawl_category)
    
    list_parser = subparsers.add_parser(
        'scrape-list',
        help='Scrape multiple URLs from a file'
    )
    list_parser.add_argument('file', help='File containing URLs (one per line)')
    list_parser.add_argument(
        '--output',
        help='Output directory name (default: batch)'
    )
    list_parser.set_defaults(func=scrape_list)
    
    all_parser = subparsers.add_parser(
        'scrape-all',
        help='Scrape all sections defined in config.yaml'
    )
    all_parser.set_defaults(func=scrape_all_sections)
    
    discover_parser = subparsers.add_parser(
        'discover',
        help='Discover URLs from a page without scraping'
    )
    discover_parser.add_argument('url', help='URL to discover links from')
    discover_parser.add_argument(
        '--save',
        help='Save discovered URLs to file'
    )
    discover_parser.add_argument(
        '--no-filter',
        action='store_true',
        help='Disable config-based URL filtering'
    )
    discover_parser.set_defaults(func=discover_urls)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
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
