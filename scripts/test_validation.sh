#!/bin/bash

# Test script for URL validation
# This will scrape one section to test the malformed URL detection

echo "=========================================="
echo "URL Validation Test"
echo "=========================================="
echo ""

# Step 1: Clean up existing data
echo "Step 1: Cleaning up existing data..."
rm -rf scraped_content/
rm -rf scrapped_plain_text/
rm -f malformed_urls.log
echo "✓ Cleaned up"
echo ""

# Step 2: Run scrape on one section
echo "Step 2: Crawling 'Cultura y Orígenes' section..."
echo "This section previously had many malformed URLs"
echo "This will discover and scrape all articles in this section..."
echo ""
CRAWL_DOMAIN=cocinadominicana.com uv run python -m core.cli crawl https://www.cocinadominicana.com/cultura/herencia

echo ""
echo "=========================================="
echo "Test Results"
echo "=========================================="
echo ""

# Step 3: Show results
if [ -f malformed_urls.log ]; then
    MALFORMED_COUNT=$(wc -l < malformed_urls.log)
    echo "✓ Malformed URLs detected: $MALFORMED_COUNT"
    echo ""
    echo "First 10 malformed URLs:"
    head -10 malformed_urls.log
    echo ""
    if [ "$MALFORMED_COUNT" -gt 10 ]; then
        echo "... (see malformed_urls.log for full list)"
    fi
else
    echo "✓ No malformed URLs detected!"
fi

echo ""
if [ -d scraped_content ]; then
    SCRAPED_COUNT=$(find scraped_content -name "*.md" | wc -l)
    echo "✓ Total articles scraped: $SCRAPED_COUNT"
    echo ""
    echo "Sample filenames:"
    ls scraped_content/*.md | head -5
else
    echo "✗ No scraped_content directory found"
fi

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo "1. Review malformed_urls.log to see the problematic URLs"
echo "2. Check scraping.log for detailed logs"
echo "3. Analyze the patterns in malformed URLs"
echo "4. Design fix based on the actual patterns"
echo ""
