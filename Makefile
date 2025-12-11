.PHONY: help setup install check-uv firecrawl-init firecrawl-build firecrawl-start firecrawl-stop \
        firecrawl-restart firecrawl-status firecrawl-logs firecrawl-clean \
        scrape scrape-url scrape-category scrape-list scrape-discover process test clean clean-all \
        check-docker check-python uv-add uv-remove uv-sync uv-lock uv-outdated setup-site list-sites

.DEFAULT_GOAL := help

PYTHON := uv run python
UV := uv
FIRECRAWL_DIR := firecrawl-local
FIRECRAWL_URL := https://github.com/mendableai/firecrawl.git
DOCKER_COMPOSE := docker compose
VENV := .venv
UV_INSTALL_URL := https://astral.sh/uv/install.sh

help:
	@echo ""
	@echo "  ╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "  ║                                                                       ║"
	@echo "  ║   ██████╗ ██████╗  ██████╗██╗███╗   ██╗ █████╗     ██████╗ ██████╗    ║"
	@echo "  ║  ██╔════╝██╔═══██╗██╔════╝██║████╗  ██║██╔══██╗    ██╔══██╗██╔══██╗   ║"
	@echo "  ║  ██║     ██║   ██║██║     ██║██╔██╗ ██║███████║    ██║  ██║██████╔╝   ║"
	@echo "  ║  ██║     ██║   ██║██║     ██║██║╚██╗██║██╔══██║    ██║  ██║██╔══██╗   ║"
	@echo "  ║  ╚██████╗╚██████╔╝╚██████╗██║██║ ╚████║██║  ██║    ██████╔╝██║  ██║   ║"
	@echo "  ║   ╚═════╝ ╚═════╝  ╚═════╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ║"
	@echo "  ║                                                                       ║"
	@echo "  ║              Multi-Site Web Scraper with Firecrawl                    ║"
	@echo "  ║                  Local Firecrawl + Python3                            ║"
	@echo "  ║                                                                       ║"
	@echo "  ╚═══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  ENVIRONMENT: CRAWL_DOMAIN=<domain> (REQUIRED for scraping)"
	@echo ""
	@echo "  SETUP COMMANDS"
	@echo "  ------------------------------------------------------------"
	@echo "    make setup              Complete first-time setup (install + firecrawl)"
	@echo "    make install            Install Python dependencies"
	@echo "    make firecrawl-init     Clone and initialize Firecrawl"
	@echo "    make setup-site DOMAIN=<domain>  Create new site configuration"
	@echo "    make list-sites         List available sites"
	@echo ""
	@echo "  FIRECRAWL MANAGEMENT"
	@echo "  ------------------------------------------------------------"
	@echo "    make firecrawl-build    Build Docker images (first run: 5-10 min)"
	@echo "    make firecrawl-start    Start Firecrawl services"
	@echo "    make firecrawl-stop     Stop Firecrawl services"
	@echo "    make firecrawl-restart  Restart all services"
	@echo "    make firecrawl-status   Show service status"
	@echo "    make firecrawl-logs     Follow API logs"
	@echo ""
	@echo "  SCRAPING COMMANDS (Require CRAWL_DOMAIN environment variable)"
	@echo "  ------------------------------------------------------------"
	@echo "    CRAWL_DOMAIN=example.com make scrape                 Run all configured sections"
	@echo "    CRAWL_DOMAIN=example.com make scrape-url URL=<url>   Scrape a single URL"
	@echo "    CRAWL_DOMAIN=example.com make scrape-category URL=<url>  Crawl category"
	@echo "    CRAWL_DOMAIN=example.com make scrape-list FILE=<file>    Scrape URLs from file"
	@echo "    CRAWL_DOMAIN=example.com make scrape-discover URL=<url>  Discover URLs"
	@echo "    make test                                            Test Firecrawl endpoint"
	@echo ""
	@echo "  PROCESSING COMMANDS"
	@echo "  ------------------------------------------------------------"
	@echo "    make process                   Process markdown to plain text"
	@echo "    make clean                     Remove scraped content and logs"
	@echo "    make clean-all                 Remove all generated files including Firecrawl"
	@echo ""
	@echo "  CHECKS"
	@echo "  ------------------------------------------------------------"
	@echo "    make check-docker       Verify Docker is installed and running"
	@echo "    make check-python       Verify Python installation"
	@echo "    make check-uv           Verify UV installation (auto-install on macOS/Linux)"
	@echo ""
	@echo "  UV PACKAGE MANAGEMENT"
	@echo "  ------------------------------------------------------------"
	@echo "    make uv-add PKG=<name>      Add a package"
	@echo "    make uv-remove PKG=<name>   Remove a package"
	@echo "    make uv-sync                Sync dependencies from pyproject.toml"
	@echo "    make uv-lock                Update lockfile"
	@echo "    make uv-outdated            Check for outdated packages"
	@echo ""

setup: check-docker check-uv check-python install firecrawl-init firecrawl-build firecrawl-start
	@echo ""
	@echo "  +-----------------------------------------------------------+"
	@echo "  |                                                           |"
	@echo "  |                    SETUP COMPLETE                         |"
	@echo "  |                                                           |"
	@echo "  |  Next steps:                                              |"
	@echo "  |    make test     - Verify Firecrawl is working            |"
	@echo "  |    make scrape   - Start scraping Dominican recipes       |"
	@echo "  |                                                           |"
	@echo "  +-----------------------------------------------------------+"
	@echo ""

install: check-uv check-python
	@if [ ! -f pyproject.toml ]; then \
		echo ""; \
		echo "  [x] Error: pyproject.toml not found"; \
		echo "  Run 'uv init' to create one or restore from backup"; \
		echo ""; \
		exit 1; \
	fi
	@echo ""
	@echo "  Installing Python dependencies with UV..."
	@echo "  ------------------------------------------------------------"
	@echo ""
	@echo "  Creating virtual environment and syncing dependencies..."
	@$(UV) sync
	@echo ""
	@echo "  [+] Dependencies installed successfully"
	@echo ""

firecrawl-init:
	@if [ -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Firecrawl directory already exists. Skipping clone."; \
	else \
		echo "Cloning Firecrawl repository..."; \
		git clone $(FIRECRAWL_URL) $(FIRECRAWL_DIR); \
		echo "Creating Firecrawl .env configuration..."; \
		echo "PORT=3002" > $(FIRECRAWL_DIR)/.env; \
		echo "HOST=0.0.0.0" >> $(FIRECRAWL_DIR)/.env; \
		echo "USE_DB_AUTHENTICATION=false" >> $(FIRECRAWL_DIR)/.env; \
		echo "BULL_AUTH_KEY=CHANGEME" >> $(FIRECRAWL_DIR)/.env; \
		echo "LOGGING_LEVEL=INFO" >> $(FIRECRAWL_DIR)/.env; \
		echo "Firecrawl initialized successfully."; \
	fi

firecrawl-build:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl not initialized. Run 'make firecrawl-init' first."; \
		exit 1; \
	fi
	@echo "Building Docker images (this may take 5-10 minutes on first run)..."
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) build
	@echo "Build complete."

firecrawl-start:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl not initialized. Run 'make firecrawl-init' first."; \
		exit 1; \
	fi
	@echo "Starting Firecrawl services..."
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo ""
	@echo "  ╔═══════════════════════════════════════════════════════════╗"
	@echo "  ║                                                           ║"
	@echo "  ║              FIRECRAWL SERVICES RUNNING                   ║"
	@echo "  ║                                                           ║"
	@echo "  ║  API:        http://localhost:3002                        ║"
	@echo "  ║  PostgreSQL: localhost:5432                               ║"
	@echo "  ║  Redis:      localhost:6379                               ║"
	@echo "  ║                                                           ║"
	@echo "  ║  Commands:                                                ║"
	@echo "  ║    make test              - Test the endpoint             ║"
	@echo "  ║    make firecrawl-logs    - View logs                     ║"
	@echo "  ║    make firecrawl-status  - Check status                  ║"
	@echo "  ║    make firecrawl-stop    - Stop services                 ║"
	@echo "  ║                                                           ║"
	@echo "  ╚═══════════════════════════════════════════════════════════╝"
	@echo ""

firecrawl-stop:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found."; \
		exit 1; \
	fi
	@echo "Stopping Firecrawl services..."
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) down
	@echo "Services stopped."

firecrawl-restart: firecrawl-stop firecrawl-start
	@echo "Firecrawl restarted."

firecrawl-status:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found."; \
		exit 1; \
	fi
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) ps

firecrawl-logs:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found."; \
		exit 1; \
	fi
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) logs -f api

firecrawl-clean:
	@if [ ! -d "$(FIRECRAWL_DIR)" ]; then \
		echo "Error: Firecrawl directory not found."; \
		exit 1; \
	fi
	@echo "Removing Firecrawl containers and volumes..."
	@cd $(FIRECRAWL_DIR) && $(DOCKER_COMPOSE) down -v
	@echo "Firecrawl cleaned."

scrape: check-uv
	@$(PYTHON) -m core.cli scrape-all

scrape-url: check-uv
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required"; \
		echo "Usage: make scrape-url URL=https://example.com/page"; \
		exit 1; \
	fi
	@$(PYTHON) -m core.cli scrape "$(URL)"

scrape-category: check-uv
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required"; \
		echo "Usage: make scrape-category URL=https://example.com/category DEPTH=2"; \
		exit 1; \
	fi
	@if [ -n "$(DEPTH)" ]; then \
		$(PYTHON) -m core.cli crawl "$(URL)" --depth $(DEPTH); \
	else \
		$(PYTHON) -m core.cli crawl "$(URL)"; \
	fi

scrape-list: check-uv
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE parameter required"; \
		echo "Usage: make scrape-list FILE=urls.txt"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "Error: File not found: $(FILE)"; \
		exit 1; \
	fi
	@$(PYTHON) -m core.cli scrape-list "$(FILE)"

scrape-discover: check-uv
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required"; \
		echo "Usage: make scrape-discover URL=https://example.com/section"; \
		echo "       make scrape-discover URL=https://... SAVE=urls.txt NOINTERACTIVE=1"; \
		exit 1; \
	fi
	@if [ -n "$(NOINTERACTIVE)" ]; then \
		if [ -n "$(SAVE)" ]; then \
			$(PYTHON) -m core.cli discover "$(URL)" --no-interactive --save "$(SAVE)"; \
		else \
			$(PYTHON) -m core.cli discover "$(URL)" --no-interactive; \
		fi \
	else \
		$(PYTHON) -m core.cli discover "$(URL)"; \
	fi

process: check-uv
	@if [ ! -d scraped_content ]; then \
		echo "Error: scraped_content directory not found. Run scraping commands first."; \
		exit 1; \
	fi
	@$(PYTHON) -m core.cli process

setup-site:
	@if [ -z "$(DOMAIN)" ]; then \
		echo "Error: DOMAIN parameter required"; \
		echo "Usage: make setup-site DOMAIN=example.com"; \
		exit 1; \
	fi
	@echo "Creating site configuration for $(DOMAIN)..."
	@DOMAIN_DIR=$$(echo "$(DOMAIN)" | sed 's/\./_/g'); \
	if [ -d "sites/$$DOMAIN_DIR" ]; then \
		echo "Error: Site $$DOMAIN_DIR already exists"; \
		exit 1; \
	fi; \
	mkdir -p sites/$$DOMAIN_DIR; \
	sed "s/DOMAIN_PLACEHOLDER/$(DOMAIN)/g" templates/site_config.yml > sites/$$DOMAIN_DIR/config.yml; \
	cp templates/processing_patterns.yml sites/$$DOMAIN_DIR/; \
	echo ""; \
	echo "  [+] Site created: sites/$$DOMAIN_DIR/"; \
	echo "  [!] Edit sites/$$DOMAIN_DIR/config.yml before crawling"; \
	echo ""; \
	echo "  Next steps:"; \
	echo "    1. Edit sites/$$DOMAIN_DIR/config.yml"; \
	echo "    2. CRAWL_DOMAIN=$(DOMAIN) make scrape"; \
	echo ""

list-sites:
	@echo ""
	@echo "  Available Sites:"
	@echo "  ────────────────────────────────────────────"
	@ls -1 sites/ 2>/dev/null | grep -v README | grep -v __pycache__ | sed 's/_/./g' | sed 's/^/    /' || echo "    No sites configured"
	@echo ""

test:
	@echo ""
	@echo "  Testing Firecrawl endpoint..."
	@echo "  ──────────────────────────────────────────────────────────────────────"
	@echo ""
	@curl -s http://localhost:3002/v2/scrape \
		-H 'Content-Type: application/json' \
		-d '{"url": "https://example.com", "formats": ["markdown"]}' \
		| $(PYTHON) -m json.tool || echo "Error: Firecrawl not responding. Run 'make firecrawl-start'"
	@echo ""

clean:
	@echo "Cleaning scraped content and logs..."
	@rm -rf scraped_content/
	@rm -rf scrapped_plain_text/
	@rm -f *.log
	@rm -f progress.json
	@echo "Clean complete."

clean-all: clean firecrawl-clean
	@echo "Removing Firecrawl installation..."
	@rm -rf $(FIRECRAWL_DIR)
	@echo "Removing virtual environment..."
	@rm -rf $(VENV)
	@echo "[+] Full cleanup complete."

check-docker:
	@which docker > /dev/null || (echo "Error: Docker not found. Install from https://docs.docker.com/get-docker/" && exit 1)
	@docker info > /dev/null 2>&1 || (echo "Error: Docker daemon not running. Start Docker Desktop." && exit 1)
	@which docker-compose > /dev/null || docker compose version > /dev/null 2>&1 || \
		(echo "Error: Docker Compose not found." && exit 1)
	@echo "Docker check passed."

check-python:
	@which python3 > /dev/null || (echo "Error: Python 3 not found." && exit 1)
	@echo "[+] Python check passed."

check-uv:
	@if ! command -v uv > /dev/null 2>&1; then \
		echo ""; \
		echo "  UV not found. Installing UV..."; \
		echo "  ------------------------------------------------------------"; \
		OS=$$(uname -s); \
		if [ "$$OS" = "Darwin" ] || [ "$$OS" = "Linux" ]; then \
			echo "  Detected $$OS - installing via official installer..."; \
			curl -LsSf $(UV_INSTALL_URL) | sh; \
			echo ""; \
			echo "  [+] UV installed successfully"; \
			echo "  [!] Please restart your shell or run: source $$HOME/.cargo/env"; \
			echo ""; \
		else \
			echo ""; \
			echo "  +----------------------------------------------------------+"; \
			echo "  |  UV Installation Required (Windows Detected)             |"; \
			echo "  +----------------------------------------------------------+"; \
			echo ""; \
			echo "  Please install UV manually:"; \
			echo ""; \
			echo "  Option 1 - PowerShell (Recommended):"; \
			echo "    powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""; \
			echo ""; \
			echo "  Option 2 - pip:"; \
			echo "    pip install uv"; \
			echo ""; \
			echo "  Option 3 - Standalone installer:"; \
			echo "    https://github.com/astral-sh/uv/releases"; \
			echo ""; \
			exit 1; \
		fi \
	else \
		UV_VERSION=$$(uv --version); \
		echo "[+] UV check passed ($$UV_VERSION)"; \
	fi

uv-add:
	@if [ -z "$(PKG)" ]; then \
		echo "[x] Error: PKG parameter required"; \
		echo "Usage: make uv-add PKG=requests"; \
		echo "       make uv-add PKG='requests>=2.31.0'"; \
		exit 1; \
	fi
	@echo "Adding package: $(PKG)"
	@$(UV) add $(PKG)
	@echo "[+] Package added and lockfile updated"

uv-remove:
	@if [ -z "$(PKG)" ]; then \
		echo "[x] Error: PKG parameter required"; \
		echo "Usage: make uv-remove PKG=requests"; \
		exit 1; \
	fi
	@echo "Removing package: $(PKG)"
	@$(UV) remove $(PKG)
	@echo "[+] Package removed and lockfile updated"

uv-sync:
	@echo "Syncing dependencies from pyproject.toml..."
	@$(UV) sync
	@echo "[+] Dependencies synchronized"

uv-lock:
	@echo "Updating lockfile..."
	@$(UV) lock
	@echo "[+] Lockfile updated"

uv-outdated:
	@echo "Checking for outdated packages..."
	@$(UV) pip list --outdated
