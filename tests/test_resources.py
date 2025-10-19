"""
Tests for MCP resources module.
"""

from unittest.mock import MagicMock, patch

import pytest
from omop_mcp import resources
from omop_mcp.models import OMOPConcept


@pytest.fixture
def mock_athena_client():
    """Mock AthenaAPIClient for testing."""
    with patch("omop_mcp.resources.AthenaAPIClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.mark.asyncio
async def test_get_concept_resource_success(mock_athena_client):
    """Test successful concept retrieval."""
    # Mock concept response
    mock_concept = OMOPConcept(
        id=313217,
        name="Atrial fibrillation",
        domain="Condition",
        vocabulary="SNOMED",
        className="Clinical Finding",
        standardConcept="S",
        code="49436004",
        invalidReason=None,
        score=None,
    )
    mock_athena_client.get_concept_by_id.return_value = mock_concept

    # Test the resource
    result = await resources.get_concept_resource(313217)

    # Verify
    assert result["concept_id"] == 313217
    assert result["concept_name"] == "Atrial fibrillation"
    assert result["domain_id"] == "Condition"
    assert result["vocabulary_id"] == "SNOMED"
    assert result["standard_concept"] == "S"
    mock_athena_client.get_concept_by_id.assert_called_once_with(313217)


@pytest.mark.asyncio
async def test_get_concept_resource_not_found(mock_athena_client):
    """Test concept not found."""
    mock_athena_client.get_concept_by_id.return_value = None

    with pytest.raises(ValueError, match="Concept 999999 not found"):
        await resources.get_concept_resource(999999)


@pytest.mark.asyncio
async def test_get_concept_resource_invalid_id():
    """Test invalid concept ID."""
    with pytest.raises(ValueError, match="Invalid concept_id"):
        await resources.get_concept_resource(-1)


@pytest.mark.asyncio
async def test_search_concepts_resource_first_page(mock_athena_client):
    """Test paginated search - first page."""
    # Mock search results
    mock_concepts = [
        OMOPConcept(
            id=201820,
            name="Diabetes mellitus",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code="73211009",
            invalidReason=None,
            score=0.95,
        ),
        OMOPConcept(
            id=201826,
            name="Type 2 diabetes mellitus",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code="44054006",
            invalidReason=None,
            score=0.90,
        ),
    ]
    mock_athena_client.search_concepts.return_value = mock_concepts

    # Test the resource
    result = await resources.search_concepts_resource(
        query="diabetes", page_size=2, domain="Condition"
    )

    # Verify
    assert result["query"] == "diabetes"
    assert result["page_size"] == 2
    assert len(result["concepts"]) == 2
    assert result["concepts"][0]["concept_name"] == "Diabetes mellitus"
    assert result["next_cursor"] is None  # No more pages since we got all results
    assert result["total_count"] == 2


@pytest.mark.asyncio
async def test_search_concepts_resource_with_pagination(mock_athena_client):
    """Test paginated search with cursor."""
    # Mock search results - simulate 10 concepts available
    all_concepts = [
        OMOPConcept(
            id=i,
            name=f"Concept {i}",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code=str(i),
            invalidReason=None,
            score=None,
        )
        for i in range(10)
    ]
    mock_athena_client.search_concepts.return_value = all_concepts

    # First page (offset 0, page_size 3)
    result1 = await resources.search_concepts_resource(query="test", page_size=3)

    assert len(result1["concepts"]) == 3
    assert result1["concepts"][0]["concept_id"] == 0
    assert result1["next_cursor"] == "offset:3"

    # Second page (offset 3, page_size 3)
    result2 = await resources.search_concepts_resource(query="test", cursor="offset:3", page_size=3)

    assert len(result2["concepts"]) == 3
    assert result2["concepts"][0]["concept_id"] == 3
    assert result2["next_cursor"] == "offset:6"


@pytest.mark.asyncio
async def test_search_concepts_resource_invalid_cursor(mock_athena_client):
    """Test search with invalid cursor."""
    with pytest.raises(ValueError, match="Invalid cursor format"):
        await resources.search_concepts_resource(query="test", cursor="invalid")


@pytest.mark.asyncio
async def test_search_concepts_resource_page_size_cap(mock_athena_client):
    """Test page size is capped at 100."""
    mock_athena_client.search_concepts.return_value = []

    await resources.search_concepts_resource(query="test", page_size=200)

    # Should request limit of 100 (capped from 200)
    # Note: limit = offset + page_size + 100, with page_size capped at 100
    # So limit = 0 + 100 + 100 = 200
    call_args = mock_athena_client.search_concepts.call_args
    assert call_args[1]["limit"] == 200  # offset(0) + capped_page_size(100) + buffer(100)


@pytest.mark.asyncio
async def test_get_backend_capabilities():
    """Test backend capabilities listing."""
    with patch("omop_mcp.resources.list_backends") as mock_list:
        with patch("omop_mcp.resources.get_backend") as mock_get:
            # Mock backends
            mock_list.return_value = ["bigquery"]

            mock_backend = MagicMock()
            mock_backend.dialect = "bigquery"
            mock_backend.execute_query = MagicMock()
            mock_get.return_value = mock_backend

            # Test the resource
            result = await resources.get_backend_capabilities()

            # Verify
            assert result["count"] == 1
            assert result["default_backend"] == "bigquery"
            assert len(result["backends"]) == 1
            assert result["backends"][0]["name"] == "bigquery"
            assert result["backends"][0]["dialect"] == "bigquery"
            assert "dry_run" in result["backends"][0]["features"]
            assert "cost_estimate" in result["backends"][0]["features"]
            assert "execute" in result["backends"][0]["features"]


@pytest.mark.asyncio
async def test_get_backend_capabilities_unavailable_backend():
    """Test backend capabilities with unavailable backend."""
    with patch("omop_mcp.resources.list_backends") as mock_list:
        with patch("omop_mcp.resources.get_backend") as mock_get:
            # Mock backends
            mock_list.return_value = ["bigquery", "postgres"]

            def get_backend_side_effect(name):
                if name == "bigquery":
                    mock_backend = MagicMock()
                    mock_backend.dialect = "bigquery"
                    mock_backend.execute_query = MagicMock()
                    return mock_backend
                else:
                    raise RuntimeError("Postgres not configured")

            mock_get.side_effect = get_backend_side_effect

            # Test the resource
            result = await resources.get_backend_capabilities()

            # Verify - should only return available backend
            assert result["count"] == 1
            assert len(result["backends"]) == 1
            assert result["backends"][0]["name"] == "bigquery"
