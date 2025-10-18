"""Backend implementations for database abstraction."""

from omop_mcp.backends.base import Backend, CohortQueryParts
from omop_mcp.backends.bigquery import BigQueryBackend
from omop_mcp.backends.registry import get_backend, list_backends

__all__ = [
    "Backend",
    "CohortQueryParts",
    "BigQueryBackend",
    "get_backend",
    "list_backends",
]
