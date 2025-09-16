.PHONY: help install install-dev test lint format clean run install-pre-commit-hooks

# Default target
help:
	@echo "OpenHands Server - Available commands:"
	@echo "  install                  - Install the package"
	@echo "  install-dev              - Install with development dependencies"
	@echo "  install-pre-commit-hooks - Install pre-commit hooks"
	@echo "  test                     - Run tests"
	@echo "  lint                     - Run pre-commit on all files"
	@echo "  format                   - Format code with ruff"
	@echo "  clean                    - Clean build artifacts"
	@echo "  run                      - Run the server"


install-uv:
	@if ! command -v uv &> /dev/null; then \
		echo "Installing UV..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	else \
		echo "UV is already installed"; \
	fi

check-uv-version:
	@echo "$(YELLOW)Checking uv version...$(RESET)"
	@UV_VERSION=$$(uv --version | cut -d' ' -f2); \
	REQUIRED_VERSION=$(REQUIRED_UV_VERSION); \
	if [ "$$(printf '%s\n' "$$REQUIRED_VERSION" "$$UV_VERSION" | sort -V | head -n1)" != "$$REQUIRED_VERSION" ]; then \
		echo "$(RED)Error: uv version $$UV_VERSION is less than required $$REQUIRED_VERSION$(RESET)"; \
		echo "$(YELLOW)Please update uv with: uv self update$(RESET)"; \
		exit 1; \
	fi; \
	echo "$(GREEN)uv version $$UV_VERSION meets requirements$(RESET)"

install: install-uv check-uv-version
	@echo "Installing development dependencies..."
	uv sync --extra dev
	@echo "Installing pre-commit hooks..."
	@git config --unset-all core.hooksPath || true
	uv run pre-commit install
	@echo "Pre-commit hooks installed successfully."

# Run tests
test: install-uv check-uv-version install
	uv run pytest

# Run pre-commit on all files
lint: check-uv-version install
	@echo "Running pre-commit on all files..."
	uv run pre-commit run --all-files --show-diff-on-failure

format: check-uv-version install
	@echo "Formatting code with ruff..."
	uv run ruff format

clean:
	rm -rf .venv/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:
	uv run openhands-sdk-server

test-schema:
	set -e
	# Generate OpenAPI JSON inline (no file left in repo)
	uv run python -c 'import os,json; from openhands_server.sdk_server.api import api; open("openapi.json","w").write(json.dumps(api.openapi(), indent=2))'

	# Generate client from the temp schema and **fail on any warnings** to check
	uv run openapi-python-client generate \
	--path "openapi.json" \
	--output-path ".client" \
	--meta uv \
	--overwrite \
	--fail-on-warning
	
	# Clean up temp schema
	rm -f openapi.json
	rm -rf .client
