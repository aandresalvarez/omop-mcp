# ============================================================================
# OMOP MCP Server - Makefile with UV support
# ============================================================================

# Configuration
PY_VERSION := 3.12
VENV := .venv
UV := uv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
BLACK := $(VENV)/bin/black

.PHONY: help venv install install-dev dev-tools format lint typecheck test test-cov \
        http stdio run clean check pre-commit pre-commit-install dev

# ============================================================================
# Help
# ============================================================================

help:
	@echo "═══════════════════════════════════════════════════════════════════"
	@echo "OMOP MCP Server - Development Commands"
	@echo "═══════════════════════════════════════════════════════════════════"
	@echo ""
	@echo "Setup:"
	@echo "  make venv            # Create $(VENV) with Python $(PY_VERSION) using uv"
	@echo "  make install         # Install package dependencies into $(VENV)"
	@echo "  make install-dev     # Install package + dev dependencies"
	@echo "  make dev-tools       # Install dev tools (ruff, mypy, black, pytest)"
	@echo "  make dev             # Full setup: venv + install-dev + dev-tools"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format          # Format code with black and ruff"
	@echo "  make lint            # Lint code with ruff"
	@echo "  make typecheck       # Type-check with mypy"
	@echo "  make check           # Run all checks (format + lint + typecheck + test)"
	@echo "  make pre-commit      # Run pre-commit on all files"
	@echo "  make pre-commit-install # Install pre-commit hooks"
	@echo ""
	@echo "Testing:"
	@echo "  make test            # Run tests with pytest"
	@echo "  make test-cov        # Run tests with coverage report"
	@echo ""
	@echo "Run Server:"
	@echo "  make http            # Run MCP server in HTTP mode"
	@echo "  make stdio           # Run MCP server in stdio mode"
	@echo "  make run             # Alias for http"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           # Remove $(VENV) and build artifacts"
	@echo ""
	@echo "═══════════════════════════════════════════════════════════════════"

# ============================================================================
# Environment Setup
# ============================================================================

venv:
	@echo "Creating virtual environment with uv..."
	@if command -v $(UV) >/dev/null 2>&1; then \
		$(UV) venv $(VENV) --python $(PY_VERSION); \
		echo "✅ Virtual environment created at $(VENV)"; \
	else \
		echo "❌ Error: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		echo "   Or use pip: pip install uv"; \
		exit 1; \
	fi

install: venv
	@echo "Installing package dependencies with uv..."
	@$(UV) pip install -e .
	@echo "✅ Package dependencies installed"

install-dev: venv
	@echo "Installing package + dev dependencies with uv..."
	@$(UV) pip install -e ".[dev]"
	@echo "✅ Dev dependencies installed"

dev-tools: venv
	@echo "Installing development tools..."
	@$(UV) pip install ruff mypy black pytest pytest-cov pytest-asyncio pre-commit
	@echo "✅ Dev tools installed"

dev: venv install-dev dev-tools
	@echo "✅ Development environment ready!"
	@echo ""
	@echo "Activate with: source $(VENV)/bin/activate"
	@echo "Or run commands with: make <target>"

# ============================================================================
# Code Quality
# ============================================================================

format:
	@echo "Formatting code with black and ruff..."
	@$(BLACK) src/ tests/ || true
	@$(RUFF) check src/ tests/ --fix || true
	@echo "✅ Code formatted"

lint:
	@echo "Linting code with ruff..."
	@$(RUFF) check src/ tests/
	@echo "✅ Lint checks passed"

typecheck:
	@echo "Type checking with mypy..."
	@$(MYPY) src/
	@echo "✅ Type checks passed"

check: format lint typecheck test
	@echo "✅ All checks passed!"

pre-commit:
	@echo "Running pre-commit on all files..."
	@$(VENV)/bin/pre-commit run --all-files
	@echo "✅ Pre-commit checks complete"

pre-commit-install: venv
	@echo "Installing pre-commit hooks..."
	@$(UV) pip install pre-commit
	@$(VENV)/bin/pre-commit install
	@echo "✅ Pre-commit hooks installed"

# ============================================================================
# Testing
# ============================================================================

test:
	@echo "Running tests with pytest..."
	@$(PYTEST) -v --maxfail=1
	@echo "✅ Tests passed"

test-cov:
	@echo "Running tests with coverage..."
	@$(PYTEST) --cov=omop_mcp --cov-report=html --cov-report=term
	@echo "✅ Coverage report generated in htmlcov/"

# ============================================================================
# Run Server
# ============================================================================

http:
	@echo "Starting MCP server (HTTP mode on port 8000)..."
	@$(PYTHON) -m omop_mcp.server --http --port 8000

stdio:
	@echo "Starting MCP server (stdio mode)..."
	@$(PYTHON) -m omop_mcp.server --stdio

run: http

# ============================================================================
# Cleanup
# ============================================================================

clean:
	@echo "Cleaning up build artifacts and caches..."
	@rm -rf $(VENV)
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info
	@rm -rf .pytest_cache/
	@rm -rf .mypy_cache/
	@rm -rf .ruff_cache/
	@rm -rf htmlcov/
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

# ============================================================================
# Quick Start
# ============================================================================

.DEFAULT_GOAL := help
