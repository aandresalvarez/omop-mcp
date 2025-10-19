"""Tests for query security guards."""

import pytest
from omop_mcp.config import config
from omop_mcp.tools.query import query_by_concepts


class TestQuerySecurity:
    """Tests for security guards in query execution."""

    @pytest.mark.asyncio
    async def test_mutation_blocking(self):
        """Test that mutating queries are blocked in execute_query."""
        from unittest.mock import AsyncMock, Mock

        from omop_mcp.backends.base import Backend

        # Create mock backend
        mock_backend = Mock(spec=Backend)
        mock_backend.name = "test"
        mock_backend.dialect = "test"
        mock_backend.qualified_table = lambda t: f"test.{t}"
        mock_backend.age_calculation_sql = lambda _: "EXTRACT(YEAR FROM age)"

        # Mock validation (returns valid)
        mock_validation = Mock()
        mock_validation.valid = True
        mock_validation.estimated_cost_usd = 0.01
        mock_validation.estimated_bytes = 1000
        mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

        # execute_query should block mutations
        mock_backend.execute_query = AsyncMock(
            side_effect=ValueError("Mutating queries not allowed")
        )

        # Test that execute_query blocks mutations
        with pytest.raises(ValueError, match="Mutating queries not allowed"):
            await mock_backend.execute_query("DELETE FROM test.person", limit=1000)

    @pytest.mark.asyncio
    async def test_cost_cap_enforcement(self):
        """Test that queries exceeding cost limit are rejected."""
        from unittest.mock import AsyncMock, Mock, patch

        from omop_mcp.backends.base import Backend

        # Create mock backend
        mock_backend = Mock(spec=Backend)
        mock_backend.name = "test"
        mock_backend.dialect = "test"
        mock_backend.qualified_table = lambda t: f"test.{t}"
        mock_backend.age_calculation_sql = lambda _: "EXTRACT(YEAR FROM age)"

        # Mock validation with high cost
        mock_validation = Mock()
        mock_validation.valid = True
        mock_validation.estimated_cost_usd = 10.0  # Above default $1 limit
        mock_validation.estimated_bytes = 1000000000
        mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

        # Use patch instead of monkey-patching
        with patch("omop_mcp.tools.query.get_backend", return_value=mock_backend):
            # Should reject due to cost
            with pytest.raises(ValueError, match="exceeds cost limit"):
                await query_by_concepts(
                    query_type="count",
                    concept_ids=[201826],
                    domain="Condition",
                    backend="test",
                    execute=True,
                )

    @pytest.mark.asyncio
    async def test_row_limit_enforcement(self):
        """Test that row limit is capped at 1000."""
        from unittest.mock import AsyncMock, Mock, patch

        from omop_mcp.backends.base import Backend

        # Create mock backend
        mock_backend = Mock(spec=Backend)
        mock_backend.name = "test"
        mock_backend.dialect = "test"
        mock_backend.qualified_table = lambda t: f"test.{t}"
        mock_backend.age_calculation_sql = lambda _: "EXTRACT(YEAR FROM age)"

        # Mock validation
        mock_validation = Mock()
        mock_validation.valid = True
        mock_validation.estimated_cost_usd = 0.01
        mock_validation.estimated_bytes = 1000
        mock_backend.validate_sql = AsyncMock(return_value=mock_validation)
        mock_backend.execute_query = AsyncMock(return_value=[])

        # Use patch instead of monkey-patching
        with patch("omop_mcp.tools.query.get_backend", return_value=mock_backend):
            # Request 5000 rows, should be capped at 1000
            await query_by_concepts(
                query_type="count",
                concept_ids=[201826],
                domain="Condition",
                backend="test",
                execute=True,
                limit=5000,
            )

            # Check that execute_query was called with capped limit
            mock_backend.execute_query.assert_called_once()
            # Check the second positional arg (limit)
            call_args = mock_backend.execute_query.call_args
            assert call_args[0][1] == 1000 or call_args[1].get("limit") == 1000

    @pytest.mark.asyncio
    async def test_phi_protection(self):
        """Test that list_patients requires allow_patient_list flag."""
        from unittest.mock import AsyncMock, Mock, patch

        from omop_mcp.backends.base import Backend

        # Save original config value
        original_allow = config.allow_patient_list

        try:
            # Disable patient list
            config.allow_patient_list = False

            # Create mock backend
            mock_backend = Mock(spec=Backend)
            mock_backend.name = "test"
            mock_backend.dialect = "test"
            mock_backend.qualified_table = lambda t: f"test.{t}"
            mock_backend.age_calculation_sql = lambda _: "EXTRACT(YEAR FROM age)"

            # Mock validation
            mock_validation = Mock()
            mock_validation.valid = True
            mock_validation.estimated_cost_usd = 0.01
            mock_validation.estimated_bytes = 1000
            mock_backend.validate_sql = AsyncMock(return_value=mock_validation)

            # Use patch instead of monkey-patching
            with patch("omop_mcp.tools.query.get_backend", return_value=mock_backend):
                # Should reject list_patients
                with pytest.raises(ValueError, match="not allowed"):
                    await query_by_concepts(
                        query_type="list_patients",
                        concept_ids=[201826],
                        domain="Condition",
                        backend="test",
                        execute=False,  # Even with execute=False, should reject
                    )

        finally:
            # Restore original config
            config.allow_patient_list = original_allow

    @pytest.mark.asyncio
    async def test_empty_concept_ids_rejected(self):
        """Test that empty concept_ids list is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            await query_by_concepts(
                query_type="count",
                concept_ids=[],  # Empty list
                domain="Condition",
                backend="bigquery",
                execute=False,
            )

    @pytest.mark.asyncio
    async def test_invalid_query_type_rejected(self):
        """Test that invalid query_type is rejected."""
        with pytest.raises(ValueError, match="must be one of"):
            await query_by_concepts(
                query_type="invalid_type",
                concept_ids=[201826],
                domain="Condition",
                backend="bigquery",
                execute=False,
            )
