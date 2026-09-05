.PHONY: help install test lint sync tidy

.DEFAULT_GOAL := help

UNISON := unison

help:
	@echo ""
	@echo "  REPOSITORY"
	@echo "    make install    Sync dependencies for all three projects"
	@echo "    make test       Run tests for all three projects"
	@echo "    make lint       Run crawler and processor Ruff checks"
	@echo "    make sync       Bidirectionally sync all project directories"
	@echo "    make tidy       Remove project-local caches"
	@echo ""

install:
	@cd crawler && uv sync
	@cd processor && uv sync
	@cd model-evaluation && uv sync

test:
	@$(MAKE) -C crawler test
	@$(MAKE) -C processor test
	@cd model-evaluation && uv run python -m pytest

lint:
	@$(MAKE) -C crawler lint
	@$(MAKE) -C processor lint

sync:
	@if [ ! -f .env ]; then \
		echo "Error: .env not found at repository root"; \
		echo "Required variables: SYNC_REMOTE_USER, SYNC_REMOTE_HOST, SYNC_REMOTE_DIR, SYNC_REMOTE_PASSWORD"; \
		exit 1; \
	fi
	@set -eu; set -a; . ./.env; set +a; \
	for var in SYNC_REMOTE_USER SYNC_REMOTE_HOST SYNC_REMOTE_DIR SYNC_REMOTE_PASSWORD; do \
		eval "value=\$$$$var"; \
		if [ -z "$$value" ]; then echo "Error: $$var is required in .env"; exit 1; fi; \
	done; \
	command -v sshpass >/dev/null 2>&1 || { echo "Error: sshpass not found"; exit 1; }; \
	command -v $(UNISON) >/dev/null 2>&1 || { echo "Error: $(UNISON) not found"; exit 1; }; \
	echo "Creating remote directory $$SYNC_REMOTE_USER@$$SYNC_REMOTE_HOST:$$SYNC_REMOTE_DIR"; \
	SSHPASS="$$SYNC_REMOTE_PASSWORD" sshpass -e ssh \
		-o StrictHostKeyChecking=accept-new \
		-o PreferredAuthentications=password \
		-o PubkeyAuthentication=no \
		"$$SYNC_REMOTE_USER@$$SYNC_REMOTE_HOST" \
		"mkdir -p \"$$SYNC_REMOTE_DIR\" && command -v unison >/dev/null 2>&1"; \
	SYNC_SSH_WRAPPER="$$(mktemp /tmp/fondocyt-sync-ssh.XXXXXX)"; \
	trap 'rm -f "$$SYNC_SSH_WRAPPER"' EXIT; \
	printf '%s\n' '#!/bin/sh' 'exec sshpass -e ssh "$$@"' > "$$SYNC_SSH_WRAPPER"; \
	chmod 700 "$$SYNC_SSH_WRAPPER"; \
	echo "Synchronizing crawler, processor, model evaluation, and root documentation"; \
	SSHPASS="$$SYNC_REMOTE_PASSWORD" $(UNISON) "$(CURDIR)" "ssh://$$SYNC_REMOTE_USER@$$SYNC_REMOTE_HOST/$$SYNC_REMOTE_DIR" \
		-auto \
		-batch \
		-times \
		-perms 0 \
		-sshcmd "$$SYNC_SSH_WRAPPER" \
		-sshargs "-o StrictHostKeyChecking=accept-new -o PreferredAuthentications=password -o PubkeyAuthentication=no -o ServerAliveInterval=30" \
		-ignore 'Name .git' \
		-ignore 'Name .env' \
		-ignore 'Name .venv' \
		-ignore 'Name .venv-report' \
		-ignore 'Name .cache' \
		-ignore 'Name .firecrawl' \
		-ignore 'Name .opencode' \
		-ignore 'Name .pytest_cache' \
		-ignore 'Name .ruff_cache' \
		-ignore 'Name .DS_Store' \
		-ignore 'Name __pycache__' \
		-ignore 'Name *.pyc' \
		-path README.md \
		-path Makefile \
		-path .env.example \
		-path .gitignore \
		-path crawler \
		-path processor \
		-path model-evaluation

tidy:
	@$(MAKE) -C crawler tidy
	@$(MAKE) -C processor tidy
	@rm -rf model-evaluation/.pytest_cache model-evaluation/__pycache__ model-evaluation/tests/__pycache__
