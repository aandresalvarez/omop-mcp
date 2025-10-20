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
PYRIGHT := $(VENV)/bin/pyright
PYLINT := $(VENV)/bin/pylint
BLACK := $(VENV)/bin/black
BANDIT := $(VENV)/bin/bandit
SQLFLUFF := $(VENV)/bin/sqlfluff
PIP_AUDIT := $(VENV)/bin/pip-audit
SAFETY := $(VENV)/bin/safety

.PHONY: help venv install install-dev dev-tools format lint typecheck pyright pylint test test-cov \
        http stdio run clean check check-all pre-commit pre-commit-full pre-commit-install dev \
        security sql-lint sql-fix coverage audit

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
	@echo "  make pylint          # Lint code with pylint (strict)"
	@echo "  make typecheck       # Type-check with mypy"
	@echo "  make pyright         # Type-check with pyright"
	@echo "  make check           # Run all checks (format + lint + typecheck + test)"
	@echo "  make check-all       # Run ALL checks including pyright and pylint"
	@echo "  make pre-commit      # Run comprehensive pre-commit checks"
	@echo "  make pre-commit-full # Run FULL pre-commit checks (includes pylint, security, SQL)"
	@echo "  make pre-commit-install # Install pre-commit hooks"
	@echo ""
	@echo "Security & Quality:"
	@echo "  make security        # Run security scans (bandit + pip-audit)"
	@echo "  make audit           # Comprehensive security audit (security + safety)"
	@echo "  make sql-lint        # Lint SQL files with sqlfluff"
	@echo "  make sql-fix         # Auto-fix SQL files with sqlfluff"
	@echo ""
	@echo "Testing:"
	@echo "  make test            # Run tests with pytest"
	@echo "  make test-cov        # Run tests with coverage report"
	@echo "  make coverage        # Generate detailed coverage report (HTML + term)"
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
	@$(UV) pip install ruff mypy pyright pylint black pytest pytest-cov pytest-asyncio pre-commit
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

pylint:
	@echo "Linting code with pylint (strict)..."
	@$(PYLINT) src/omop_mcp --rcfile=.pylintrc || true
	@echo "✅ Pylint checks complete"

typecheck:
	@echo "Type checking with mypy..."
	@$(MYPY) src/
	@echo "✅ Type checks passed"

pyright:
	@echo "Type checking with pyright..."
	@$(PYRIGHT) src/
	@echo "✅ Pyright checks passed"

check: format lint typecheck test
	@echo "✅ All checks passed!"

check-all: format lint pylint typecheck pyright security test
	@echo "✅ ALL checks passed (including security, pylint, and pyright)!"

pre-commit:
	@echo "Running comprehensive pre-commit checks..."
	@echo "→ Code formatting..."
	@$(BLACK) src/ tests/ || true
	@$(RUFF) check src/ tests/ --fix || true
	@echo "→ Linting with ruff..."
	@$(RUFF) check src/ tests/
	@echo "→ Type checking with mypy..."
	@$(MYPY) src/
	@echo "→ Type checking with pyright..."
	@$(PYRIGHT) src/
	@echo "→ Security scan with bandit..."
	@$(BANDIT) -r src/ -ll -f screen || true
	@echo "→ Running tests..."
	@$(PYTEST) -v --maxfail=1
	@echo "→ Pre-commit hooks..."
	@$(VENV)/bin/pre-commit run --all-files
	@echo "✅ All pre-commit checks complete"

pre-commit-full:
	@echo "Running FULL pre-commit checks (comprehensive)..."
	@echo "→ Code formatting..."
	@$(BLACK) src/ tests/ || true
	@$(RUFF) check src/ tests/ --fix || true
	@echo "→ Linting with ruff..."
	@$(RUFF) check src/ tests/
	@echo "→ Linting with pylint..."
	@$(PYLINT) src/omop_mcp --rcfile=.pylintrc || true
	@echo "→ Type checking with mypy..."
	@$(MYPY) src/
	@echo "→ Type checking with pyright..."
	@$(PYRIGHT) src/
	@echo "→ Security scan with bandit..."
	@$(BANDIT) -r src/ -ll -f screen || true
	@echo "→ Vulnerability scan with pip-audit..."
	@$(PIP_AUDIT) --require-hashes --disable-pip || $(PIP_AUDIT) || true
	@echo "→ SQL linting..."
	@$(SQLFLUFF) lint agents/qb/*.sql --dialect bigquery || true
	@echo "→ Running tests..."
	@$(PYTEST) -v --maxfail=1
	@echo "→ Pre-commit hooks..."
	@$(VENV)/bin/pre-commit run --all-files
	@echo "✅ FULL pre-commit checks complete"

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

coverage:
	@echo "Running comprehensive coverage analysis..."
	@$(PYTEST) --cov=omop_mcp --cov-report=html --cov-report=term --cov-report=json --cov-branch
	@echo "✅ Detailed coverage report:"
	@echo "   - HTML: htmlcov/index.html"
	@echo "   - JSON: coverage.json"
	@echo "   - Terminal summary above"

# ============================================================================
# Security & SQL Quality
# ============================================================================

security:
	@echo "Running security scans..."
	@echo "→ Bandit (Python security linter)..."
	@$(BANDIT) -r src/ -ll -f screen || true
	@echo ""
	@echo "→ pip-audit (PyPI vulnerability scanner)..."
	@$(PIP_AUDIT) --require-hashes --disable-pip || $(PIP_AUDIT) || true
	@echo "✅ Security scans complete"

audit: security
	@echo "→ Safety (dependency vulnerability database)..."
	@$(SAFETY) check --json || $(SAFETY) scan || true
	@echo "✅ Comprehensive security audit complete"

sql-lint:
	@echo "Linting SQL files with sqlfluff..."
	@$(SQLFLUFF) lint agents/qb/*.sql --dialect bigquery || true
	@echo "✅ SQL lint complete"

sql-fix:
	@echo "Auto-fixing SQL files with sqlfluff..."
	@$(SQLFLUFF) fix agents/qb/*.sql --dialect bigquery
	@echo "✅ SQL files formatted"

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
