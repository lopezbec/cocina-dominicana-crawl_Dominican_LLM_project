.PHONY: help install install-analysis process compare-pdf test lint tidy

.DEFAULT_GOAL := help

PYTHON := uv run python
UV := uv

help:
	@echo ""
	@echo "  PROCESSOR"
	@echo "    make install                  Install processing dependencies"
	@echo "    make install-analysis         Install notebook dependencies"
	@echo "    make process                  Build plaintext and run deduplication"
	@echo "    make compare-pdf IDS=<ids>    Compare raw and processed files"
	@echo "    make test                     Run processor unit tests"
	@echo "    make lint                     Run Ruff"
	@echo "    make tidy                     Remove local caches and build artifacts"
	@echo ""

install:
	@$(UV) sync

install-analysis:
	@$(UV) sync --extra analysis

process:
	@$(PYTHON) -m dominican_llm_processor process

compare-pdf:
	@if [ -z "$(IDS)" ]; then \
		echo "Error: IDS parameter required"; \
		echo "Usage: make compare-pdf IDS=0002,0080,0809 [OUTPUT=reports/comparison.pdf]"; \
		exit 1; \
	fi
	@$(UV) sync --extra reports
	@$(PYTHON) -m playwright install chromium
	@$(PYTHON) scripts/generate_comparison_pdf.py --ids "$(IDS)" $(if $(OUTPUT),--output "$(OUTPUT)")

test:
	@$(PYTHON) -m pytest

lint:
	@$(PYTHON) -m ruff check src tests scripts experiments

tidy:
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@rm -rf .ruff_cache .pytest_cache build dist *.egg-info
