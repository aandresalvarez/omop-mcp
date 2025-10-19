"""Snowflake backend for OMOP queries."""

from __future__ import annotations

import logging
from typing import Any

import snowflake.connector
from snowflake.connector.errors import DatabaseError, ProgrammingError

from omop_mcp.backends.base import Backend, CohortQueryParts
from omop_mcp.backends.dialect import translate_sql
from omop_mcp.config import config
from omop_mcp.models import SQLValidationResult

logger = logging.getLogger(__name__)


class SnowflakeBackend(Backend):
    """Snowflake implementation of Backend protocol."""

    name: str = "snowflake"
    dialect: str = "snowflake"

    def __init__(self):
        """Initialize Snowflake backend."""
        self.account = config.snowflake_account
        self.user = config.snowflake_user
        self.password = config.snowflake_password
        self.database = config.snowflake_database
        self.schema = config.snowflake_schema
        self.warehouse = config.snowflake_warehouse

        if not all([self.account, self.user, self.database, self.schema]):
            logger.warning("Snowflake not fully configured - some parameters missing")

    def _get_connection(self) -> snowflake.connector.SnowflakeConnection:
        """Create Snowflake connection."""
        return snowflake.connector.connect(
            account=self.account,
            user=self.user,
            password=self.password,
            database=self.database,
            schema=self.schema,
            warehouse=self.warehouse,
        )

    async def build_cohort_sql(
        self,
        exposure_ids: list[int],
        outcome_ids: list[int],
        pre_outcome_days: int,
        cdm: str = "5.4",
    ) -> CohortQueryParts:
        """Build Snowflake cohort SQL."""
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

        # Snowflake uses DATEDIFF(DAY, date1, date2) instead of DATE_DIFF
        cohort_cte = f"""cohort AS (
  SELECT
    e.person_id,
    e.exposure_date,
    o.outcome_date,
    DATEDIFF(DAY, e.exposure_date, o.outcome_date) AS days_to_outcome
  FROM exposure e
  INNER JOIN outcome o ON e.person_id = o.person_id
  WHERE e.exposure_date <= o.outcome_date
    AND DATEDIFF(DAY, e.exposure_date, o.outcome_date) <= {pre_outcome_days}
)"""

        # Snowflake uses QUALIFY with ROW_NUMBER() like BigQuery
        final_select = """SELECT * FROM cohort
QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY exposure_date) = 1"""

        return CohortQueryParts(
            exposure_cte=exposure_cte,
            outcome_cte=outcome_cte,
            cohort_cte=cohort_cte,
            final_select=final_select,
        )

    async def validate_sql(self, sql: str) -> SQLValidationResult:
        """Validate SQL query using Snowflake's EXPLAIN."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Use EXPLAIN to validate without executing
                    cursor.execute(f"EXPLAIN {sql}")
                    _ = cursor.fetchall()  # Consume result
                    return SQLValidationResult(valid=True)
        except Exception as e:
            return SQLValidationResult(valid=False, error_message=str(e))

    async def execute_query(self, sql: str, limit: int = 1000) -> list[dict[str, Any]]:
        """Execute SQL and return results."""
        # Security: block mutating queries
        sql_upper = sql.upper()
        if any(
            kw in sql_upper
            for kw in ("DELETE", "UPDATE", "DROP", "TRUNCATE", "ALTER", "MERGE", "INSERT")
        ):
            raise ValueError("Mutating queries not allowed")

        # Safety: add LIMIT if not present
        if "LIMIT" not in sql_upper:
            sql = f"{sql}\nLIMIT {limit}"

        logger.info(f"Executing query on Snowflake (limit={limit})")

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

            cursor.close()
            conn.close()

            logger.info(f"Query executed successfully, returned {len(rows)} rows")

            return rows

        except (ProgrammingError, DatabaseError) as e:
            logger.error(f"Query execution failed on Snowflake: {e}")
            raise
        except Exception as e:
            logger.error(f"Snowflake connection failed: {e}")
            raise

    def qualified_table(self, table: str) -> str:
        """Return Snowflake-style fully qualified table name."""
        return f"{self.database}.{self.schema}.{table}"

    def age_calculation_sql(self, birth_col: str = "birth_datetime") -> str:
        """Return Snowflake-specific age calculation."""
        return f"DATEDIFF(YEAR, {birth_col}, CURRENT_DATE())"

    def translate_from_bigquery(self, sql: str) -> str:
        """Translate BigQuery SQL to Snowflake SQL."""
        return translate_sql(sql, source_dialect="bigquery", target_dialect="snowflake")
