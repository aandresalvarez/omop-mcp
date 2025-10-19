"""Tests for SQL generation module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from omop_mcp.models import (
    CohortSQLResult,
    SQLValidationResult,
)

# CohortQueryParts is not directly used in tests - we mock the backend
from omop_mcp.tools.sqlgen import (
    format_sql,
    generate_cohort_sql,
    generate_simple_query,
    validate_concept_ids,
)


class TestGenerateCohortSQL:
    """Test cohort SQL generation."""

    @pytest.mark.asyncio
    async def test_generate_cohort_sql_basic(self):
        """Test basic cohort SQL generation."""
        # Mock backend
        mock_backend = MagicMock()
        mock_backend.name = "bigquery"
        mock_backend.dialect = "bigquery"

        # Mock cohort parts
        mock_parts = MagicMock()
        mock_parts.to_sql.return_value = "SELECT * FROM cohort"
        mock_backend.build_cohort_sql = AsyncMock(return_value=mock_parts)

        # Mock validation
        mock_validation = SQLValidationResult(
            valid=True,
            error_message=None,
            estimated_cost_usd=0.01,
        )
        mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

        with patch("omop_mcp.tools.sqlgen.get_backend", return_value=mock_backend):
            result = await generate_cohort_sql(
                exposure_concept_ids=[1234],
                outcome_concept_ids=[5678],
                time_window_days=90,
                backend="bigquery",
                validate=True,
            )

        assert isinstance(result, CohortSQLResult)
        assert result.sql == "SELECT * FROM cohort"
        assert result.backend == "bigquery"
        assert result.dialect == "bigquery"
        assert result.concept_counts == {"exposure": 1, "outcome": 1}
        assert result.is_valid is True
        assert result.validation == mock_validation

    @pytest.mark.asyncio
    async def test_generate_cohort_sql_without_validation(self):
        """Test cohort SQL generation without validation."""
        mock_backend = MagicMock()
        mock_backend.name = "postgres"
        mock_backend.dialect = "postgresql"

        mock_parts = MagicMock()
        mock_parts.to_sql.return_value = "SELECT * FROM cohort"
        mock_backend.build_cohort_sql = AsyncMock(return_value=mock_parts)

        with patch("omop_mcp.tools.sqlgen.get_backend", return_value=mock_backend):
            result = await generate_cohort_sql(
                exposure_concept_ids=[1234, 5678],
                outcome_concept_ids=[9012],
                time_window_days=180,
                backend="postgres",
                validate=False,
            )

        assert result.validation is None
        assert result.is_valid is False  # is_valid is False when validation is None
        assert result.concept_counts == {"exposure": 2, "outcome": 1}
        mock_backend.validate_sql.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_cohort_sql_validation_failure(self):
        """Test cohort SQL generation with validation failure."""
        mock_backend = MagicMock()
        mock_backend.name = "bigquery"
        mock_backend.dialect = "bigquery"

        mock_parts = MagicMock()
        mock_parts.to_sql.return_value = "SELECT * FROM invalid_table"
        mock_backend.build_cohort_sql = AsyncMock(return_value=mock_parts)

        mock_validation = SQLValidationResult(
            valid=False,
            error_message="Table not found: invalid_table",
        )
        mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

        with patch("omop_mcp.tools.sqlgen.get_backend", return_value=mock_backend):
            result = await generate_cohort_sql(
                exposure_concept_ids=[1234],
                outcome_concept_ids=[5678],
                time_window_days=90,
                backend="bigquery",
                validate=True,
            )

        assert result.is_valid is False
        assert result.validation is not None
        assert result.validation.valid is False
        assert result.validation.error_message is not None
        assert "Table not found" in result.validation.error_message

    @pytest.mark.asyncio
    async def test_generate_cohort_sql_backend_error(self):
        """Test cohort SQL generation with backend error."""
        mock_backend = MagicMock()
        mock_backend.build_cohort_sql = AsyncMock(side_effect=ValueError("Invalid concept IDs"))

        with patch("omop_mcp.tools.sqlgen.get_backend", return_value=mock_backend):
            with pytest.raises(ValueError, match="exposure_concept_ids cannot be empty"):
                await generate_cohort_sql(
                    exposure_concept_ids=[],
                    outcome_concept_ids=[5678],
                    time_window_days=90,
                )


class TestGenerateSimpleQuery:
    """Test simple query generation."""

    @pytest.mark.asyncio
    async def test_generate_count_query(self):
        """Test count query generation."""
        mock_backend = MagicMock()
        mock_backend.name = "bigquery"
        mock_backend.dialect = "bigquery"
        mock_backend.build_simple_query = AsyncMock(
            return_value="SELECT COUNT(*) FROM drug_exposure WHERE drug_concept_id IN (1234)"
        )

        mock_validation = SQLValidationResult(
            valid=True,
            error_message=None,
            estimated_cost_usd=0.01,
        )
        mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

        with patch("omop_mcp.tools.sqlgen.get_backend", return_value=mock_backend):
            result = await generate_simple_query(
                query_type="count",
                concept_ids=[1234],
                domain="drug",
                backend="bigquery",
                validate=True,
            )

        assert "sql" in result
        assert "validation" in result
        assert result["validation"]["valid"] is True
        assert result["backend"] == "bigquery"
        assert result["dialect"] == "bigquery"

    @pytest.mark.asyncio
    async def test_generate_breakdown_query(self):
        """Test breakdown query generation."""
        mock_backend = MagicMock()
        mock_backend.name = "postgres"
        mock_backend.dialect = "postgresql"
        mock_backend.qualified_table = MagicMock(return_value="condition_occurrence")

        with patch("omop_mcp.tools.sqlgen.get_backend", return_value=mock_backend):
            result = await generate_simple_query(
                query_type="breakdown",
                concept_ids=[1234],
                domain="condition",
                backend="postgres",
                validate=False,
            )

        assert "sql" in result
        assert "GROUP BY" in result["sql"]

    @pytest.mark.asyncio
    async def test_generate_list_query_with_limit(self):
        """Test list query generation."""
        mock_backend = MagicMock()
        mock_backend.name = "bigquery"
        mock_backend.qualified_table = MagicMock(return_value="procedure_occurrence")

        with patch("omop_mcp.tools.sqlgen.get_backend", return_value=mock_backend):
            result = await generate_simple_query(
                query_type="list_patients",
                concept_ids=[1234],
                domain="procedure",
                backend="bigquery",
                validate=False,
            )

        assert "sql" in result
        assert "SELECT" in result["sql"]

    @pytest.mark.asyncio
    async def test_generate_query_invalid_type(self):
        """Test query generation with invalid query type."""
        with pytest.raises(ValueError, match="Invalid query_type"):
            await generate_simple_query(
                query_type="invalid_type",
                concept_ids=[1234],
                domain="drug",
            )

    @pytest.mark.asyncio
    async def test_generate_query_empty_concepts(self):
        """Test query generation with empty concept IDs."""
        with pytest.raises(ValueError, match="concept_ids cannot be empty"):
            await generate_simple_query(
                query_type="count",
                concept_ids=[],
                domain="drug",
            )


class TestFormatSQL:
    """Test SQL formatting."""

    def test_format_sql_basic(self):
        """Test basic SQL formatting."""
        raw_sql = "SELECT * FROM person WHERE person_id = 1234"
        formatted = format_sql(raw_sql)

        assert "SELECT" in formatted
        assert "FROM" in formatted
        assert "WHERE" in formatted

    def test_format_sql_with_joins(self):
        """Test SQL formatting with joins."""
        raw_sql = """
        SELECT p.person_id, de.drug_concept_id
        FROM person p JOIN drug_exposure de ON p.person_id = de.person_id
        WHERE de.drug_concept_id IN (1234, 5678)
        """
        formatted = format_sql(raw_sql)

        assert "SELECT" in formatted
        assert "JOIN" in formatted
        # Formatted SQL should have content
        assert len(formatted) > 0

    def test_format_sql_preserves_structure(self):
        """Test that formatting preserves SQL structure."""
        raw_sql = "SELECT COUNT(*) as count FROM drug_exposure GROUP BY drug_concept_id"
        formatted = format_sql(raw_sql)

        # All keywords should still be present
        assert "SELECT" in formatted
        assert "COUNT" in formatted
        assert "FROM" in formatted
        assert "GROUP BY" in formatted

    def test_format_sql_empty_string(self):
        """Test formatting empty SQL."""
        formatted = format_sql("")
        # Empty string may be formatted with whitespace
        assert len(formatted.strip()) == 0

    def test_format_sql_already_formatted(self):
        """Test formatting already well-formatted SQL."""
        raw_sql = """
SELECT
    person_id,
    drug_concept_id
FROM
    drug_exposure
WHERE
    drug_concept_id = 1234
        """.strip()

        formatted = format_sql(raw_sql)
        # Should still be valid (even if reformatted differently)
        assert "SELECT" in formatted
        assert "person_id" in formatted


class TestValidateConceptIds:
    """Test concept ID validation."""

    def test_validate_concept_ids_valid(self):
        """Test validation with valid concept IDs."""
        concept_ids = [1234, 5678, 9012]
        is_valid, error = validate_concept_ids(concept_ids)
        assert is_valid is True
        assert error is None

    def test_validate_concept_ids_single(self):
        """Test validation with single concept ID."""
        is_valid, error = validate_concept_ids([42])
        assert is_valid is True
        assert error is None

    def test_validate_concept_ids_duplicates_allowed(self):
        """Test that duplicates are preserved."""
        concept_ids = [1234, 1234, 5678]
        is_valid, error = validate_concept_ids(concept_ids)
        assert is_valid is True
        assert error is None

    def test_validate_concept_ids_empty(self):
        """Test validation with empty list."""
        is_valid, error = validate_concept_ids([])
        assert is_valid is False
        assert error == "concept_ids cannot be empty"

    def test_validate_concept_ids_non_integer(self):
        """Test validation with non-integer values."""
        is_valid, error = validate_concept_ids([1234, "5678"])  # type: ignore
        assert is_valid is False
        assert error is not None
        assert "integers" in error

    def test_validate_concept_ids_negative(self):
        """Test validation with negative values."""
        is_valid, error = validate_concept_ids([1234, -5678, 9012])
        assert is_valid is False
        assert error is not None
        assert "positive" in error

    def test_validate_concept_ids_too_many(self):
        """Test validation with too many IDs."""
        concept_ids = list(range(1, 1002))  # 1001 valid IDs
        is_valid, error = validate_concept_ids(concept_ids)
        assert is_valid is False
        assert error is not None
        assert "1000" in error
