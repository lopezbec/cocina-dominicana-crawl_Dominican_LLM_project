.PHONY: help install demo run clean test lint

help:
	@echo "🇩🇴 Dominican Cuisine Cultural Content Scraper"
	@echo "=============================================="
	@echo ""
	@echo "Available commands:"
	@echo "  install     Install dependencies and set up environment"
	@echo "  demo        Run a quick demo with one section"
	@echo "  run         Run the full scraper (all sections)"
	@echo "  run-section Run scraper for specific section"
	@echo "  clean       Clean up generated files"
	@echo "  test        Run basic tests"
	@echo "  lint        Run code quality checks"
	@echo "  help        Show this help message"
	@echo ""
	@echo "Example usage:"
	@echo "  make install"
	@echo "  make demo"
	@echo "  make run"
	@echo "  make run-section SECTION=cultura-y-origenes"

install:
	@echo "📦 Installing Dominican Cuisine Scraper..."
	@chmod +x install.sh
	@./install.sh

demo:
	@echo "🧪 Running demo..."
	@if [ ! -f .env ]; then echo "❌ .env file not found. Run 'make install' first."; exit 1; fi
	@source venv/bin/activate && python demo.py

run:
	@echo "🚀 Running full scraper..."
	@if [ ! -f .env ]; then echo "❌ .env file not found. Run 'make install' first."; exit 1; fi
	@source venv/bin/activate && python main.py

run-section:
	@echo "🎯 Running scraper for section: $(SECTION)"
	@if [ ! -f .env ]; then echo "❌ .env file not found. Run 'make install' first."; exit 1; fi
	@if [ -z "$(SECTION)" ]; then echo "❌ Please specify SECTION. Example: make run-section SECTION=cultura-y-origenes"; exit 1; fi
	@source venv/bin/activate && python main.py --section $(SECTION)

clean:
	@echo "🧹 Cleaning up..."
	@rm -rf topics/
	@rm -rf demo_output/
	@rm -f *.log
	@rm -f progress.json
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

test:
	@echo "🧪 Running basic tests..."
	@if [ ! -d venv ]; then echo "❌ Virtual environment not found. Run 'make install' first."; exit 1; fi
	@source venv/bin/activate && python -c "import config, models, utils; print('✅ All modules import successfully')"

lint:
	@echo "🔍 Running code quality checks..."
	@if [ ! -d venv ]; then echo "❌ Virtual environment not found. Run 'make install' first."; exit 1; fi
	@source venv/bin/activate && python -m py_compile *.py
	@echo "✅ Code quality check passed"