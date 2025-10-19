"""
Analytical query tools for OMOP CDM data.

Provides safe query execution with security guards:
- Cost validation before execution
- Mutation blocking (no DELETE/UPDATE/DROP)
- Row limits (max 1000)
- PHI protection (list_patients requires flag)
"""

from datetime import datetime

import structlog

from omop_mcp.backends.registry import get_backend
from omop_mcp.config import config
from omop_mcp.models import QueryOMOPResult

logger = structlog.get_logger(__name__)

# Map OMOP domains to tables
TABLE_BY_DOMAIN = {
    "Condition": "condition_occurrence",
    "Drug": "drug_exposure",
    "Procedure": "procedure_occurrence",
    "Measurement": "measurement",
    "Observation": "observation",
}


def _concept_col(domain: str) -> str:
    """Get concept_id column name for domain."""
    domain_lower = domain.lower()
    if domain_lower == "condition":
        return "condition_concept_id"
    elif domain_lower == "drug":
        return "drug_concept_id"
    elif domain_lower == "procedure":
        return "procedure_concept_id"
    elif domain_lower == "measurement":
        return "measurement_concept_id"
    elif domain_lower == "observation":
        return "observation_concept_id"
    else:
        return "condition_concept_id"  # Default fallback


async def query_by_concepts(
    query_type: str,
    concept_ids: list[int],
    domain: str,
    backend: str,
    execute: bool,
    limit: int = 1000,
) -> QueryOMOPResult:
    """
    Execute analytical queries against OMOP CDM.

    Args:
        query_type: "count", "breakdown", or "list_patients"
        concept_ids: List of OMOP concept IDs
        domain: OMOP domain (Condition, Drug, Procedure, Measurement, Observation)
        backend: Backend name ("bigquery", "postgres")
        execute: Execute query or return SQL only
        limit: Maximum rows (capped at 1000)

    Returns:
        QueryOMOPResult with SQL, results, and metadata

    Raises:
        ValueError: If query_type invalid, concept_ids empty, or security check fails
    """
    # Validation
    if not concept_ids:
        raise ValueError("concept_ids cannot be empty")

    if query_type not in ["count", "breakdown", "list_patients"]:
        raise ValueError("query_type must be one of: count, breakdown, list_patients")

    # Security: cap limit
    if limit > 1000:
        logger.warning("query_limit_capped", requested=limit, capped_to=1000)
        limit = 1000

    logger.info(
        "query_by_concepts_called",
        query_type=query_type,
        concept_count=len(concept_ids),
        domain=domain,
        backend=backend,
        execute=execute,
        limit=limit,
    )

    # Get backend
    backend_impl = get_backend(backend)

    # Get table and column names
    table = TABLE_BY_DOMAIN.get(domain, "condition_occurrence")
    col = _concept_col(domain)

    # Security: Pydantic already validated concept_ids as List[int]
    # Convert to comma-separated string for SQL
    # TODO v1.1: Refactor to parameterized queries
    concept_list = ",".join(map(str, concept_ids))

    # Generate SQL based on query type
    if query_type == "count":
        sql = f"""
SELECT COUNT(DISTINCT person_id) AS patient_count
FROM {backend_impl.qualified_table(table)}
WHERE {col} IN ({concept_list})
""".strip()

    elif query_type == "breakdown":
        sql = f"""
SELECT
  p.gender_concept_id,
  {backend_impl.age_calculation_sql("p.birth_datetime")} AS age_years,
  COUNT(DISTINCT p.person_id) AS patient_count
FROM {backend_impl.qualified_table(table)} t
JOIN {backend_impl.qualified_table("person")} p ON t.person_id = p.person_id
WHERE t.{col} IN ({concept_list})
GROUP BY 1, 2
ORDER BY patient_count DESC
LIMIT {limit}
""".strip()

    elif query_type == "list_patients":
        # Security: PHI protection
        if not config.allow_patient_list:
            raise ValueError(
                "list_patients query type not allowed. "
                "Set ALLOW_PATIENT_LIST=true in environment to enable."
            )

        sql = f"""
SELECT DISTINCT person_id
FROM {backend_impl.qualified_table(table)}
WHERE {col} IN ({concept_list})
LIMIT {limit}
""".strip()

    else:
        raise ValueError(f"Invalid query_type: {query_type}")

    logger.info("sql_generated", query_type=query_type, sql_length=len(sql))

    # Validate SQL (dry-run)
    validation = await backend_impl.validate_sql(sql)

    if not validation.valid:
        logger.error(
            "sql_validation_failed",
            query_type=query_type,
            error=validation.error_message,
        )
        return QueryOMOPResult(
            sql=sql,
            results=None,
            row_count=None,
            estimated_cost_usd=None,
            estimated_bytes=None,
            backend=backend_impl.name,
            dialect=backend_impl.dialect,
            timestamp=datetime.now(),
        )

    # Check cost limit if executing
    results = None
    row_count = None

    if execute:
        # Security: enforce cost cap
        estimated_cost = validation.estimated_cost_usd or 0.0
        if estimated_cost > config.max_query_cost_usd:
            raise ValueError(
                f"Query exceeds cost limit. "
                f"Estimated: ${estimated_cost:.4f}, "
                f"Limit: ${config.max_query_cost_usd:.4f}. "
                f"Set execute=false to fetch SQL only."
            )

        logger.info(
            "executing_query",
            query_type=query_type,
            estimated_cost_usd=estimated_cost,
            estimated_bytes=validation.estimated_bytes,
        )

        # Execute with security guards (mutation blocking, LIMIT injection)
        results = await backend_impl.execute_query(sql, limit)
        row_count = len(results)

        logger.info(
            "query_executed",
            query_type=query_type,
            row_count=row_count,
            estimated_cost_usd=estimated_cost,
        )

    return QueryOMOPResult(
        sql=sql,
        results=results,
        row_count=row_count,
        estimated_cost_usd=validation.estimated_cost_usd,
        estimated_bytes=validation.estimated_bytes,
        backend=backend_impl.name,
        dialect=backend_impl.dialect,
        timestamp=datetime.now(),
    )
