"""SQL dialect translation utilities using SQLGlot.

This module provides utilities to translate SQL between different dialects
(BigQuery, Snowflake, DuckDB, PostgreSQL, etc.) and validate SQL syntax.
"""

import logging
from typing import Any

from sqlglot import exp, optimizer, parse_one
from sqlglot.errors import ParseError

logger = logging.getLogger(__name__)

# Supported SQL dialects
SUPPORTED_DIALECTS = {
    "bigquery": "bigquery",
    "snowflake": "snowflake",
    "duckdb": "duckdb",
    "postgres": "postgres",
    "postgresql": "postgres",  # Alias
    "mysql": "mysql",
    "sqlite": "sqlite",
    "redshift": "redshift",
    "spark": "spark",
    "trino": "trino",
    "presto": "presto",
}


class SQLDialectError(Exception):
    """Exception raised for SQL dialect translation errors."""

    pass


def translate_sql(
    sql: str,
    source_dialect: str,
    target_dialect: str,
    validate: bool = True,
) -> str:
    """
    Translate SQL from one dialect to another.

    Args:
        sql: SQL query to translate
        source_dialect: Source SQL dialect (e.g., "bigquery", "postgres")
        target_dialect: Target SQL dialect
        validate: Validate SQL syntax before translation

    Returns:
        Translated SQL string

    Raises:
        SQLDialectError: If translation fails
        ValueError: If dialect is not supported

    Example:
        >>> sql = "SELECT DATE_TRUNC(created_at, DAY) FROM users"
        >>> translate_sql(sql, "bigquery", "postgres")
        'SELECT DATE_TRUNC(\\'DAY\\', created_at) FROM users'
    """
    # Normalize dialect names
    source = SUPPORTED_DIALECTS.get(source_dialect.lower())
    target = SUPPORTED_DIALECTS.get(target_dialect.lower())

    if not source:
        raise ValueError(f"Unsupported source dialect: {source_dialect}")
    if not target:
        raise ValueError(f"Unsupported target dialect: {target_dialect}")

    # If same dialect, return as-is
    if source == target:
        return sql

    logger.info(f"Translating SQL from {source} to {target}")

    try:
        # Parse SQL in source dialect
        parsed = parse_one(sql, read=source)

        # Validate if requested
        if validate:
            _validate_parsed_sql(parsed, source)

        # Translate to target dialect
        translated: str = parsed.sql(dialect=target, pretty=True)

        logger.info(f"Successfully translated SQL ({len(sql)} → {len(translated)} chars)")
        return translated

    except ParseError as e:
        logger.error(f"Failed to parse SQL in {source} dialect: {e}")
        raise SQLDialectError(f"Invalid {source} SQL: {e}") from e
    except Exception as e:
        logger.error(f"SQL translation failed: {e}")
        raise SQLDialectError(f"Translation failed: {e}") from e


def validate_sql(sql: str, dialect: str) -> tuple[bool, str | None]:
    """
    Validate SQL syntax for a specific dialect.

    Args:
        sql: SQL query to validate
        dialect: SQL dialect to validate against

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> validate_sql("SELECT * FROM users", "postgres")
        (True, None)
        >>> validate_sql("SELECT FROM", "postgres")
        (False, "Expecting column or * in SELECT...")
    """
    dialect_name = SUPPORTED_DIALECTS.get(dialect.lower())
    if not dialect_name:
        return False, f"Unsupported dialect: {dialect}"

    try:
        parsed = parse_one(sql, read=dialect_name)
        _validate_parsed_sql(parsed, dialect_name)
        return True, None
    except ParseError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Validation error: {e}"


def _validate_parsed_sql(parsed: exp.Expression, dialect: str) -> None:
    """Validate parsed SQL expression."""
    # Check for common issues
    if not parsed:
        raise SQLDialectError("Empty SQL expression")

    # Ensure it's a valid statement
    if not isinstance(parsed, exp.Select | exp.Insert | exp.Update | exp.Delete | exp.Create):
        raise SQLDialectError(f"Unsupported SQL statement type: {type(parsed).__name__}")


def format_sql(sql: str, dialect: str = "bigquery", pretty: bool = True) -> str:
    """
    Format SQL for better readability.

    Args:
        sql: SQL query to format
        dialect: SQL dialect
        pretty: Use pretty printing with indentation

    Returns:
        Formatted SQL string

    Example:
        >>> format_sql("select a,b,c from t where x=1")
        'SELECT\\n  a,\\n  b,\\n  c\\nFROM t\\nWHERE\\n  x = 1'
    """
    dialect_name = SUPPORTED_DIALECTS.get(dialect.lower(), "bigquery")

    try:
        parsed = parse_one(sql, read=dialect_name)
        formatted: str = parsed.sql(dialect=dialect_name, pretty=pretty)
        return formatted
    except Exception as e:
        logger.warning(f"Failed to format SQL: {e}, returning original")
        return sql


def get_sql_tables(sql: str, dialect: str = "bigquery") -> list[str]:
    """
    Extract table names from SQL query.

    Args:
        sql: SQL query
        dialect: SQL dialect

    Returns:
        List of table names referenced in query

    Example:
        >>> get_sql_tables("SELECT * FROM dataset.table1 JOIN dataset.table2")
        ['dataset.table1', 'dataset.table2']
    """
    dialect_name = SUPPORTED_DIALECTS.get(dialect.lower(), "bigquery")

    try:
        parsed = parse_one(sql, read=dialect_name)
        tables = []

        # Find all table references
        for table in parsed.find_all(exp.Table):
            table_name = table.sql(dialect=dialect_name)
            tables.append(table_name)

        return tables
    except Exception as e:
        logger.warning(f"Failed to extract tables: {e}")
        return []


def optimize_sql(sql: str, dialect: str = "bigquery") -> str:
    """
    Apply basic SQL optimizations.

    Args:
        sql: SQL query to optimize
        dialect: SQL dialect

    Returns:
        Optimized SQL string

    Note:
        This performs basic optimizations like:
        - Removing unnecessary subqueries
        - Simplifying expressions
        - Normalizing syntax
    """
    dialect_name = SUPPORTED_DIALECTS.get(dialect.lower(), "bigquery")

    try:
        parsed = parse_one(sql, read=dialect_name)

        # Apply optimizations using simplify
        optimized = optimizer.simplify.simplify(parsed)

        result: str = optimized.sql(dialect=dialect_name, pretty=True)
        return result
    except Exception as e:
        logger.warning(f"Failed to optimize SQL: {e}, returning original")
        return sql


def get_dialect_info() -> dict[str, Any]:
    """
    Get information about supported SQL dialects.

    Returns:
        Dictionary with dialect information

    Example:
        >>> info = get_dialect_info()
        >>> print(info['supported_dialects'])
        ['bigquery', 'snowflake', 'duckdb', ...]
    """
    return {
        "supported_dialects": sorted(set(SUPPORTED_DIALECTS.values())),
        "dialect_aliases": {
            alias: canonical
            for alias, canonical in SUPPORTED_DIALECTS.items()
            if alias != canonical
        },
        "total_count": len(set(SUPPORTED_DIALECTS.values())),
    }
