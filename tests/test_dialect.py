"""Tests for SQL dialect translation and new backends."""

import pytest
from omop_mcp.backends import (
    DuckDBBackend,
    SnowflakeBackend,
    format_sql,
    get_dialect_info,
    get_supported_dialects,
    translate_query,
    translate_sql,
    validate_sql,
)
from omop_mcp.backends.dialect import SQLDialectError


class TestSQLDialectTranslation:
    """Tests for SQL dialect translation utilities."""

    def test_get_dialect_info(self):
        """Test getting dialect information."""
        info = get_dialect_info()

        assert "supported_dialects" in info
        assert "dialect_aliases" in info
        assert "total_count" in info

        # Should support major dialects
        dialects = info["supported_dialects"]
        assert "bigquery" in dialects
        assert "snowflake" in dialects
        assert "duckdb" in dialects
        assert "postgres" in dialects

    def test_translate_sql_basic(self):
        """Test basic SQL translation between dialects."""
        # Simple SELECT should work across dialects
        sql = "SELECT person_id, birth_datetime FROM person"

        translated = translate_sql(sql, "bigquery", "postgres")

        assert "SELECT" in translated
        assert "person_id" in translated
        assert "FROM person" in translated

    def test_translate_sql_date_functions(self):
        """Test translating date functions between dialects."""
        # BigQuery DATE_DIFF function
        bigquery_sql = "SELECT DATE_DIFF(date2, date1, DAY) FROM events"

        # Translate to Snowflake (uses DATEDIFF)
        snowflake_sql = translate_sql(bigquery_sql, "bigquery", "snowflake")

        assert "DATEDIFF" in snowflake_sql or "DATE_DIFF" in snowflake_sql

    def test_translate_sql_same_dialect(self):
        """Test that translation between same dialect returns original."""
        sql = "SELECT * FROM users"

        translated = translate_sql(sql, "bigquery", "bigquery")

        assert "SELECT" in translated
        assert "FROM users" in translated

    def test_translate_sql_invalid_source_dialect(self):
        """Test that invalid source dialect raises error."""
        with pytest.raises(ValueError, match="Unsupported source dialect"):
            translate_sql("SELECT 1", "invalid_dialect", "bigquery")

    def test_translate_sql_invalid_target_dialect(self):
        """Test that invalid target dialect raises error."""
        with pytest.raises(ValueError, match="Unsupported target dialect"):
            translate_sql("SELECT 1", "bigquery", "invalid_dialect")

    def test_translate_sql_invalid_syntax(self):
        """Test that invalid SQL raises error."""
        with pytest.raises(SQLDialectError, match="Invalid"):
            translate_sql("SELECT FROM WHERE", "bigquery", "postgres")

    def test_validate_sql_valid(self):
        """Test validating valid SQL."""
        sql = "SELECT person_id, COUNT(*) FROM person GROUP BY person_id"

        is_valid, error = validate_sql(sql, "bigquery")

        assert is_valid is True
        assert error is None

    def test_validate_sql_invalid(self):
        """Test validating invalid SQL."""
        sql = "SELECT FROM WHERE"  # Invalid syntax

        is_valid, error = validate_sql(sql, "postgres")

        assert is_valid is False
        assert error is not None
        assert isinstance(error, str)

    def test_validate_sql_unsupported_dialect(self):
        """Test validation with unsupported dialect."""
        is_valid, error = validate_sql("SELECT 1", "unsupported")

        assert is_valid is False
        assert error is not None
        assert "Unsupported dialect" in error

    def test_format_sql(self):
        """Test SQL formatting."""
        sql = "select a,b,c from table1 where x=1"

        formatted = format_sql(sql, dialect="postgres")

        assert "SELECT" in formatted
        assert "\n" in formatted  # Should be pretty-printed
        assert "FROM table1" in formatted

    def test_format_sql_preserves_semantics(self):
        """Test that formatting preserves SQL semantics."""
        sql = "SELECT * FROM users WHERE age > 18 AND active = true"

        formatted = format_sql(sql)

        assert "users" in formatted
        assert "age" in formatted
        assert "18" in formatted
        assert "active" in formatted


class TestSnowflakeBackend:
    """Tests for Snowflake backend."""

    def test_snowflake_backend_initialization(self):
        """Test Snowflake backend initialization."""
        backend = SnowflakeBackend()

        assert backend.name == "snowflake"
        assert backend.dialect == "snowflake"

    def test_snowflake_qualified_table(self):
        """Test Snowflake qualified table name generation."""
        backend = SnowflakeBackend()
        backend.database = "test_db"
        backend.schema = "test_schema"

        table_name = backend.qualified_table("person")

        assert table_name == "test_db.test_schema.person"

    def test_snowflake_age_calculation(self):
        """Test Snowflake age calculation SQL."""
        backend = SnowflakeBackend()

        age_sql = backend.age_calculation_sql()

        assert "DATEDIFF" in age_sql
        assert "YEAR" in age_sql
        assert "CURRENT_DATE" in age_sql

    @pytest.mark.asyncio
    async def test_snowflake_build_cohort_sql(self):
        """Test Snowflake cohort SQL generation."""
        backend = SnowflakeBackend()
        backend.database = "omop_db"
        backend.schema = "cdm"

        parts = await backend.build_cohort_sql(
            exposure_ids=[1503297],
            outcome_ids=[443530],
            pre_outcome_days=90,
        )

        assert "WITH exposure AS" in parts.exposure_cte
        assert "1503297" in parts.exposure_cte
        assert "outcome AS" in parts.outcome_cte
        assert "443530" in parts.outcome_cte
        assert "DATEDIFF(DAY" in parts.cohort_cte  # Snowflake syntax
        assert "90" in parts.cohort_cte
        assert "QUALIFY ROW_NUMBER()" in parts.final_select

    def test_snowflake_translate_from_bigquery(self):
        """Test translating BigQuery SQL to Snowflake."""
        backend = SnowflakeBackend()
        bigquery_sql = "SELECT DATE_DIFF(date2, date1, DAY) FROM events"

        snowflake_sql = backend.translate_from_bigquery(bigquery_sql)

        assert "SELECT" in snowflake_sql
        assert "FROM events" in snowflake_sql


class TestDuckDBBackend:
    """Tests for DuckDB backend."""

    def test_duckdb_backend_initialization(self):
        """Test DuckDB backend initialization."""
        backend = DuckDBBackend()

        assert backend.name == "duckdb"
        assert backend.dialect == "duckdb"
        assert backend.database_path == ":memory:"  # Default in-memory

    def test_duckdb_qualified_table_default_schema(self):
        """Test DuckDB qualified table with default schema."""
        backend = DuckDBBackend()
        backend.schema = "main"

        table_name = backend.qualified_table("person")

        assert table_name == "person"  # No schema prefix for 'main'

    def test_duckdb_qualified_table_custom_schema(self):
        """Test DuckDB qualified table with custom schema."""
        backend = DuckDBBackend()
        backend.schema = "omop"

        table_name = backend.qualified_table("person")

        assert table_name == "omop.person"

    def test_duckdb_age_calculation(self):
        """Test DuckDB age calculation SQL."""
        backend = DuckDBBackend()

        age_sql = backend.age_calculation_sql()

        assert "date_diff" in age_sql
        assert "year" in age_sql
        assert "current_date" in age_sql

    @pytest.mark.asyncio
    async def test_duckdb_build_cohort_sql(self):
        """Test DuckDB cohort SQL generation."""
        backend = DuckDBBackend()
        backend.schema = "main"

        parts = await backend.build_cohort_sql(
            exposure_ids=[1503297, 1503298],
            outcome_ids=[443530],
            pre_outcome_days=30,
        )

        assert "WITH exposure AS" in parts.exposure_cte
        assert "1503297" in parts.exposure_cte
        assert "1503298" in parts.exposure_cte
        assert "outcome AS" in parts.outcome_cte
        assert "443530" in parts.outcome_cte
        assert "date_diff('day'" in parts.cohort_cte  # DuckDB syntax
        assert "30" in parts.cohort_cte
        assert "QUALIFY ROW_NUMBER()" in parts.final_select

    @pytest.mark.asyncio
    async def test_duckdb_validate_sql(self):
        """Test DuckDB SQL validation."""
        backend = DuckDBBackend()
        sql = "SELECT 1 AS test"

        result = await backend.validate_sql(sql)

        assert result.valid is True
        assert result.error_message is None
        assert result.estimated_cost_usd == 0.0  # DuckDB is free

    @pytest.mark.asyncio
    async def test_duckdb_validate_invalid_sql(self):
        """Test DuckDB validation with invalid SQL."""
        backend = DuckDBBackend()
        sql = "SELECT FROM WHERE"

        result = await backend.validate_sql(sql)

        assert result.valid is False
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_duckdb_execute_simple_query(self):
        """Test DuckDB query execution."""
        backend = DuckDBBackend()
        sql = "SELECT 1 AS id, 'test' AS name"

        results = await backend.execute_query(sql, limit=10)

        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["name"] == "test"

    @pytest.mark.asyncio
    async def test_duckdb_blocks_dangerous_queries(self):
        """Test that DuckDB blocks dangerous queries."""
        backend = DuckDBBackend()

        with pytest.raises(ValueError, match="Mutating queries not allowed"):
            await backend.execute_query("DELETE FROM users")

        with pytest.raises(ValueError, match="Mutating queries not allowed"):
            await backend.execute_query("DROP TABLE users")

    def test_duckdb_translate_from_bigquery(self):
        """Test translating BigQuery SQL to DuckDB."""
        backend = DuckDBBackend()
        bigquery_sql = "SELECT CURRENT_TIMESTAMP()"

        duckdb_sql = backend.translate_from_bigquery(bigquery_sql)

        assert "SELECT" in duckdb_sql

    def test_duckdb_close_connection(self):
        """Test closing DuckDB connection."""
        backend = DuckDBBackend()
        backend._get_connection()  # Create connection

        backend.close()

        assert backend._conn is None


class TestBackendRegistry:
    """Tests for backend registry with new backends."""

    def test_registry_includes_all_backends(self):
        """Test that registry includes all implemented backends."""
        from omop_mcp.backends import list_backends

        backends = list_backends()

        assert "bigquery" in backends
        assert "snowflake" in backends
        assert "duckdb" in backends

    def test_registry_backend_features(self):
        """Test that backends have correct features."""
        from omop_mcp.backends import list_backends

        backends = list_backends()

        # BigQuery features
        assert "cost_estimate" in backends["bigquery"]["features"]
        assert "dry_run" in backends["bigquery"]["features"]

        # Snowflake features
        assert "explain" in backends["snowflake"]["features"]
        assert "translate" in backends["snowflake"]["features"]

        # DuckDB features
        assert "local" in backends["duckdb"]["features"]
        assert "translate" in backends["duckdb"]["features"]

    def test_get_supported_dialects(self):
        """Test getting supported dialects from registry."""
        dialects = get_supported_dialects()

        assert "supported_dialects" in dialects
        assert len(dialects["supported_dialects"]) >= 10

    def test_translate_query_between_backends(self):
        """Test translating queries between backends via registry."""
        sql = "SELECT person_id FROM person"

        translated = translate_query(sql, "bigquery", "snowflake")

        assert "SELECT" in translated
        assert "person_id" in translated


class TestDialectCompatibility:
    """Tests for SQL dialect compatibility features."""

    def test_bigquery_to_snowflake_translation(self):
        """Test BigQuery to Snowflake SQL translation."""
        bigquery_sql = """
        SELECT
            person_id,
            DATE_DIFF(end_date, start_date, DAY) AS duration
        FROM visits
        WHERE visit_concept_id IN (9201, 9202)
        """

        snowflake_sql = translate_sql(bigquery_sql, "bigquery", "snowflake")

        assert "person_id" in snowflake_sql
        assert "FROM visits" in snowflake_sql
        assert "visit_concept_id" in snowflake_sql

    def test_bigquery_to_duckdb_translation(self):
        """Test BigQuery to DuckDB SQL translation."""
        bigquery_sql = "SELECT CURRENT_TIMESTAMP() AS now"

        duckdb_sql = translate_sql(bigquery_sql, "bigquery", "duckdb")

        assert "SELECT" in duckdb_sql
        assert "now" in duckdb_sql

    def test_roundtrip_translation(self):
        """Test that roundtrip translation preserves semantics."""
        original_sql = "SELECT person_id, COUNT(*) AS cnt FROM person GROUP BY person_id"

        # BigQuery → DuckDB → BigQuery
        step1 = translate_sql(original_sql, "bigquery", "duckdb")
        step2 = translate_sql(step1, "duckdb", "bigquery")

        # Should contain all key elements
        assert "person_id" in step2
        assert "COUNT" in step2
        assert "GROUP BY" in step2
