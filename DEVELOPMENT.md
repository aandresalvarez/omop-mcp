# OMOP MCP Development Guide

## Prerequisites

### Install UV (Required)

`uv` is a fast Python package installer and resolver written in Rust. It's required for this project's development workflow.

**Installation:**

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv

# Or with Homebrew
brew install uv
```

**Verify installation:**
```bash
uv --version
```

## Quick Start

### 1. Setup Development Environment

```bash
# One command to set up everything
make dev
```

This will:
- Create `.venv` with Python 3.12 using `uv`
- Install all package dependencies
- Install development tools (ruff, mypy, black, pytest)

### 2. Activate Virtual Environment

```bash
source .venv/bin/activate
```

Or use `make` commands directly (they use `.venv` automatically).

### 3. Verify Installation

```bash
# Import the package
python -c "from omop_mcp import config; print('✅ Package working!')"

# Test ATHENA client
python -c "from omop_mcp.tools import discover_concepts; print('✅ Tools working!')"
```

## Makefile Commands

### Setup Commands

| Command | Description |
|---------|-------------|
| `make venv` | Create `.venv` with Python 3.12 using uv |
| `make install` | Install package dependencies |
| `make install-dev` | Install package + dev dependencies |
| `make dev-tools` | Install development tools |
| `make dev` | **Full setup** (recommended for first time) |

### Code Quality Commands

| Command | Description |
|---------|-------------|
| `make format` | Format code with black and ruff |
| `make lint` | Lint code with ruff |
| `make typecheck` | Type-check with mypy |
| `make check` | Run all checks (format + lint + typecheck + test) |
| `make pre-commit` | Run pre-commit on all files |
| `make pre-commit-install` | Install pre-commit hooks |

### Testing Commands

| Command | Description |
|---------|-------------|
| `make test` | Run tests with pytest |
| `make test-cov` | Run tests with coverage report |

### Run Server Commands

| Command | Description |
|---------|-------------|
| `make http` | Run MCP server in HTTP mode (port 8000) |
| `make stdio` | Run MCP server in stdio mode |
| `make run` | Alias for `make http` |

### Cleanup Commands

| Command | Description |
|---------|-------------|
| `make clean` | Remove `.venv` and build artifacts |

## Development Workflow

### Initial Setup

```bash
# 1. Clone repository
git clone <repo-url>
cd omop-mcp

# 2. Setup development environment
make dev

# 3. Copy environment variables
cp .env.example .env

# 4. Edit .env with your credentials
# - OPENAI_API_KEY
# - BIGQUERY_PROJECT_ID
# - etc.
```

### Daily Development

```bash
# Activate environment
source .venv/bin/activate

# Make code changes...

# Format and check
make format
make lint
make typecheck

# Run tests
make test

# Or run all checks at once
make check
```

### Before Committing

```bash
# Run all checks
make check

# Or use pre-commit
make pre-commit-install  # First time only
make pre-commit
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# OpenAI (required for PydanticAI agents)
OPENAI_API_KEY=sk-...

# ATHENA API
ATHENA_BASE_URL=https://athena.ohdsi.org/api/v1

# BigQuery
BIGQUERY_PROJECT_ID=your-project-id
BIGQUERY_DATASET_ID=your-dataset-id

# Postgres (optional)
POSTGRES_DSN=postgresql://user:pass@localhost/omop

# Security
MAX_QUERY_COST_USD=1.0
ALLOW_PATIENT_LIST=false
QUERY_TIMEOUT_SEC=300
```

### Python Version

The project requires Python 3.12+. The version is specified in:
- `.python-version` (for pyenv/uv)
- `pyproject.toml` (for package metadata)

## Project Structure

```
omop-mcp/
├── src/omop_mcp/          # Main package
│   ├── __init__.py
│   ├── config.py          # Configuration with pydantic-settings
│   ├── models.py          # Pydantic data models
│   ├── backends/          # Database backends
│   │   ├── base.py        # Backend protocol
│   │   ├── bigquery.py    # BigQuery implementation
│   │   └── registry.py    # Backend registry
│   └── tools/             # MCP tools
│       ├── athena.py      # ATHENA API client
│       └── __init__.py
├── tests/                 # Test suite
├── pyproject.toml         # Package configuration
├── Makefile              # Development commands
├── .env.example          # Environment template
└── README.md             # User documentation
```

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
.venv/bin/pytest tests/test_athena_client.py -v

# Run specific test
.venv/bin/pytest tests/test_athena_client.py::test_search_concepts -v
```

### Writing Tests

Tests use `pytest` with async support:

```python
# tests/test_example.py
import pytest
from omop_mcp.tools import discover_concepts

def test_discover_concepts():
    result = discover_concepts("diabetes", limit=5)
    assert len(result.concepts) > 0
    assert result.query == "diabetes"

@pytest.mark.asyncio
async def test_async_function():
    # Async test example
    result = await some_async_function()
    assert result is not None
```

## Troubleshooting

### UV Not Found

If you see "uv not found":

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (may be needed)
export PATH="$HOME/.cargo/bin:$PATH"
```

### Python Version Issues

If Python 3.12 is not available:

```bash
# Install Python 3.12 (macOS with Homebrew)
brew install python@3.12

# Or use pyenv
pyenv install 3.12.0
pyenv local 3.12.0
```

### Import Errors

If you see import errors after setup:

```bash
# Reinstall in development mode
make clean
make dev

# Verify installation
.venv/bin/python -c "import omop_mcp; print(omop_mcp.__file__)"
```

### ATHENA API Errors

If ATHENA searches fail:

1. Check network connectivity
2. Verify ATHENA_BASE_URL in `.env`
3. Try the public endpoint: `https://athena.ohdsi.org/api/v1`

## Additional Resources

- **MCP Documentation**: https://modelcontextprotocol.io/
- **PydanticAI**: https://ai.pydantic.dev/
- **OMOP CDM**: https://ohdsi.github.io/CommonDataModel/
- **ATHENA**: https://athena.ohdsi.org/
- **UV Documentation**: https://github.com/astral-sh/uv

## Contributing

1. Create a feature branch
2. Make changes
3. Run `make check` to verify
4. Submit pull request

## License

[Your License Here]
