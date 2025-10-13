#!/usr/bin/env python3
"""
Demo script to test the Dominican Cuisine Scraper with a single article
"""

import os
import sys
from pathlib import Path

# Check if .env exists
if not os.path.exists('.env'):
    print("❌ .env file not found. Please copy .env.example to .env and add your Firecrawl API key.")
    sys.exit(1)

try:
    from config import ScrapingConfig
    from scraper import DominicanCuisineScraper
    
    # Test configuration
    config = ScrapingConfig.from_env()
    config.output_dir = "demo_output"
    config.max_pages_per_section = 1  # Only scrape first page for demo
    
    print("🇩🇴 Dominican Cuisine Scraper Demo")
    print("==================================")
    print(f"Output directory: {config.output_dir}")
    print(f"Rate limit: {config.delay_between_requests} seconds between requests")
    print()
    
    # Initialize scraper
    scraper = DominicanCuisineScraper(config)
    
    # Test with one section
    test_section = "cultura-y-origenes"
    print(f"Testing with section: {test_section}")
    print("This will scrape only the first page to test functionality...")
    print()
    
    # Run the demo
    scraper.scrape_section(test_section)
    
    print()
    print("✅ Demo completed!")
    print(f"Check the '{config.output_dir}' directory for results.")
    print()
    print("If the demo worked, you can run the full scraper with:")
    print("python main.py")
    
except ImportError as e:
    print("❌ Missing dependencies. Please run the installation first:")
    print("./install.sh")
    print(f"Error: {e}")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Demo failed: {e}")
    print("Please check your .env file and ensure your Firecrawl API key is correct.")
    sys.exit(1)