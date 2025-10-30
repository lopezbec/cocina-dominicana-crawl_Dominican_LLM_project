.PHONY: help setup install firecrawl-init firecrawl-build firecrawl-start firecrawl-stop \
        firecrawl-restart firecrawl-status firecrawl-logs firecrawl-clean \
        scrape scrape-url scrape-category scrape-list scrape-discover test clean clean-all \
        check-docker check-python

.DEFAULT_GOAL := help

PYTHON := python3
PIP := $(PYTHON) -m pip
FIRECRAWL_DIR := firecrawl-local
FIRECRAWL_URL := https://github.com/mendableai/firecrawl.git
DOCKER_COMPOSE := docker compose
VENV := .venv

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
	@echo "  ║              Dominican Culinary Heritage Web Scraper                  ║"
	@echo "  ║                  Local Firecrawl + Python3                            ║"
	@echo "  ║                                                                       ║"
	@echo "  ╚═══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  SETUP COMMANDS"
	@echo "  ──────────────────────────────────────────────────────────────────────"
	@echo "    make setup              Complete first-time setup (install + firecrawl)"
	@echo "    make install            Install Python dependencies"
	@echo "    make firecrawl-init     Clone and initialize Firecrawl"
	@echo ""
	@echo "  FIRECRAWL MANAGEMENT"
	@echo "  ──────────────────────────────────────────────────────────────────────"
	@echo "    make firecrawl-build    Build Docker images (first run: 5-10 min)"
	@echo "    make firecrawl-start    Start Firecrawl services"
	@echo "    make firecrawl-stop     Stop Firecrawl services"
	@echo "    make firecrawl-restart  Restart all services"
	@echo "    make firecrawl-status   Show service status"
	@echo "    make firecrawl-logs     Follow API logs"
	@echo ""
	@echo "  SCRAPING COMMANDS"
	@echo "  ──────────────────────────────────────────────────────────────────────"
	@echo "    make scrape                    Run all configured sections"
	@echo "    make scrape-url URL=<url>      Scrape a single URL"
	@echo "    make scrape-category URL=<url> Crawl category and scrape articles"
	@echo "    make scrape-list FILE=<file>   Scrape URLs from file"
	@echo "    make scrape-discover URL=<url> Discover URLs without scraping"
	@echo "    make test                      Test Firecrawl endpoint"
	@echo "    make clean                     Remove scraped content and logs"
	@echo "    make clean-all                 Remove all generated files including Firecrawl"
	@echo ""
	@echo "  CHECKS"
	@echo "  ──────────────────────────────────────────────────────────────────────"
	@echo "    make check-docker       Verify Docker is installed and running"
	@echo "    make check-python       Verify Python installation"
	@echo ""

setup: check-docker check-python install firecrawl-init firecrawl-build firecrawl-start
	@echo ""
	@echo "  ╔═══════════════════════════════════════════════════════════╗"
	@echo "  ║                                                           ║"
	@echo "  ║                    SETUP COMPLETE                         ║"
	@echo "  ║                                                           ║"
	@echo "  ║  Next steps:                                              ║"
	@echo "  ║    make test     - Verify Firecrawl is working            ║"
	@echo "  ║    make scrape   - Start scraping Dominican recipes       ║"
	@echo "  ║                                                           ║"
	@echo "  ╚═══════════════════════════════════════════════════════════╝"
	@echo ""

install: check-python
	@if [ ! -f requirements.txt ]; then \
		echo "Error: requirements.txt not found"; \
		exit 1; \
	fi
	@echo ""
	@echo "  Installing Python dependencies..."
	@$(PIP) install -r requirements.txt
	@echo ""
	@echo "  ✓ Dependencies installed successfully"
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

scrape: check-python
	@if [ ! -f scraper.py ]; then \
		echo "Error: scraper.py not found"; \
		exit 1; \
	fi
	@echo "Starting scraper..."
	@$(PYTHON) scraper.py

scrape-url: check-python
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required"; \
		echo "Usage: make scrape-url URL=https://www.cocinadominicana.com/batata-asada"; \
		exit 1; \
	fi
	@echo "Scraping single URL: $(URL)"
	@$(PYTHON) cli.py scrape "$(URL)"

scrape-category: check-python
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required"; \
		echo "Usage: make scrape-category URL=https://www.cocinadominicana.com/cocina DEPTH=2"; \
		exit 1; \
	fi
	@echo "Crawling category: $(URL)"
	@if [ -n "$(DEPTH)" ]; then \
		$(PYTHON) cli.py crawl "$(URL)" --depth $(DEPTH); \
	else \
		$(PYTHON) cli.py crawl "$(URL)"; \
	fi

scrape-list: check-python
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE parameter required"; \
		echo "Usage: make scrape-list FILE=urls.txt"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "Error: File not found: $(FILE)"; \
		exit 1; \
	fi
	@echo "Scraping URLs from file: $(FILE)"
	@$(PYTHON) cli.py scrape-list "$(FILE)"

scrape-discover: check-python
	@if [ -z "$(URL)" ]; then \
		echo "Error: URL parameter required"; \
		echo "Usage: make scrape-discover URL=https://www.cocinadominicana.com/inicia"; \
		exit 1; \
	fi
	@echo "Discovering URLs from: $(URL)"
	@$(PYTHON) cli.py discover "$(URL)"

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
	@rm -f *.log
	@rm -f progress.json
	@echo "Clean complete."

clean-all: clean firecrawl-clean
	@echo "Removing Firecrawl installation..."
	@rm -rf $(FIRECRAWL_DIR)
	@echo "Full cleanup complete."

check-docker:
	@which docker > /dev/null || (echo "Error: Docker not found. Install from https://docs.docker.com/get-docker/" && exit 1)
	@docker info > /dev/null 2>&1 || (echo "Error: Docker daemon not running. Start Docker Desktop." && exit 1)
	@which docker-compose > /dev/null || docker compose version > /dev/null 2>&1 || \
		(echo "Error: Docker Compose not found." && exit 1)
	@echo "Docker check passed."

check-python:
	@which $(PYTHON) > /dev/null || (echo "Error: Python 3 not found." && exit 1)
	@echo "Python check passed."
