"""BigQuery backend implementation."""

import os
from typing import Any

import structlog
from google.api_core.exceptions import GoogleAPIError
from google.auth import default as google_auth_default
from google.cloud import bigquery

from omop_mcp.backends.base import Backend, CohortQueryParts
from omop_mcp.config import config
from omop_mcp.models import SQLValidationResult

logger = structlog.get_logger()


class BigQueryBackend(Backend):
    """BigQuery implementation of Backend protocol."""

    name: str = "bigquery"
    dialect: str = "bigquery"

    def __init__(self):
        """Initialize BigQuery backend."""
        self.project_id = config.bigquery_project_id
        self.dataset_id = config.bigquery_dataset_id
        self.credentials_path = config.bigquery_credentials_path

        if not self.project_id or not self.dataset_id:
            logger.warning(
                "bigquery_not_configured", msg="BigQuery project_id or dataset_id not set"
            )

    def _get_client(self) -> "bigquery.Client":
        """
        Get authenticated BigQuery client using service account or ADC.

        Authentication priority:
        1. Service account JSON file (if BIGQUERY_CREDENTIALS_PATH is set and file exists)
        2. Application Default Credentials (ADC) - user credentials, metadata service, etc.

        Returns:
            Authenticated BigQuery client

        Raises:
            ValueError: If authentication fails or project ID is not available
        """
        if self.credentials_path and os.path.exists(self.credentials_path):
            # Use service account credentials
            logger.info("using_service_account", credentials_path=self.credentials_path)
            return bigquery.Client.from_service_account_json(  # type: ignore[no-any-return]
                self.credentials_path, project=self.project_id
            )
        # Use Application Default Credentials (ADC)
        logger.info("using_adc", project_id=self.project_id)
        try:
            # Verify ADC is available and get credentials
            _, detected_project = google_auth_default()

            # Use detected project if config project is not set
            project_id = self.project_id or detected_project
            if not project_id:
                raise ValueError("No project ID available from config or ADC")

            logger.info("adc_success", project_id=project_id, detected_project=detected_project)
            return bigquery.Client(project=project_id)  # type: ignore[no-any-return]
        except Exception as e:
            logger.error("adc_auth_failed", error=str(e))
            raise ValueError(
                "Failed to authenticate with Application Default Credentials. "
                "Run 'gcloud auth application-default login' or set BIGQUERY_CREDENTIALS_PATH"
            ) from e

    async def build_cohort_sql(
        self,
        exposure_ids: list[int],
        outcome_ids: list[int],
        pre_outcome_days: int,
        cdm: str = "5.4",
    ) -> CohortQueryParts:
        """Build BigQuery cohort SQL."""
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

        cohort_cte = f"""cohort AS (
  SELECT
    e.person_id,
    e.exposure_date,
    o.outcome_date,
    DATE_DIFF(o.outcome_date, e.exposure_date, DAY) AS days_to_outcome
  FROM exposure e
  INNER JOIN outcome o ON e.person_id = o.person_id
  WHERE e.exposure_date <= o.outcome_date
    AND DATE_DIFF(o.outcome_date, e.exposure_date, DAY) <= {pre_outcome_days}
)"""

        final_select = """SELECT * FROM cohort
QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY exposure_date) = 1"""

        return CohortQueryParts(
            exposure_cte=exposure_cte,
            outcome_cte=outcome_cte,
            cohort_cte=cohort_cte,
            final_select=final_select,
        )

    async def validate_sql(self, sql: str) -> SQLValidationResult:
        """Validate SQL with BigQuery dry-run."""
        logger.info("validating_sql", backend="bigquery")

        try:
            client = self._get_client()

            job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

            query_job = client.query(sql, job_config=job_config)

            estimated_bytes = query_job.total_bytes_processed
            estimated_cost_usd = (estimated_bytes / 1e12) * 5.0  # $5 per TB

            logger.info(
                "sql_validation_success",
                estimated_bytes=estimated_bytes,
                estimated_cost_usd=estimated_cost_usd,
            )

            return SQLValidationResult(
                valid=True,
                estimated_bytes=estimated_bytes,
                estimated_cost_usd=round(estimated_cost_usd, 4),
                error_message=None,
            )

        except GoogleAPIError as e:
            logger.error("sql_validation_failed", error=str(e))

            return SQLValidationResult(
                valid=False, estimated_bytes=None, estimated_cost_usd=None, error_message=str(e)
            )

    async def execute_query(self, sql: str, limit: int = 1000) -> list[dict[str, Any]]:
        """Execute SQL and return results."""
        # Security: block mutating queries
        sql_upper = sql.upper()
        if any(
            kw in sql_upper for kw in ("DELETE", "UPDATE", "DROP", "TRUNCATE", "ALTER", "MERGE")
        ):
            raise ValueError("Mutating queries not allowed")

        # Safety: add LIMIT if not present
        if "LIMIT" not in sql_upper:
            sql = f"{sql}\nLIMIT {limit}"

        logger.info("executing_query", backend="bigquery", limit=limit)

        try:
            client = self._get_client()
            query_job = client.query(sql, timeout=config.query_timeout_sec)
            results = query_job.result()

            rows = [dict(row) for row in results]

            logger.info("query_executed", row_count=len(rows))

            return rows

        except GoogleAPIError as e:
            logger.error("query_execution_failed", error=str(e))
            raise

    def qualified_table(self, table: str) -> str:
        """Return BigQuery-style fully qualified table name."""
        return f"`{self.project_id}.{self.dataset_id}.{table}`"

    def age_calculation_sql(self, birth_col: str = "birth_datetime") -> str:
        """Return BigQuery-specific age calculation."""
        return f"EXTRACT(YEAR FROM CURRENT_DATE()) - EXTRACT(YEAR FROM {birth_col})"
