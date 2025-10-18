"""Tests for backend registry."""

import pytest
from omop_mcp.backends import get_backend, list_backends


def test_backend_registry_initialized():
    """Test that backend registry is initialized with BigQuery."""
    backends = list_backends()
    assert "bigquery" in backends
    assert backends["bigquery"]["dialect"] == "bigquery"


def test_get_backend_bigquery():
    """Test getting BigQuery backend."""
    backend = get_backend("bigquery")
    assert backend is not None
    # Check it has required Backend protocol methods
    assert hasattr(backend, "build_cohort_sql")
    assert hasattr(backend, "validate_sql")
    assert hasattr(backend, "execute_query")
    assert hasattr(backend, "qualified_table")
    assert hasattr(backend, "age_calculation_sql")


def test_get_backend_invalid():
    """Test getting invalid backend raises error."""
    with pytest.raises(ValueError, match="not found"):
        get_backend("invalid_backend")


def test_list_backends_returns_dict():
    """Test that list_backends returns proper structure."""
    backends = list_backends()
    assert isinstance(backends, dict)
    assert len(backends) > 0

    # Check BigQuery backend structure
    bq = backends["bigquery"]
    assert "dialect" in bq
    assert "features" in bq
    assert "name" in bq
    assert bq["dialect"] == "bigquery"
    assert "cost_estimate" in bq["features"]
