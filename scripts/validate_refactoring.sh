#!/bin/bash
set -e

echo "================================"
echo "Refactoring Validation"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

echo "1. Testing package import..."
if uv run python -c "import dominican_llm_scraper; print(f'Version: {dominican_llm_scraper.__version__}')" 2>/dev/null; then
    success "Package imports correctly"
else
    error "Package import failed"
fi

echo "2. Testing CLI help..."
if uv run python -m dominican_llm_scraper --help > /dev/null 2>&1; then
    success "CLI accessible"
else
    error "CLI not accessible"
fi

echo "3. Testing module imports..."
if uv run python -c "from dominican_llm_scraper.core import Crawler, load_config; print('Imports work')" 2>/dev/null; then
    success "Core imports work"
else
    error "Core imports failed"
fi

echo "4. Testing utils imports..."
if uv run python -c "from dominican_llm_scraper.utils import log_canonical, PerformanceTimer; print('Imports work')" 2>/dev/null; then
    success "Utils imports work"
else
    error "Utils imports failed"
fi

echo "5. Checking directory structure..."
[ -d "src/dominican_llm_scraper" ] && success "src/ structure exists" || error "src/ structure missing"
[ -d "config/sites" ] && success "config/sites exists" || error "config/sites missing"
[ -d "data/raw" ] && success "data/raw exists" || error "data/raw missing"
[ -d "data/logs" ] && success "data/logs exists" || error "data/logs missing"

echo "6. Checking configuration files..."
[ -f "pyproject.toml" ] && success "pyproject.toml exists" || error "pyproject.toml missing"
[ -f "config/config.yml" ] && success "config/config.yml exists" || error "config/config.yml missing"
[ -f ".gitignore" ] && success ".gitignore exists" || error ".gitignore missing"

echo "7. Checking entry points..."
[ -f "src/dominican_llm_scraper/__main__.py" ] && success "__main__.py exists" || error "__main__.py missing"
[ -f "src/dominican_llm_scraper/__init__.py" ] && success "__init__.py exists" || error "__init__.py missing"

echo "8. Checking package metadata..."
if grep -q "dominican-llm-scraper" pyproject.toml && grep -q "0.2.0" pyproject.toml; then
    success "Package metadata updated"
else
    error "Package metadata not updated"
fi

echo "9. Checking old directories removed..."
if [ ! -d "core" ] || [ "$(ls -A core 2>/dev/null)" ]; then
    echo "  ⚠ Warning: Old core/ directory still exists"
else
    success "Old core/ directory removed"
fi

if [ ! -f "utils.py" ]; then
    success "Old utils.py removed"
else
    echo "  ⚠ Warning: Old utils.py still exists"
fi

echo ""
echo "================================"
echo -e "${GREEN}✓ All validations passed!${NC}"
echo "================================"
echo ""
echo "Next steps:"
echo "  1. Run: uv run python -m dominican_llm_scraper --help"
echo "  2. Test a command: CRAWL_DOMAIN=<domain> uv run python -m dominican_llm_scraper scrape-all"
echo "  3. Review docs/MIGRATION.md for more details"
echo ""
