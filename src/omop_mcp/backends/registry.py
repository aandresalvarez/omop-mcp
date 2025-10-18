"""Backend registry for managing database backends."""

from typing import Any

import structlog

from omop_mcp.backends.base import Backend
from omop_mcp.backends.bigquery import BigQueryBackend

logger = structlog.get_logger()

# Backend registry
_backends: dict[str, Backend] = {}


def register_backend(backend: Backend) -> None:
    """Register a backend."""
    _backends[backend.name] = backend
    logger.info("backend_registered", name=backend.name, dialect=backend.dialect)


def get_backend(name: str) -> Backend:
    """Get a backend by name."""
    if name not in _backends:
        raise ValueError(f"Backend '{name}' not found. Available: {list(_backends.keys())}")
    return _backends[name]


def list_backends() -> dict[str, dict[str, Any]]:
    """List all registered backends with their capabilities."""
    return {
        name: {
            "name": backend.name,
            "dialect": backend.dialect,
            "features": (
                ["dry_run", "cost_estimate", "execute"] if name == "bigquery" else ["execute"]
            ),
        }
        for name, backend in _backends.items()
    }


# Initialize default backends
def initialize_backends() -> None:
    """Initialize and register default backends."""
    try:
        bigquery_backend = BigQueryBackend()
        register_backend(bigquery_backend)
    except Exception as e:
        logger.warning("bigquery_backend_init_failed", error=str(e))


# Auto-initialize on module import
initialize_backends()
