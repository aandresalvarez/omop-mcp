"""
SQL generation for OMOP cohort queries.

Provides tools for generating validated SQL for cohort definitions,
including exposure→outcome temporal logic, demographic filters,
and concept-based patient selection.
"""

from datetime import datetime
from typing import Any

import structlog

from omop_mcp.backends.registry import get_backend
from omop_mcp.models import CohortSQLResult, OMOPDomain

logger = structlog.get_logger(__name__)


async def generate_cohort_sql(
    exposure_concept_ids: list[int],
    outcome_concept_ids: list[int],
    time_window_days: int = 90,
    backend: str = "bigquery",
    validate: bool = True,
) -> CohortSQLResult:
    """
    Generate SQL for cohort definition with exposure → outcome logic.

    Creates a validated SQL query for identifying patients who:
    1. Have an exposure event (e.g., drug prescription)
    2. Followed by an outcome event (e.g., adverse event)
    3. Within a specified time window

    The SQL uses OMOP CDM standard tables and includes:
    - Deduplication (first exposure per patient)
    - Temporal constraints (outcome after exposure, within window)
    - Date difference calculations
    - Backend-specific SQL dialect

    Args:
        exposure_concept_ids: OMOP concept IDs for exposure events
        outcome_concept_ids: OMOP concept IDs for outcome events
        time_window_days: Maximum days between exposure and outcome (default: 90)
        backend: Database backend ("bigquery" or "postgres")
        validate: Run dry-run validation (default: True)

    Returns:
        CohortSQLResult with:
        - sql: Generated SQL query
        - validation: Validation result (cost, bytes, etc.)
        - concept_counts: Exposure/outcome concept counts
        - backend: Backend name
        - dialect: SQL dialect
        - is_valid: Whether SQL passed validation

    Raises:
        ValueError: If concept lists empty or backend invalid

    Example:
        >>> result = await generate_cohort_sql(
        ...     exposure_concept_ids=[1503297],  # Metformin
        ...     outcome_concept_ids=[46271022],  # Acute kidney injury
        ...     time_window_days=90,
        ...     backend="bigquery"
        ... )
        >>> print(result.sql)
        >>> print(f"Valid: {result.is_valid}")
        >>> print(f"Cost: ${result.validation.estimated_cost_usd}")
    """
    if not exposure_concept_ids:
        raise ValueError("exposure_concept_ids cannot be empty")

    if not outcome_concept_ids:
        raise ValueError("outcome_concept_ids cannot be empty")

    logger.info(
        "generate_cohort_sql",
        exposure_count=len(exposure_concept_ids),
        outcome_count=len(outcome_concept_ids),
        time_window_days=time_window_days,
        backend=backend,
        validate=validate,
    )

    try:
        backend_impl = get_backend(backend)

        # Build SQL using backend
        cohort_parts = await backend_impl.build_cohort_sql(
            exposure_ids=exposure_concept_ids,
            outcome_ids=outcome_concept_ids,
            pre_outcome_days=time_window_days,
        )

        sql = cohort_parts.to_sql()

        # Validate if requested
        validation_result = None
        if validate:
            validation_result = await backend_impl.validate_sql(sql)
            logger.info(
                "sql_validated",
                is_valid=validation_result.valid,
                estimated_cost_usd=validation_result.estimated_cost_usd,
                estimated_bytes=validation_result.estimated_bytes,
            )

        result = CohortSQLResult(
            sql=sql,
            validation=validation_result,
            concept_counts={
                "exposure": len(exposure_concept_ids),
                "outcome": len(outcome_concept_ids),
            },
            backend=backend_impl.name,
            dialect=backend_impl.dialect,
        )

        logger.info(
            "cohort_sql_generated",
            backend=backend,
            is_valid=result.is_valid,
            sql_length=len(sql),
        )

        return result

    except Exception as e:
        logger.error(
            "cohort_sql_generation_failed",
            backend=backend,
            error=str(e),
            exc_info=True,
        )
        raise


async def generate_simple_query(
    concept_ids: list[int],
    domain: OMOPDomain | str,
    query_type: str = "count",
    backend: str = "bigquery",
    validate: bool = True,
) -> dict[str, Any]:
    """
    Generate simple analytical SQL query for concepts.

    Simpler alternative to cohort SQL for basic queries:
    - Patient counts
    - Demographic breakdowns
    - Concept prevalence

    Args:
        concept_ids: OMOP concept IDs to query
        domain: OMOP domain (Condition, Drug, Procedure, etc.)
        query_type: "count", "breakdown", or "list_patients"
        backend: Database backend
        validate: Run validation

    Returns:
        Dictionary with SQL, validation, and metadata

    Example:
        >>> result = await generate_simple_query(
        ...     concept_ids=[201826],  # Type 2 diabetes
        ...     domain="Condition",
        ...     query_type="count"
        ... )
        >>> print(result["sql"])
    """
    if not concept_ids:
        raise ValueError("concept_ids cannot be empty")

    if query_type not in ["count", "breakdown", "list_patients"]:
        raise ValueError(
            f"Invalid query_type: {query_type}. Must be count, breakdown, or list_patients"
        )

    logger.info(
        "generate_simple_query",
        concept_count=len(concept_ids),
        domain=domain,
        query_type=query_type,
        backend=backend,
    )

    try:
        backend_impl = get_backend(backend)

        # Convert domain to string if enum
        domain_str = domain.value if isinstance(domain, OMOPDomain) else domain

        # Map domain to table
        table_map = {
            "Condition": "condition_occurrence",
            "Drug": "drug_exposure",
            "Procedure": "procedure_occurrence",
            "Measurement": "measurement",
            "Observation": "observation",
        }

        table = table_map.get(domain_str, "condition_occurrence")
        concept_col = f"{domain_str.lower()}_concept_id"

        # Generate SQL based on query type
        concept_list = ",".join(map(str, concept_ids))

        if query_type == "count":
            sql = f"""
SELECT COUNT(DISTINCT person_id) AS patient_count
FROM {backend_impl.qualified_table(table)}
WHERE {concept_col} IN ({concept_list})
""".strip()

        elif query_type == "breakdown":
            sql = f"""
SELECT
  p.gender_concept_id,
  {backend_impl.age_calculation_sql("p.birth_datetime")} AS age_years,
  COUNT(DISTINCT p.person_id) AS patient_count
FROM {backend_impl.qualified_table(table)} t
JOIN {backend_impl.qualified_table("person")} p ON t.person_id = p.person_id
WHERE t.{concept_col} IN ({concept_list})
GROUP BY p.gender_concept_id, age_years
ORDER BY patient_count DESC
""".strip()

        else:  # list_patients
            sql = f"""
SELECT DISTINCT person_id
FROM {backend_impl.qualified_table(table)}
WHERE {concept_col} IN ({concept_list})
LIMIT 1000
""".strip()

        # Validate if requested
        validation_result = None
        if validate:
            validation_result = await backend_impl.validate_sql(sql)

        result = {
            "sql": sql,
            "validation": validation_result.model_dump() if validation_result else None,
            "concept_count": len(concept_ids),
            "domain": domain_str,
            "query_type": query_type,
            "backend": backend_impl.name,
            "dialect": backend_impl.dialect,
            "is_valid": validation_result.valid if validation_result else None,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            "simple_query_generated",
            query_type=query_type,
            sql_length=len(sql),
        )

        return result

    except Exception as e:
        logger.error(
            "simple_query_generation_failed",
            query_type=query_type,
            error=str(e),
            exc_info=True,
        )
        raise


def format_sql(sql: str, dialect: str = "bigquery") -> str:
    """
    Format SQL for readability.

    Adds proper indentation and line breaks for better readability.
    Dialect-specific formatting for BigQuery vs Postgres.

    Args:
        sql: Raw SQL string
        dialect: SQL dialect ("bigquery" or "postgres")

    Returns:
        Formatted SQL string

    Example:
        >>> sql = "SELECT * FROM table WHERE id = 1"
        >>> formatted = format_sql(sql)
        >>> print(formatted)
    """
    # Basic formatting - can be enhanced with sqlparse or similar
    sql = sql.strip()

    # Add line breaks after major keywords
    keywords = ["SELECT", "FROM", "WHERE", "JOIN", "GROUP BY", "ORDER BY", "LIMIT"]
    for keyword in keywords:
        sql = sql.replace(f" {keyword} ", f"\n{keyword} ")

    # Indent joins and conditions
    lines = sql.split("\n")
    formatted_lines = []
    indent_level = 0

    for line in lines:
        line = line.strip()
        if any(kw in line for kw in ["JOIN", "WHERE", "AND", "OR"]):
            formatted_lines.append("  " * indent_level + line)
        elif any(kw in line for kw in ["SELECT", "FROM", "GROUP BY", "ORDER BY"]):
            formatted_lines.append(line)
        else:
            formatted_lines.append("  " + line)

    return "\n".join(formatted_lines)


def validate_concept_ids(concept_ids: list[int]) -> tuple[bool, str | None]:
    """
    Validate concept IDs before SQL generation.

    Checks:
    - Non-empty list
    - All positive integers
    - Reasonable count (not too many)

    Args:
        concept_ids: List of concept IDs to validate

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> valid, error = validate_concept_ids([201826, 201254])
        >>> if not valid:
        ...     print(f"Invalid: {error}")
    """
    if not concept_ids:
        return False, "concept_ids cannot be empty"

    if not all(isinstance(cid, int) for cid in concept_ids):
        return False, "All concept IDs must be integers"

    if not all(cid > 0 for cid in concept_ids):
        return False, "All concept IDs must be positive"

    if len(concept_ids) > 1000:
        return False, "Too many concept IDs (max 1000)"

    return True, None
