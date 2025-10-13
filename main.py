#!/usr/bin/env python3
"""
Dominican Cuisine Cultural Content Scraper
A comprehensive web scraper for cocinadominicana.com cultural articles.
"""

import argparse
import sys
from pathlib import Path

from config import ScrapingConfig, SECTIONS
from scraper import DominicanCuisineScraper
from utils import setup_logging

def main():
    parser = argparse.ArgumentParser(
        description="Scrape Dominican cuisine cultural content from cocinadominicana.com"
    )
    parser.add_argument(
        "--section",
        choices=list(SECTIONS.keys()) + ["all"],
        default="all",
        help="Section to scrape (default: all)"
    )
    parser.add_argument(
        "--output-dir",
        default="topics",
        help="Output directory for scraped content"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between requests in seconds"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=50,
        help="Maximum pages to scrape per section"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous incomplete scraping session"
    )

    args = parser.parse_args()

    logger = setup_logging(args.log_level)

    try:
        config = ScrapingConfig.from_env()
        config.output_dir = args.output_dir
        config.delay_between_requests = args.delay
        config.max_pages_per_section = args.max_pages

        scraper = DominicanCuisineScraper(config)

        if args.section == "all":
            scraper.scrape_all_sections()
        else:
            scraper.scrape_section(args.section)

        logger.info("Scraping completed successfully!")

    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()