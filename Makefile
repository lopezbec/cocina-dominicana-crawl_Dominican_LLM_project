.PHONY: help setup install firecrawl-start firecrawl-stop firecrawl-restart \
        firecrawl-status firecrawl-logs firecrawl-test scrape scrape-url \
        scrape-force process compare-pdf sync clean tidy

.DEFAULT_GOAL := help

# Variables
PYTHON := uv run python
UV := uv
FIRECRAWL_DIR := firecrawl
DOCKER_COMPOSE := docker compose
UNISON := unison

help:
	@echo ""
	@echo "  ╔═════════════════════════════════════════════════════════════════════════════════════════════════╗"
	@echo "  ║                                                                                                 ║"
	@echo "  ║                                                                                                 ║"
	@echo "  ║                                                                                                 ║"
	@echo "  ║     ██╗     ██╗     ███╗   ███╗    ███████╗ ██████╗██████╗  █████╗ ██████╗ ███████╗██████╗      ║"
	@echo "  ║     ██║     ██║     ████╗ ████║    ██╔════╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗     ║"
	@echo "  ║     ██║     ██║     ██╔████╔██║    ███████╗██║     ██████╔╝███████║██████╔╝█████╗  ██████╔╝     ║"
	@echo "  ║     ██║     ██║     ██║╚██╔╝██║    ╚════██║██║     ██╔══██╗██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗     ║"
	@echo "  ║     ███████╗███████╗██║ ╚═╝ ██║    ███████║╚██████╗██║  ██║██║  ██║██║     ███████╗██║  ██║     ║"
	@echo "  ║     ╚══════╝╚══════╝╚═╝     ╚═╝    ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝     ║"
	@echo "  ║                                                                                                 ║"
	@echo "  ║                                                                                                 ║"
	@echo "  ╚═════════════════════════════════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  SETUP"
	@echo "    make setup                    First-time setup (install + start firecrawl)"
	@echo "    make install                  Install Python dependencies"
	@echo ""
	@echo "  FIRECRAWL"
	@echo "    make firecrawl-start          Start Firecrawl services"
	@echo "    make firecrawl-stop           Stop Firecrawl services"
	@echo "    make firecrawl-restart        Restart services"
	@echo "    make firecrawl-status         Show service status"
	@echo "    make firecrawl-logs           Follow API logs"
	@echo "    make firecrawl-test           Test Firecrawl endpoint"
	@echo ""
	@echo "  SCRAPING"
	@echo "    make scrape                   Scrape unprocessed URLs from config/urls.yml"
	@echo "    make scrape-url URL=<url>     Scrape specific URL"
	@echo "    make scrape-force             Reprocess all URLs (ignore processed status)"
	@echo ""
	@echo "  PROCESSING"
	@echo "    make process                  Convert markdown to plaintext"
	@echo "    make compare-pdf IDS=<ids>    Create raw vs processed PDF report"
	@echo ""
	@echo "  SYNC"
	@echo "    make sync                     Bidirectional sync with remote server"
	@echo ""
	@echo "  CLEANUP"
	@echo "    make clean                    Remove Firecrawl containers and volumes"
	@echo "    make tidy                     Remove Python cache/build/run artifacts"
	@echo ""
	@echo "  DIRECT CLI USAGE"
	@echo "    uv run python -m dominican_llm_scraper scrape [urls...]"
	@echo "    uv run python -m dominican_llm_scraper scrape --urls-file <file>"
	@echo "    uv run python -m dominican_llm_scraper process"
	@echo ""

# Setup Commands
setup: install firecrawl-start
	@echo ""
	@echo "✓ Setup complete"
	@echo "  Next steps:"
	@echo "    make firecrawl-test    - Verify Firecrawl"
	@echo "    make scrape            - Start scraping"
	@echo ""

install:
	@if ! command -v uv > /dev/null 2>&1; then \
		echo ""; \
		echo "Error: uv not found"; \
		echo "Install from: https://docs.astral.sh/uv/"; \
		echo ""; \
		exit 1; \
	fi
	@if [ ! -f pyproject.toml ]; then \
		echo ""; \
		echo "Error: pyproject.toml not found"; \
		echo "Run from project root directory"; \
		echo ""; \
		exit 1; \
	fi
	@echo ""
	@echo "Installing Python dependencies..."
	@$(UV) sync
	@echo "✓ Dependencies installed"
	@echo ""

# Firecrawl Management
firecrawl-start:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo ""; \
		echo "Error: Firecrawl directory not found at $(FIRECRAWL_DIR)/"; \
		echo "Ensure firecrawl/ exists with docker-compose.yml"; \
		echo ""; \
		exit 1; \
	fi
	@echo "Starting Firecrawl services..."
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) up -d
	@echo "✓ Firecrawl started at http://localhost:3002"
	@echo "  Run 'make firecrawl-test' to verify endpoint"

firecrawl-stop:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found"; \
		exit 1; \
	fi
	@echo "Stopping Firecrawl services..."
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) stop
	@echo "✓ Services stopped"

firecrawl-restart:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found"; \
		exit 1; \
	fi
	@echo "Restarting Firecrawl services..."
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) restart
	@echo "✓ Services restarted"

firecrawl-status:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found"; \
		exit 1; \
	fi
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) ps

firecrawl-logs:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found"; \
		exit 1; \
	fi
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) logs -f api

firecrawl-test:
	@echo ""
	@echo "Testing Firecrawl endpoint..."
	@echo "────────────────────────────────────────────────────────────"
	@echo ""
	@curl -s http://localhost:3002/v2/scrape \
		-H 'Content-Type: application/json' \
		-d '{"url": "https://example.com", "formats": ["markdown"]}' \
		| $(PYTHON) -m json.tool || echo "Error: Firecrawl not responding. Run 'make firecrawl-start'"
	@echo ""

# Scraping Commands
scrape:
	@$(PYTHON) -m dominican_llm_scraper scrape

scrape-url:
	@if [ -z "$(URL)" ]; then \
		echo ""; \
		echo "Error: URL parameter required"; \
		echo "Usage: make scrape-url URL=https://example.com/page"; \
		echo ""; \
		exit 1; \
	fi
	@$(PYTHON) -m dominican_llm_scraper scrape "$(URL)"

scrape-force:
	@$(PYTHON) -m dominican_llm_scraper scrape --force

# Processing Commands
process:
	@$(PYTHON) -m dominican_llm_scraper process

compare-pdf:
	@if [ -z "$(IDS)" ]; then \
		echo ""; \
		echo "Error: IDS parameter required"; \
		echo "Usage: make compare-pdf IDS=0002,0080,0809 [OUTPUT=reports/comparison.pdf]"; \
		echo ""; \
		exit 1; \
	fi
	@$(UV) sync
	@$(PYTHON) -m playwright install chromium
	@$(PYTHON) scripts/generate_comparison_pdf.py --ids "$(IDS)" $(if $(OUTPUT),--output "$(OUTPUT)")

# Synchronization
sync:
	@if [ ! -f .env ]; then \
		echo "Error: .env not found"; \
		echo "Required variables: SYNC_REMOTE_USER, SYNC_REMOTE_HOST, SYNC_REMOTE_DIR, SYNC_REMOTE_PASSWORD"; \
		exit 1; \
	fi
	@set -a; . ./.env; set +a; \
	for var in SYNC_REMOTE_USER SYNC_REMOTE_HOST SYNC_REMOTE_DIR SYNC_REMOTE_PASSWORD; do \
		eval "value=\$$$$var"; \
		if [ -z "$$value" ]; then \
			echo "Error: $$var is required in .env"; \
			exit 1; \
		fi; \
	done; \
	if ! command -v sshpass > /dev/null 2>&1; then \
		echo "Error: sshpass not found"; \
		echo "Install it locally before running make sync"; \
		exit 1; \
	fi; \
	if ! command -v $(UNISON) > /dev/null 2>&1; then \
		echo "Error: $(UNISON) not found"; \
		echo "Install unison locally before running make sync"; \
		exit 1; \
	fi; \
	echo "Creating remote directory $$SYNC_REMOTE_USER@$$SYNC_REMOTE_HOST:$$SYNC_REMOTE_DIR"; \
	SSHPASS="$$SYNC_REMOTE_PASSWORD" sshpass -e ssh \
		-o StrictHostKeyChecking=accept-new \
		-o PreferredAuthentications=password \
		-o PubkeyAuthentication=no \
		"$$SYNC_REMOTE_USER@$$SYNC_REMOTE_HOST" \
		"mkdir -p \"$$SYNC_REMOTE_DIR\" && command -v unison > /dev/null 2>&1 || { echo 'Error: unison not found on remote server'; exit 127; }"; \
	echo "Synchronizing selected project paths"; \
	SYNC_SSH_WRAPPER="$$(mktemp /tmp/fondocyt-sync-ssh.XXXXXX)"; \
	printf '%s\n' '#!/bin/sh' 'exec sshpass -e ssh "$$@"' > "$$SYNC_SSH_WRAPPER"; \
	chmod 700 "$$SYNC_SSH_WRAPPER"; \
	SSHPASS="$$SYNC_REMOTE_PASSWORD" $(UNISON) "$(CURDIR)" "ssh://$$SYNC_REMOTE_USER@$$SYNC_REMOTE_HOST/$$SYNC_REMOTE_DIR" \
		-auto \
		-batch \
		-times \
		-perms 0 \
		-sshcmd "$$SYNC_SSH_WRAPPER" \
		-sshargs "-o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password -o PubkeyAuthentication=no -o ServerAliveInterval=30" \
		-path config \
		-path data \
		-path firecrawl \
		-path Makefile \
		-path pyproject.toml \
		-path src \
		-path uv.lock \
		-path .env.example \
		-path .python-version; \
	rm -f "$$SYNC_SSH_WRAPPER"

# Cleanup
clean:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found"; \
		exit 1; \
	fi
	@echo "Removing Firecrawl containers and volumes..."
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) down -v
	@echo "✓ Firecrawl containers and volumes removed"

tidy:
	@echo "Removing Python cache/build/run artifacts..."
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@rm -rf .ruff_cache .pytest_cache build dist *.egg-info run
	@echo "✓ Python cache/build/run artifacts removed"
