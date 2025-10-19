"""Backend implementations for database abstraction."""

from omop_mcp.backends.base import Backend, CohortQueryParts
from omop_mcp.backends.bigquery import BigQueryBackend
from omop_mcp.backends.dialect import (
    format_sql,
    get_dialect_info,
    translate_sql,
    validate_sql,
)
from omop_mcp.backends.duckdb import DuckDBBackend
from omop_mcp.backends.registry import (
    get_backend,
    get_supported_dialects,
    list_backends,
    translate_query,
)
from omop_mcp.backends.snowflake import SnowflakeBackend

__all__ = [
    "Backend",
    "CohortQueryParts",
    "BigQueryBackend",
    "SnowflakeBackend",
    "DuckDBBackend",
    "get_backend",
    "list_backends",
    "get_supported_dialects",
    "translate_query",
    "translate_sql",
    "validate_sql",
    "format_sql",
    "get_dialect_info",
]
