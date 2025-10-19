"""
Integration tests for multi-step OMOP workflows.

Tests the end-to-end discover→query pattern that users will follow.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from athena_client.models import ConceptType
from omop_mcp.tools.athena import discover_concepts
from omop_mcp.tools.query import query_by_concepts


@pytest.mark.asyncio
async def test_discover_and_query_flu_workflow():
    """
    E2E test: Discover flu concepts → Query patient count.

    This is the primary workflow users will follow.
    """
    # Mock ATHENA client
    with patch("omop_mcp.tools.athena.AthenaClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock flu concept search results
        mock_flu_concept = MagicMock()
        mock_flu_concept.id = 4171852
        mock_flu_concept.name = "Influenza"
        mock_flu_concept.domain = "Condition"
        mock_flu_concept.vocabulary = "SNOMED"
        mock_flu_concept.className = "Clinical Finding"
        mock_flu_concept.standardConcept = ConceptType.STANDARD
        mock_flu_concept.code = "6142004"
        mock_flu_concept.invalidReason = None
        mock_flu_concept.score = 0.95

        mock_client.search.return_value = [mock_flu_concept]

        # Step 1: Discover concepts
        discovery_result = discover_concepts(
            query="flu",
            domain="Condition",
            standard_only=True,
            limit=10,
        )

        assert len(discovery_result.concepts) == 1
        assert discovery_result.concepts[0].concept_id == 4171852
        assert discovery_result.concepts[0].concept_name == "Influenza"

        concept_ids = [c.concept_id for c in discovery_result.concepts]

        # Step 2: Mock backend for query
        with patch("omop_mcp.tools.query.get_backend") as mock_get_backend:
            mock_backend = MagicMock()
            mock_backend.name = "bigquery"
            mock_backend.dialect = "bigquery"
            mock_backend.qualified_table = lambda t: f"`project.dataset.{t}`"
            mock_backend.age_calculation_sql = (
                lambda c: f"EXTRACT(YEAR FROM CURRENT_DATE()) - EXTRACT(YEAR FROM {c})"
            )

            # Mock validation (dry-run)
            mock_validation = MagicMock()
            mock_validation.is_valid = True
            mock_validation.estimated_cost_usd = 0.001
            mock_validation.estimated_bytes = 1024
            mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

            # Mock execution
            mock_backend.execute_query = AsyncMock(return_value=[{"patient_count": 1500}])

            mock_get_backend.return_value = mock_backend

            # Step 2a: Estimate cost (dry-run)
            estimate_result = await query_by_concepts(
                query_type="count",
                concept_ids=concept_ids,
                domain="Condition",
                backend="bigquery",
                execute=False,
            )

            assert estimate_result.sql is not None
            assert "COUNT(DISTINCT person_id)" in estimate_result.sql
            assert estimate_result.estimated_cost_usd == 0.001
            assert estimate_result.results is None

            # Step 2b: Execute query
            execution_result = await query_by_concepts(
                query_type="count",
                concept_ids=concept_ids,
                domain="Condition",
                backend="bigquery",
                execute=True,
            )

            assert execution_result.results is not None
            assert execution_result.results[0]["patient_count"] == 1500
            assert execution_result.row_count == 1


@pytest.mark.asyncio
async def test_breakdown_query_workflow():
    """
    E2E test: Discover concepts → Query demographic breakdown.
    """
    with patch("omop_mcp.tools.athena.AthenaClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock diabetes concepts
        mock_concept = MagicMock()
        mock_concept.id = 201826
        mock_concept.name = "Type 2 diabetes mellitus"
        mock_concept.domain = "Condition"
        mock_concept.vocabulary = "SNOMED"
        mock_concept.className = "Clinical Finding"
        mock_concept.standardConcept = ConceptType.STANDARD
        mock_concept.code = "44054006"
        mock_concept.invalidReason = None
        mock_concept.score = 0.98

        mock_client.search.return_value = [mock_concept]

        # Discover concepts
        discovery_result = discover_concepts(
            query="type 2 diabetes",
            domain="Condition",
            standard_only=True,
            limit=10,
        )

        concept_ids = [c.concept_id for c in discovery_result.concepts]

        # Query with breakdown
        with patch("omop_mcp.tools.query.get_backend") as mock_get_backend:
            mock_backend = MagicMock()
            mock_backend.name = "bigquery"
            mock_backend.dialect = "bigquery"
            mock_backend.qualified_table = lambda t: f"`project.dataset.{t}`"
            mock_backend.age_calculation_sql = (
                lambda c: f"EXTRACT(YEAR FROM CURRENT_DATE()) - EXTRACT(YEAR FROM {c})"
            )

            mock_validation = MagicMock()
            mock_validation.is_valid = True
            mock_validation.estimated_cost_usd = 0.05
            mock_validation.estimated_bytes = 50000
            mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

            mock_backend.execute_query = AsyncMock(
                return_value=[
                    {"gender_concept_id": 8507, "age_years": 65, "patient_count": 500},
                    {"gender_concept_id": 8532, "age_years": 62, "patient_count": 450},
                ]
            )

            mock_get_backend.return_value = mock_backend

            result = await query_by_concepts(
                query_type="breakdown",
                concept_ids=concept_ids,
                domain="Condition",
                backend="bigquery",
                execute=True,
            )

            assert result.results is not None
            assert len(result.results) == 2
            assert "gender_concept_id" in result.results[0]
            assert "age_years" in result.results[0]
            assert "patient_count" in result.results[0]


@pytest.mark.asyncio
async def test_cost_guard_workflow():
    """
    E2E test: Verify cost guard prevents expensive queries.
    """
    with patch("omop_mcp.tools.query.get_backend") as mock_get_backend:
        mock_backend = MagicMock()
        mock_backend.name = "bigquery"
        mock_backend.dialect = "bigquery"
        mock_backend.qualified_table = lambda t: f"`project.dataset.{t}`"

        # Mock expensive query
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.estimated_cost_usd = 5.0  # Over $1 limit
        mock_validation.estimated_bytes = 5000000000
        mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

        mock_get_backend.return_value = mock_backend

        # Should raise error when trying to execute
        with pytest.raises(ValueError, match="Query exceeds cost limit"):
            await query_by_concepts(
                query_type="count",
                concept_ids=[4171852, 4171853],
                domain="Condition",
                backend="bigquery",
                execute=True,
            )


@pytest.mark.asyncio
async def test_multi_backend_support():
    """
    Test that queries work with both BigQuery and Postgres backends.
    """
    concept_ids = [201826]

    # Test BigQuery
    with patch("omop_mcp.tools.query.get_backend") as mock_get_backend:
        mock_bq = MagicMock()
        mock_bq.name = "bigquery"
        mock_bq.dialect = "bigquery"
        mock_bq.qualified_table = lambda t: f"`project.dataset.{t}`"
        mock_bq.age_calculation_sql = (
            lambda c: f"EXTRACT(YEAR FROM CURRENT_DATE()) - EXTRACT(YEAR FROM {c})"
        )

        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.estimated_cost_usd = 0.01
        mock_validation.estimated_bytes = 1000
        mock_bq.validate_sql = AsyncMock(return_value=mock_validation)
        mock_bq.execute_query = AsyncMock(return_value=[{"patient_count": 100}])

        mock_get_backend.return_value = mock_bq

        bq_result = await query_by_concepts(
            query_type="count",
            concept_ids=concept_ids,
            domain="Condition",
            backend="bigquery",
            execute=True,
        )

        assert bq_result.backend == "bigquery"
        assert bq_result.dialect == "bigquery"
        assert "`project.dataset.condition_occurrence`" in bq_result.sql
        assert "condition_concept_id" in bq_result.sql

    # Test Postgres
    with patch("omop_mcp.tools.query.get_backend") as mock_get_backend:
        mock_pg = MagicMock()
        mock_pg.name = "postgres"
        mock_pg.dialect = "postgresql"
        mock_pg.qualified_table = lambda t: f"public.{t}"
        mock_pg.age_calculation_sql = lambda c: f"extract(year from age(current_date, {c}))"

        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.estimated_cost_usd = 0.0
        mock_validation.estimated_bytes = 1000
        mock_pg.validate_sql = AsyncMock(return_value=mock_validation)
        mock_pg.execute_query = AsyncMock(return_value=[{"patient_count": 100}])

        mock_get_backend.return_value = mock_pg

        pg_result = await query_by_concepts(
            query_type="count",
            concept_ids=concept_ids,
            domain="Condition",
            backend="postgres",
            execute=True,
        )

        assert pg_result.backend == "postgres"
        assert pg_result.dialect == "postgresql"
        assert "public.condition_occurrence" in pg_result.sql
        assert "condition_concept_id" in pg_result.sql


@pytest.mark.asyncio
async def test_empty_discovery_handling():
    """
    Test workflow when concept discovery returns no results.
    """
    with patch("omop_mcp.tools.athena.AthenaClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock empty search results
        mock_client.search.return_value = []

        discovery_result = discover_concepts(
            query="nonexistent disease xyz123",
            domain="Condition",
            standard_only=True,
            limit=10,
        )

        assert len(discovery_result.concepts) == 0

        # Attempting to query with empty concept list should fail
        with pytest.raises(ValueError, match="concept_ids cannot be empty"):
            await query_by_concepts(
                query_type="count",
                concept_ids=[],
                domain="Condition",
                backend="bigquery",
                execute=False,
            )


@pytest.mark.asyncio
async def test_multiple_domains_workflow():
    """
    Test discovering and querying concepts across different domains.
    """
    domains_to_test = [
        ("Condition", "condition_occurrence", "condition_concept_id"),
        ("Drug", "drug_exposure", "drug_concept_id"),
        ("Procedure", "procedure_occurrence", "procedure_concept_id"),
    ]

    for domain, expected_table, expected_col in domains_to_test:
        with patch("omop_mcp.tools.query.get_backend") as mock_get_backend:
            mock_backend = MagicMock()
            mock_backend.name = "bigquery"
            mock_backend.dialect = "bigquery"
            mock_backend.qualified_table = lambda t: f"`project.dataset.{t}`"

            mock_validation = MagicMock()
            mock_validation.is_valid = True
            mock_validation.estimated_cost_usd = 0.001
            mock_validation.estimated_bytes = 1000
            mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

            mock_get_backend.return_value = mock_backend

            result = await query_by_concepts(
                query_type="count",
                concept_ids=[12345],
                domain=domain,
                backend="bigquery",
                execute=False,
            )

            assert expected_table in result.sql
            assert expected_col in result.sql
