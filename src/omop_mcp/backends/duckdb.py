"""DuckDB backend for OMOP queries."""

from __future__ import annotations  # type: ignore[annotation-unchecked]

import logging
from typing import Any

import duckdb

from omop_mcp.backends.base import Backend, CohortQueryParts
from omop_mcp.backends.dialect import translate_sql
from omop_mcp.config import config
from omop_mcp.models import SQLValidationResult

logger = logging.getLogger(__name__)


class DuckDBBackend(Backend):
    """DuckDB implementation of Backend protocol."""

    name: str = "duckdb"
    dialect: str = "duckdb"

    def __init__(self):
        """Initialize DuckDB backend."""
        self.database_path = config.duckdb_database_path
        self.schema = config.duckdb_schema
        self._conn: Any = None  # type: ignore[assignment]

        logger.info(f"DuckDB backend initialized (database={self.database_path})")

    def _get_connection(self) -> Any:  # type: ignore[return]
        """Get or create DuckDB connection."""
        if self._conn is None:
            self._conn = duckdb.connect(self.database_path)
            # Set schema if not default
            if self.schema != "main":
                self._conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")
                self._conn.execute(f"SET schema = {self.schema}")

        return self._conn

    async def build_cohort_sql(
        self,
        exposure_ids: list[int],
        outcome_ids: list[int],
        pre_outcome_days: int,
        cdm: str = "5.4",
    ) -> CohortQueryParts:
        """Build DuckDB cohort SQL."""
        exposure_list = ",".join(map(str, exposure_ids))
        outcome_list = ",".join(map(str, outcome_ids))

        exposure_cte = f"""WITH exposure AS (
  SELECT DISTINCT
    person_id,
    drug_exposure_start_date AS exposure_date
  FROM {self.qualified_table("drug_exposure")}
  WHERE drug_concept_id IN ({exposure_list})
)"""

        outcome_cte = f"""outcome AS (
  SELECT DISTINCT
    person_id,
    condition_start_date AS outcome_date
  FROM {self.qualified_table("condition_occurrence")}
  WHERE condition_concept_id IN ({outcome_list})
)"""

        # DuckDB uses date_diff() function
        cohort_cte = f"""cohort AS (
  SELECT
    e.person_id,
    e.exposure_date,
    o.outcome_date,
    date_diff('day', e.exposure_date, o.outcome_date) AS days_to_outcome
  FROM exposure e
  INNER JOIN outcome o ON e.person_id = o.person_id
  WHERE e.exposure_date <= o.outcome_date
    AND date_diff('day', e.exposure_date, o.outcome_date) <= {pre_outcome_days}
)"""

        # DuckDB supports QUALIFY like BigQuery/Snowflake
        final_select = """SELECT * FROM cohort
QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY exposure_date) = 1"""

        return CohortQueryParts(
            exposure_cte=exposure_cte,
            outcome_cte=outcome_cte,
            cohort_cte=cohort_cte,
            final_select=final_select,
        )

    async def validate_sql(self, sql: str) -> SQLValidationResult:
        """Validate SQL query using DuckDB's EXPLAIN."""
        try:
            with self._get_connection() as conn:
                # Use EXPLAIN to validate without executing
                _ = conn.execute(f"EXPLAIN {sql}").fetchall()  # Consume result
                return SQLValidationResult(valid=True)
        except Exception as e:
            return SQLValidationResult(valid=False, error_message=str(e))

    async def execute_query(self, sql: str, limit: int = 1000) -> list[dict[str, Any]]:
        """Execute SQL and return results."""
        # Security: block mutating queries (except CREATE for setup)
        sql_upper = sql.upper()
        dangerous_keywords = ["DELETE", "UPDATE", "DROP", "TRUNCATE", "ALTER"]
        if any(kw in sql_upper for kw in dangerous_keywords):
            # Allow CREATE for table setup
            if "CREATE" not in sql_upper:
                raise ValueError("Mutating queries not allowed")

        # Safety: add LIMIT if not present
        if "LIMIT" not in sql_upper:
            sql = f"{sql}\nLIMIT {limit}"

        logger.info(f"Executing query on DuckDB (limit={limit})")

        try:
            conn = self._get_connection()

            result = conn.execute(sql)
            columns = [desc[0] for desc in result.description]
            rows = [dict(zip(columns, row, strict=False)) for row in result.fetchall()]

            logger.info(f"Query executed successfully, returned {len(rows)} rows")

            return rows

        except Exception as e:
            logger.error(f"Query execution failed on DuckDB: {e}")
            raise

    def qualified_table(self, table: str) -> str:
        """Return DuckDB-style qualified table name."""
        if self.schema == "main":
            return table
        return f"{self.schema}.{table}"

    def age_calculation_sql(self, birth_col: str = "birth_datetime") -> str:
        """Return DuckDB-specific age calculation."""
        return f"date_diff('year', {birth_col}, current_date)"

    def translate_from_bigquery(self, sql: str) -> str:
        """Translate BigQuery SQL to DuckDB SQL."""
        return translate_sql(sql, source_dialect="bigquery", target_dialect="duckdb")

    def close(self) -> None:
        """Close DuckDB connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            logger.info("DuckDB connection closed")
