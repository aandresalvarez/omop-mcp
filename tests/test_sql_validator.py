"""
Tests for SQL validator with OMOP table allowlist and security checks.
"""

from unittest.mock import AsyncMock, patch

import pytest
from omop_mcp.models import SQLValidationResult
from omop_mcp.tools.sql_validator import (
    ColumnBlockedError,
    SecurityViolationError,
    SQLSyntaxError,
    TableNotAllowedError,
    extract_column_names,
    extract_table_names,
    validate_column_blocklist,
    validate_row_limit,
    validate_security,
    validate_sql_comprehensive,
    validate_sql_syntax,
    validate_table_allowlist,
)


class TestSQLSyntaxValidation:
    """Test SQL syntax validation."""

    def test_valid_sql_syntax(self):
        """Test valid SQL syntax passes validation."""
        valid_sql = "SELECT * FROM person WHERE person_id = 1"
        validate_sql_syntax(valid_sql)  # Should not raise

    def test_invalid_sql_syntax(self):
        """Test invalid SQL syntax raises error."""
        invalid_sql = "SELCT * FROM person"  # Typo in SELECT
        with pytest.raises(SQLSyntaxError, match="Invalid SQL syntax"):
            validate_sql_syntax(invalid_sql)

    def test_empty_sql_raises_error(self):
        """Test empty SQL raises error."""
        with pytest.raises(SQLSyntaxError, match="Empty or invalid SQL query"):
            validate_sql_syntax("")

    def test_none_sql_raises_error(self):
        """Test None SQL raises error."""
        with pytest.raises(SQLSyntaxError, match="Empty or invalid SQL query"):
            validate_sql_syntax(None)


class TestSecurityValidation:
    """Test security validation."""

    def test_select_statement_allowed(self):
        """Test SELECT statements are allowed."""
        sql = "SELECT * FROM person"
        validate_security(sql)  # Should not raise

    def test_dangerous_keywords_blocked(self):
        """Test dangerous keywords are blocked."""
        dangerous_queries = [
            "DELETE FROM person",
            "UPDATE person SET name = 'test'",
            "DROP TABLE person",
            "TRUNCATE person",
            "ALTER TABLE person ADD COLUMN test",
            "INSERT INTO person VALUES (1, 'test')",
            "MERGE person USING source",
            "CREATE TABLE test",
            "REPLACE INTO person VALUES (1, 'test')",
        ]

        for sql in dangerous_queries:
            with pytest.raises(SecurityViolationError, match="not allowed"):
                validate_security(sql)

    def test_case_insensitive_detection(self):
        """Test dangerous keywords detected case-insensitively."""
        sql = "delete from person"  # lowercase
        with pytest.raises(SecurityViolationError, match="not allowed"):
            validate_security(sql)

    def test_non_select_statement_blocked(self):
        """Test non-SELECT statements are blocked."""
        sql = "EXPLAIN SELECT * FROM person"
        with pytest.raises(SecurityViolationError, match="Only SELECT and WITH"):
            validate_security(sql)

    def test_cte_statements_allowed(self):
        """Test CTE (Common Table Expression) statements are allowed."""
        sql = "WITH cte AS (SELECT 1 AS x) SELECT * FROM cte"
        validate_security(sql)  # Should not raise

        sql = "WITH patients AS (SELECT person_id FROM person) SELECT COUNT(*) FROM patients"
        validate_security(sql)  # Should not raise

        sql = "WITH RECURSIVE hierarchy AS (SELECT * FROM concept) SELECT * FROM hierarchy"
        validate_security(sql)  # Should not raise


class TestTableAllowlistValidation:
    """Test OMOP table allowlist validation."""

    @patch("omop_mcp.tools.sql_validator.config")
    def test_allowed_table_passes(self, mock_config):
        """Test allowed OMOP tables pass validation."""
        mock_config.strict_table_validation = True
        mock_config.omop_allowed_tables = ["person", "condition_occurrence"]

        sql = "SELECT * FROM person"
        validate_table_allowlist(sql)  # Should not raise

    @patch("omop_mcp.tools.sql_validator.config")
    def test_non_allowed_table_raises_error(self, mock_config):
        """Test non-allowed tables raise error."""
        mock_config.strict_table_validation = True
        mock_config.omop_allowed_tables = ["person", "condition_occurrence"]

        sql = "SELECT * FROM custom_table"
        with pytest.raises(TableNotAllowedError, match="not in allowlist"):
            validate_table_allowlist(sql)

    @patch("omop_mcp.tools.sql_validator.config")
    def test_strict_validation_disabled(self, mock_config):
        """Test validation skipped when strict mode disabled."""
        mock_config.strict_table_validation = False

        sql = "SELECT * FROM any_table"
        validate_table_allowlist(sql)  # Should not raise

    @patch("omop_mcp.tools.sql_validator.config")
    def test_case_insensitive_table_names(self, mock_config):
        """Test table names compared case-insensitively."""
        mock_config.strict_table_validation = True
        mock_config.omop_allowed_tables = ["person", "condition_occurrence"]

        sql = "SELECT * FROM PERSON"  # uppercase
        validate_table_allowlist(sql)  # Should not raise


class TestColumnBlocklistValidation:
    """Test PHI column blocklist validation."""

    @patch("omop_mcp.tools.sql_validator.config")
    def test_allowed_columns_pass(self, mock_config):
        """Test allowed columns pass validation."""
        mock_config.omop_blocked_columns = ["person_source_value", "provider_source_value"]

        sql = "SELECT person_id, condition_concept_id FROM condition_occurrence"
        validate_column_blocklist(sql)  # Should not raise

    @patch("omop_mcp.tools.sql_validator.config")
    def test_blocked_columns_raise_error(self, mock_config):
        """Test blocked PHI columns raise error."""
        mock_config.omop_blocked_columns = ["person_source_value", "provider_source_value"]

        sql = "SELECT person_id, person_source_value FROM person"
        with pytest.raises(ColumnBlockedError, match="contains PHI and is blocked"):
            validate_column_blocklist(sql)

    @patch("omop_mcp.tools.sql_validator.config")
    def test_case_insensitive_column_names(self, mock_config):
        """Test column names compared case-insensitively."""
        mock_config.omop_blocked_columns = ["person_source_value"]

        sql = "SELECT PERSON_SOURCE_VALUE FROM person"  # uppercase
        with pytest.raises(ColumnBlockedError, match="contains PHI and is blocked"):
            validate_column_blocklist(sql)


class TestRowLimitValidation:
    """Test row limit validation."""

    def test_add_limit_to_query(self):
        """Test LIMIT clause added to query."""
        sql = "SELECT * FROM person"
        result = validate_row_limit(sql, limit=100)
        assert "LIMIT 100" in result

    def test_existing_limit_preserved(self):
        """Test existing LIMIT clause preserved."""
        sql = "SELECT * FROM person LIMIT 50"
        result = validate_row_limit(sql, limit=100)
        assert result == sql  # Should be unchanged

    def test_case_insensitive_limit_detection(self):
        """Test LIMIT detection case-insensitive."""
        sql = "SELECT * FROM person limit 50"  # lowercase
        result = validate_row_limit(sql, limit=100)
        assert result == sql  # Should be unchanged


class TestTableNameExtraction:
    """Test table name extraction from SQL."""

    def test_extract_simple_table(self):
        """Test extraction of simple table name."""
        sql = "SELECT * FROM person"
        tables = extract_table_names(sql)
        assert "person" in tables

    def test_extract_multiple_tables(self):
        """Test extraction of multiple table names."""
        sql = "SELECT * FROM person p JOIN condition_occurrence c ON p.person_id = c.person_id"
        tables = extract_table_names(sql)
        assert "person" in tables
        assert "condition_occurrence" in tables

    def test_extract_table_with_alias(self):
        """Test extraction handles table aliases."""
        sql = "SELECT * FROM person p"
        tables = extract_table_names(sql)
        assert "person" in tables  # Should use actual table name, not alias

    def test_extract_case_insensitive(self):
        """Test extraction handles case-insensitive table names."""
        sql = "SELECT * FROM PERSON"
        tables = extract_table_names(sql)
        assert "person" in tables  # Should be lowercase

    def test_extract_handles_parse_error(self):
        """Test extraction handles SQL parse errors gracefully."""
        sql = "INVALID SQL SYNTAX"
        tables = extract_table_names(sql)
        assert tables == set()  # Should return empty set


class TestColumnNameExtraction:
    """Test column name extraction from SQL."""

    def test_extract_simple_columns(self):
        """Test extraction of simple column names."""
        sql = "SELECT person_id, condition_concept_id FROM condition_occurrence"
        columns = extract_column_names(sql)
        assert "person_id" in columns
        assert "condition_concept_id" in columns

    def test_extract_case_insensitive(self):
        """Test extraction handles case-insensitive column names."""
        sql = "SELECT PERSON_ID FROM person"
        columns = extract_column_names(sql)
        assert "person_id" in columns  # Should be lowercase

    def test_extract_handles_parse_error(self):
        """Test extraction handles SQL parse errors gracefully."""
        sql = "INVALID SQL SYNTAX"
        columns = extract_column_names(sql)
        assert columns == set()  # Should return empty set


class TestComprehensiveValidation:
    """Test comprehensive SQL validation."""

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.sql_validator.config")
    @patch("omop_mcp.tools.sql_validator.get_backend")
    async def test_valid_query_passes(self, mock_get_backend, mock_config):
        """Test valid query passes comprehensive validation."""
        # Setup mocks
        mock_config.strict_table_validation = False
        mock_config.omop_blocked_columns = []
        mock_config.max_query_cost_usd = 1.0

        mock_backend = AsyncMock()
        mock_validation = SQLValidationResult(
            valid=True, error_message=None, estimated_cost_usd=0.01, estimated_bytes=1000000
        )
        mock_backend.validate_sql.return_value = mock_validation
        mock_get_backend.return_value = mock_backend

        sql = "SELECT COUNT(*) FROM person"
        result = await validate_sql_comprehensive(sql, "bigquery", 1000, True)

        assert result.valid is True
        assert result.error_message is None
        assert result.estimated_cost_usd == 0.01

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.sql_validator.config")
    async def test_invalid_syntax_fails(self, mock_config):
        """Test invalid SQL syntax fails validation."""
        mock_config.strict_table_validation = False
        mock_config.omop_blocked_columns = []

        sql = "SELCT * FROM person"  # Invalid syntax
        result = await validate_sql_comprehensive(sql, "bigquery", 1000, False)

        assert result.valid is False
        assert result.error_message is not None
        assert "Invalid SQL syntax" in result.error_message

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.sql_validator.config")
    async def test_security_violation_fails(self, mock_config):
        """Test security violation fails validation."""
        mock_config.strict_table_validation = False
        mock_config.omop_blocked_columns = []

        sql = "DELETE FROM person"  # Security violation
        result = await validate_sql_comprehensive(sql, "bigquery", 1000, False)

        assert result.valid is False
        assert result.error_message is not None
        assert "not allowed" in result.error_message

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.sql_validator.config")
    @patch("omop_mcp.tools.sql_validator.get_backend")
    async def test_cost_limit_exceeded(self, mock_get_backend, mock_config):
        """Test cost limit exceeded fails validation."""
        mock_config.strict_table_validation = False
        mock_config.omop_blocked_columns = []
        mock_config.max_query_cost_usd = 0.01  # Low limit

        mock_backend = AsyncMock()
        mock_validation = SQLValidationResult(
            valid=True,
            error_message=None,
            estimated_cost_usd=0.05,  # Exceeds limit
            estimated_bytes=5000000,
        )
        mock_backend.validate_sql.return_value = mock_validation
        mock_get_backend.return_value = mock_backend

        sql = "SELECT * FROM person"
        result = await validate_sql_comprehensive(sql, "bigquery", 1000, True)

        assert result.valid is False
        assert result.error_message is not None
        assert "exceeds limit" in result.error_message

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.sql_validator.config")
    async def test_backend_validation_failure(self, mock_config):
        """Test backend validation failure."""
        mock_config.strict_table_validation = False
        mock_config.omop_blocked_columns = []

        sql = "SELECT * FROM person"
        result = await validate_sql_comprehensive(sql, "duckdb", 1000, False)

        # Should pass basic validation even if backend validation fails
        assert result.valid is True
        assert result.estimated_cost_usd == 0.0


class TestErrorTypes:
    """Test custom error types."""

    def test_security_violation_error(self):
        """Test SecurityViolationError."""
        error = SecurityViolationError("Test message")
        assert str(error) == "Test message"
        assert isinstance(error, Exception)

    def test_table_not_allowed_error(self):
        """Test TableNotAllowedError."""
        error = TableNotAllowedError("Table 'test' not allowed")
        assert str(error) == "Table 'test' not allowed"
        assert isinstance(error, Exception)

    def test_column_blocked_error(self):
        """Test ColumnBlockedError."""
        error = ColumnBlockedError("Column 'test' blocked")
        assert str(error) == "Column 'test' blocked"
        assert isinstance(error, Exception)

    def test_sql_syntax_error(self):
        """Test SQLSyntaxError."""
        error = SQLSyntaxError("Invalid syntax")
        assert str(error) == "Invalid syntax"
        assert isinstance(error, Exception)
