"""Tests for OMOP MCP configuration."""

from omop_mcp.config import OMOPConfig, config


def test_config_singleton():
    """Test that config is properly initialized."""
    assert config is not None
    assert isinstance(config, OMOPConfig)


def test_config_has_required_fields():
    """Test that config has all required fields."""
    assert hasattr(config, "openai_api_key")
    assert hasattr(config, "athena_base_url")
    assert hasattr(config, "max_query_cost_usd")
    assert hasattr(config, "allow_patient_list")
    assert hasattr(config, "query_timeout_sec")


def test_config_defaults():
    """Test default configuration values."""
    assert config.athena_base_url == "https://athena.ohdsi.org/api/v1"
    assert config.max_query_cost_usd == 1.0
    assert config.allow_patient_list is False
    assert config.query_timeout_sec == 30
    assert config.max_concepts_per_query == 50


def test_config_types():
    """Test configuration field types."""
    assert isinstance(config.athena_base_url, str)
    assert isinstance(config.max_query_cost_usd, float)
    assert isinstance(config.allow_patient_list, bool)
    assert isinstance(config.query_timeout_sec, int)
    assert isinstance(config.max_concepts_per_query, int)
