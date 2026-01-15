.PHONY: help setup install firecrawl-start firecrawl-stop firecrawl-restart \
        firecrawl-status firecrawl-logs firecrawl-test scrape scrape-url \
        scrape-force process clean

.DEFAULT_GOAL := help

# Variables
PYTHON := uv run python
UV := uv
FIRECRAWL_DIR := firecrawl
DOCKER_COMPOSE := docker compose

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
	@echo ""
	@echo "  CLEANUP"
	@echo "    make clean                    Remove Firecrawl containers and volumes"
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
	@if [ ! -d data/raw ]; then \
		echo ""; \
		echo "Error: data/raw directory not found"; \
		echo "Run scraping commands first to generate content"; \
		echo ""; \
		exit 1; \
	fi
	@$(PYTHON) -m dominican_llm_scraper process

# Cleanup
clean:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found"; \
		exit 1; \
	fi
	@echo "Removing Firecrawl containers and volumes..."
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) down -v
	@echo "✓ Firecrawl containers and volumes removed"
