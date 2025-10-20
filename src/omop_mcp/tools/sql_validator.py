"""
Enhanced SQL validator with OMOP table allowlist and security checks.

This module provides comprehensive SQL validation for OMOP CDM queries,
including syntax validation, security checks, table allowlisting, and
column blocking for PHI protection.
"""

from typing import Any

import structlog
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from omop_mcp.backends.registry import get_backend
from omop_mcp.config import config
from omop_mcp.models import SQLValidationResult

logger = structlog.get_logger(__name__)


class SQLValidationError(Exception):
    """Base exception for SQL validation errors."""

    pass


class SecurityViolationError(SQLValidationError):
    """Raised when dangerous SQL operations are detected."""

    pass


class TableNotAllowedError(SQLValidationError):
    """Raised when accessing non-allowlisted tables."""

    pass


class ColumnBlockedError(SQLValidationError):
    """Raised when accessing blocked PHI columns."""

    pass


class CostLimitExceededError(SQLValidationError):
    """Raised when query cost exceeds configured limit."""

    pass


class SQLSyntaxError(SQLValidationError):
    """Raised when SQL syntax is invalid."""

    pass


def extract_table_names(sql: str) -> set[str]:
    """
    Extract table names from SQL query.

    Args:
        sql: SQL query string

    Returns:
        Set of table names referenced in the query
    """
    try:
        parsed = parse_one(sql)
        if not parsed:
            return set()

        tables = set()

        # Extract table names from FROM clauses
        for table in parsed.find_all(exp.Table):
            if hasattr(table, "alias") and table.alias:
                # Use table name, not alias
                if hasattr(table, "name") and table.name:
                    table_name = table.name
                else:
                    continue
            elif hasattr(table, "name") and table.name:
                table_name = table.name
            else:
                continue
            tables.add(table_name.lower())

        return tables
    except Exception as e:
        logger.warning("Failed to extract table names", error=str(e), sql=sql[:100])
        return set()


def extract_column_names(sql: str) -> set[str]:
    """
    Extract column names from SQL query.

    Args:
        sql: SQL query string

    Returns:
        Set of column names referenced in the query
    """
    try:
        parsed = parse_one(sql)
        if not parsed:
            return set()

        columns = set()

        # Extract column names from SELECT clauses
        for column in parsed.find_all(exp.Column):
            if hasattr(column, "name") and column.name:
                columns.add(column.name.lower())

        return columns
    except Exception as e:
        logger.warning("Failed to extract column names", error=str(e), sql=sql[:100])
        return set()


def validate_sql_syntax(sql: str | None) -> None:
    """
    Validate SQL syntax using SQLGlot.

    Args:
        sql: SQL query string

    Raises:
        SQLSyntaxError: If SQL syntax is invalid
    """
    if not sql or not sql.strip():
        raise SQLSyntaxError("Empty or invalid SQL query")

    try:
        parsed = parse_one(sql)
        if not parsed:
            raise SQLSyntaxError("Empty or invalid SQL query")
    except ParseError as e:
        raise SQLSyntaxError(f"Invalid SQL syntax: {e}") from e


def validate_security(sql: str) -> None:
    """
    Validate SQL for security violations.

    Args:
        sql: SQL query string

    Raises:
        SecurityViolationError: If dangerous operations are detected
    """
    sql_upper = sql.upper()

    # Block dangerous keywords
    dangerous_keywords = [
        "DELETE",
        "UPDATE",
        "DROP",
        "TRUNCATE",
        "ALTER",
        "INSERT",
        "MERGE",
        "CREATE",
        "REPLACE",
    ]

    for keyword in dangerous_keywords:
        if keyword in sql_upper:
            raise SecurityViolationError(f"Operation '{keyword}' not allowed")

    # Ensure it's a read-only statement (SELECT, WITH, or other read-only patterns)
    sql_stripped = sql_upper.strip()
    read_only_patterns = ["SELECT", "WITH"]

    if not any(sql_stripped.startswith(pattern) for pattern in read_only_patterns):
        raise SecurityViolationError("Only SELECT and WITH (CTE) statements are allowed")


def validate_table_allowlist(sql: str) -> None:
    """
    Validate that only allowlisted OMOP tables are accessed.

    Args:
        sql: SQL query string

    Raises:
        TableNotAllowedError: If non-allowlisted table is accessed
    """
    if not config.strict_table_validation:
        return

    tables = extract_table_names(sql)
    allowed_tables = {table.lower() for table in config.omop_allowed_tables}

    for table in tables:
        if table not in allowed_tables:
            raise TableNotAllowedError(
                f"Table '{table}' not in allowlist. "
                f"Allowed tables: {', '.join(sorted(allowed_tables))}"
            )


def validate_column_blocklist(sql: str) -> None:
    """
    Validate that blocked PHI columns are not accessed.

    Args:
        sql: SQL query string

    Raises:
        ColumnBlockedError: If blocked column is accessed
    """
    columns = extract_column_names(sql)
    blocked_columns = {col.lower() for col in config.omop_blocked_columns}

    for column in columns:
        if column in blocked_columns:
            raise ColumnBlockedError(
                f"Column '{column}' contains PHI and is blocked. "
                f"Blocked columns: {', '.join(sorted(blocked_columns))}"
            )


def validate_row_limit(sql: str, limit: int = 1000) -> str:
    """
    Ensure SQL query has appropriate row limit.

    Args:
        sql: SQL query string
        limit: Maximum number of rows to return

    Returns:
        SQL query with LIMIT clause if not present
    """
    sql_upper = sql.upper()

    # Check if LIMIT is already present
    if "LIMIT" in sql_upper:
        return sql

    # Add LIMIT clause
    return f"{sql.rstrip()}\nLIMIT {limit}"


async def validate_sql_comprehensive(
    sql: str, backend_name: str = "bigquery", limit: int = 1000, check_cost: bool = True
) -> SQLValidationResult:
    """
    Perform comprehensive SQL validation.

    Args:
        sql: SQL query string
        backend_name: Database backend name
        limit: Maximum number of rows to return
        check_cost: Whether to check query cost

    Returns:
        SQLValidationResult with validation status and metadata

    Raises:
        SQLValidationError: If validation fails
    """
    logger.info("validating_sql", sql_length=len(sql), backend=backend_name)

    try:
        # 1. Syntax validation
        validate_sql_syntax(sql)

        # 2. Security validation
        validate_security(sql)

        # 3. Table allowlist validation
        validate_table_allowlist(sql)

        # 4. Column blocklist validation
        validate_column_blocklist(sql)

        # 5. Row limit enforcement
        sql_with_limit = validate_row_limit(sql, limit)

        # 6. Backend-specific validation (cost, etc.)
        estimated_cost = 0.0
        estimated_bytes = 0

        if check_cost and backend_name == "bigquery":
            try:
                backend = get_backend(backend_name)
                validation = await backend.validate_sql(sql_with_limit)

                if not validation.valid:
                    return SQLValidationResult(
                        valid=False,
                        error_message=validation.error_message,
                        estimated_cost_usd=0.0,
                        estimated_bytes=0,
                    )

                estimated_cost = validation.estimated_cost_usd or 0.0
                estimated_bytes = validation.estimated_bytes or 0

                # Check cost limit
                if estimated_cost > config.max_query_cost_usd:
                    raise CostLimitExceededError(
                        f"Query cost ${estimated_cost:.4f} exceeds limit "
                        f"${config.max_query_cost_usd:.4f}"
                    )

            except SQLValidationError:
                # Re-raise validation errors to be handled by outer try-catch
                raise
            except Exception as e:
                logger.warning("Backend validation failed", error=str(e))
                # Continue with basic validation if backend validation fails

        logger.info(
            "sql_validation_success", estimated_cost=estimated_cost, estimated_bytes=estimated_bytes
        )

        return SQLValidationResult(
            valid=True,
            error_message=None,
            estimated_cost_usd=estimated_cost,
            estimated_bytes=estimated_bytes,
        )

    except SQLValidationError as e:
        logger.error("sql_validation_failed", error=str(e), sql=sql[:100])
        return SQLValidationResult(
            valid=False, error_message=str(e), estimated_cost_usd=0.0, estimated_bytes=0
        )
    except Exception as e:
        logger.error("sql_validation_error", error=str(e), sql=sql[:100])
        return SQLValidationResult(
            valid=False,
            error_message=f"Validation error: {str(e)}",
            estimated_cost_usd=0.0,
            estimated_bytes=0,
        )


def get_omop_table_info() -> dict[str, Any]:
    """
    Get information about OMOP CDM tables and their purposes.

    Returns:
        Dictionary mapping table names to descriptions
    """
    return {
        "person": "Patient demographics and basic information",
        "condition_occurrence": "Medical conditions and diagnoses",
        "drug_exposure": "Medication records and prescriptions",
        "procedure_occurrence": "Medical procedures and interventions",
        "measurement": "Lab values, vital signs, and measurements",
        "observation": "Clinical observations and assessments",
        "visit_occurrence": "Healthcare encounters and visits",
        "death": "Mortality data and cause of death",
        "location": "Geographic locations and addresses",
        "care_site": "Healthcare facilities and organizations",
        "provider": "Healthcare providers and clinicians",
        "concept": "OMOP concept definitions and metadata",
        "vocabulary": "Vocabulary system metadata",
        "concept_relationship": "Concept mappings and relationships",
        "concept_ancestor": "Concept hierarchy and ancestry",
    }


def get_blocked_column_info() -> dict[str, str]:
    """
    Get information about blocked columns and why they're blocked.

    Returns:
        Dictionary mapping column names to blocking reasons
    """
    return {
        "person_source_value": "Contains raw patient identifiers from source systems",
        "provider_source_value": "Contains raw provider identifiers from source systems",
        "location_source_value": "Contains raw location identifiers from source systems",
        "care_site_source_value": "Contains raw facility identifiers from source systems",
    }
