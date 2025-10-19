"""Backend registry for managing database backends."""

import logging
from typing import Any

from omop_mcp.backends.base import Backend
from omop_mcp.backends.bigquery import BigQueryBackend
from omop_mcp.backends.dialect import get_dialect_info, translate_sql
from omop_mcp.backends.duckdb import DuckDBBackend
from omop_mcp.backends.snowflake import SnowflakeBackend

logger = logging.getLogger(__name__)

# Backend registry
_backends: dict[str, Backend] = {}


def register_backend(backend: Backend) -> None:
    """Register a backend."""
    _backends[backend.name] = backend
    logger.info(f"Backend registered: {backend.name} (dialect={backend.dialect})")


def get_backend(name: str) -> Backend:
    """Get a backend by name."""
    if name not in _backends:
        raise ValueError(f"Backend '{name}' not found. Available: {list(_backends.keys())}")
    return _backends[name]


def list_backends() -> dict[str, dict[str, Any]]:
    """List all registered backends with their capabilities."""
    backend_features = {
        "bigquery": ["dry_run", "cost_estimate", "execute", "validate", "translate"],
        "snowflake": ["explain", "execute", "validate", "translate"],
        "duckdb": ["explain", "execute", "validate", "translate", "local"],
    }

    return {
        name: {
            "name": backend.name,
            "dialect": backend.dialect,
            "features": backend_features.get(name, ["execute"]),
        }
        for name, backend in _backends.items()
    }


def get_supported_dialects() -> dict[str, Any]:
    """Get list of supported SQL dialects for translation."""
    return get_dialect_info()


def translate_query(
    sql: str,
    source_backend: str,
    target_backend: str,
) -> str:
    """
    Translate SQL from one backend to another.

    Args:
        sql: SQL query to translate
        source_backend: Source backend name
        target_backend: Target backend name

    Returns:
        Translated SQL string

    Raises:
        ValueError: If backend not found
    """
    source = get_backend(source_backend)
    target = get_backend(target_backend)

    return translate_sql(sql, source.dialect, target.dialect)


# Initialize default backends
def initialize_backends() -> None:
    """Initialize and register default backends."""
    # BigQuery
    try:
        bigquery_backend = BigQueryBackend()
        register_backend(bigquery_backend)
    except Exception as e:
        logger.warning(f"BigQuery backend init failed: {e}")

    # Snowflake
    try:
        snowflake_backend = SnowflakeBackend()
        register_backend(snowflake_backend)
    except Exception as e:
        logger.warning(f"Snowflake backend init failed: {e}")

    # DuckDB (always available - embedded)
    try:
        duckdb_backend = DuckDBBackend()
        register_backend(duckdb_backend)
        logger.info("DuckDB backend always available (embedded)")
    except Exception as e:
        logger.error(f"DuckDB backend init failed: {e}")


# Auto-initialize on module import
initialize_backends()
