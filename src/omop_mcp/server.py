"""
OMOP MCP Server - FastMCP implementation with stdio and HTTP transports.

Provides tools for OMOP concept discovery, SQL generation, and analytical queries.
"""

from typing import Any

import structlog
from mcp.server.fastmcp import Context, FastMCP

from omop_mcp import prompts, resources
from omop_mcp.config import config
from omop_mcp.models import (
    ConceptDiscoveryResult,
    QueryOMOPResult,
)
from omop_mcp.tools.athena import AthenaAPIClient
from omop_mcp.tools.athena import discover_concepts as athena_discover_concepts
from omop_mcp.tools.schema import get_all_tables_schema, get_table_schema
from omop_mcp.tools.sql_validator import validate_sql_comprehensive

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

logger = structlog.get_logger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    "omop-mcp",
    dependencies=["pydantic-ai>=0.0.13", "athena-client==1.0.27"],
)


# ============================================================================
# MCP Tools
# ============================================================================


@mcp.tool()
async def discover_concepts(
    ctx: Context,
    clinical_text: str,
    domain: str | None = None,
    vocabulary: str | None = None,
    standard_only: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Discover OMOP concepts by searching ATHENA vocabulary.

    This tool searches the ATHENA vocabulary API for OMOP standard concepts
    matching the provided clinical term. It's the first step in building
    cohort definitions or analytical queries.

    Args:
        clinical_text: Clinical term to search (e.g., "type 2 diabetes", "influenza")
        domain: Filter by OMOP domain (Condition, Drug, Procedure, Measurement, etc.)
        vocabulary: Filter by vocabulary (SNOMED, RxNorm, LOINC, etc.)
        standard_only: Return only standard concepts (default: True)
        limit: Maximum number of concepts to return (default: 50, max: 100)

    Returns:
        Dictionary with:
        - query: Original search term
        - concepts: List of matching OMOP concepts with metadata
        - concept_ids: List of concept IDs (for use in other tools)
        - standard_concepts: Filtered list of standard concepts
        - search_metadata: Search parameters used

    Example:
        >>> result = await discover_concepts(
        ...     ctx,
        ...     clinical_text="diabetes",
        ...     domain="Condition",
        ...     standard_only=True
        ... )
        >>> print(f"Found {len(result['concepts'])} concepts")
        >>> print(f"Concept IDs: {result['concept_ids']}")
    """
    logger.info(
        "discover_concepts_called",
        clinical_text=clinical_text,
        domain=domain,
        vocabulary=vocabulary,
        standard_only=standard_only,
        limit=limit,
    )

    try:
        result: ConceptDiscoveryResult = athena_discover_concepts(
            query=clinical_text,
            domain=domain,
            vocabulary=vocabulary,
            standard_only=standard_only,
            limit=limit,
        )

        response = {
            "query": result.query,
            "concepts": [c.model_dump() for c in result.concepts],
            "concept_ids": result.concept_ids,
            "standard_concepts": [c.model_dump() for c in result.standard_concepts],
            "search_metadata": result.search_metadata,
            "timestamp": result.timestamp.isoformat(),
        }

        logger.info(
            "discover_concepts_success",
            clinical_text=clinical_text,
            concept_count=len(result.concepts),
        )

        return response

    except Exception as e:
        logger.error(
            "discover_concepts_failed",
            clinical_text=clinical_text,
            error=str(e),
            exc_info=True,
        )
        raise


@mcp.tool()
async def get_concept_relationships(
    ctx: Context,
    concept_id: int,
    relationship_id: str | None = None,
) -> dict[str, Any]:
    """
    Get relationships for an OMOP concept.

    Retrieves concept relationships such as "Maps to", "Subsumes", "Is a", etc.
    Useful for understanding concept hierarchies and finding related concepts.

    Args:
        concept_id: OMOP concept ID
        relationship_id: Filter by relationship type (optional)

    Returns:
        Dictionary with:
        - concept_id: Original concept ID
        - relationships: List of related concepts with relationship types
        - relationship_count: Total number of relationships found

    Example:
        >>> result = await get_concept_relationships(ctx, concept_id=201826)
        >>> print(f"Found {result['relationship_count']} relationships")
    """
    logger.info(
        "get_concept_relationships_called",
        concept_id=concept_id,
        relationship_id=relationship_id,
    )

    try:
        client = AthenaAPIClient()
        relationships = client.get_concept_relationships(
            concept_id=concept_id, relationship_id=relationship_id
        )

        response = {
            "concept_id": concept_id,
            "relationships": [r.model_dump() for r in relationships],
            "relationship_count": len(relationships),
        }

        logger.info(
            "get_concept_relationships_success",
            concept_id=concept_id,
            relationship_count=len(relationships),
        )

        return response

    except Exception as e:
        logger.error(
            "get_concept_relationships_failed",
            concept_id=concept_id,
            error=str(e),
            exc_info=True,
        )
        raise


@mcp.tool()
async def query_omop(
    ctx: Context,
    query_type: str,
    concept_ids: list[int],
    domain: str = "Condition",
    backend: str = "bigquery",
    execute: bool = True,
    limit: int = 1000,
) -> dict[str, Any]:
    """
    Execute analytical queries against OMOP CDM data.

    This tool supports three query types:
    - "count": Count distinct patients with the specified concepts
    - "breakdown": Group patients by demographics (age, gender)
    - "list_patients": List patient IDs (PHI-protected, requires permission)

    Security features:
    - Cost estimation before execution
    - Cost cap enforcement (default: $1.00 USD)
    - Mutation blocking (no DELETE/UPDATE/DROP)
    - Row limits (max: 1000)
    - PHI protection (list_patients requires ALLOW_PATIENT_LIST=true)

    Args:
        query_type: Type of query ("count", "breakdown", "list_patients")
        concept_ids: List of OMOP concept IDs to query
        domain: OMOP domain (Condition, Drug, Procedure, Measurement, Observation)
        backend: Database backend to use (default: "bigquery")
        execute: Execute query or return SQL only (default: True)
        limit: Maximum rows to return (default: 1000, max: 1000)

    Returns:
        Dictionary with:
        - sql: Generated SQL query
        - results: Query results (if executed)
        - row_count: Number of rows returned
        - estimated_cost_usd: Estimated query cost
        - estimated_bytes: Estimated bytes processed
        - backend: Backend used
        - dialect: SQL dialect

    Example:
        >>> # Step 1: Discover concepts
        >>> discovery = await discover_concepts(ctx, clinical_text="influenza")
        >>> concept_ids = discovery['concept_ids']
        >>>
        >>> # Step 2: Count patients (estimate cost first)
        >>> estimate = await query_omop(
        ...     ctx,
        ...     query_type="count",
        ...     concept_ids=concept_ids,
        ...     execute=False
        ... )
        >>> print(f"Estimated cost: ${estimate['estimated_cost_usd']:.4f}")
        >>>
        >>> # Step 3: Execute if cost is acceptable
        >>> if estimate['estimated_cost_usd'] < 0.10:
        ...     result = await query_omop(
        ...         ctx,
        ...         query_type="count",
        ...         concept_ids=concept_ids,
        ...         execute=True
        ...     )
        ...     print(f"Patient count: {result['results'][0]['patient_count']}")
    """
    logger.info(
        "query_omop_called",
        query_type=query_type,
        concept_ids=concept_ids,
        domain=domain,
        backend=backend,
        execute=execute,
        limit=limit,
    )

    try:
        # Import here to avoid circular dependency
        from omop_mcp.tools.query import query_by_concepts

        result: QueryOMOPResult = await query_by_concepts(
            query_type=query_type,
            concept_ids=concept_ids,
            domain=domain,
            backend=backend,
            execute=execute,
            limit=limit,
        )

        response = {
            "sql": result.sql,
            "results": result.results,
            "row_count": result.row_count,
            "estimated_cost_usd": result.estimated_cost_usd,
            "estimated_bytes": result.estimated_bytes,
            "backend": result.backend,
            "dialect": result.dialect,
            "timestamp": result.timestamp.isoformat(),
        }

        logger.info(
            "query_omop_success",
            query_type=query_type,
            concept_count=len(concept_ids),
            executed=execute,
            row_count=result.row_count,
        )

        return response

    except Exception as e:
        logger.error(
            "query_omop_failed",
            query_type=query_type,
            concept_ids=concept_ids,
            error=str(e),
            exc_info=True,
        )
        raise


@mcp.tool()  # Remove deferred parameter as it's not supported
async def generate_cohort_sql(
    ctx: Context,
    exposure_concept_ids: list[int],
    outcome_concept_ids: list[int],
    pre_outcome_days: int = 90,
    backend: str = "bigquery",
    validate: bool = True,
) -> dict[str, Any]:
    """
    Generate SQL for cohort definition with exposure → outcome logic.

    This tool generates validated SQL for identifying a cohort where:
    - Patients have an exposure event (e.g., drug prescription)
    - Followed by an outcome event (e.g., adverse event)
    - Within a specified time window (pre_outcome_days)

    The generated SQL uses OMOP CDM standard tables and can be executed
    directly in your database.

    Args:
        exposure_concept_ids: Concept IDs for exposure events
        outcome_concept_ids: Concept IDs for outcome events
        pre_outcome_days: Maximum days between exposure and outcome (default: 90)
        backend: Database backend ("bigquery" or "postgres")
        validate: Run dry-run validation (default: True)

    Returns:
        Dictionary with:
        - sql: Generated SQL query
        - validation: Validation result (if validate=True)
        - concept_counts: Count of exposure/outcome concepts
        - backend: Backend used
        - dialect: SQL dialect
        - is_valid: Whether SQL passed validation

    Example:
        >>> # Find exposures (statins) and outcomes (myopathy)
        >>> exposures = await discover_concepts(ctx, "statin")
        >>> outcomes = await discover_concepts(ctx, "myopathy")
        >>>
        >>> result = await generate_cohort_sql(
        ...     ctx,
        ...     exposure_concept_ids=exposures['concept_ids'],
        ...     outcome_concept_ids=outcomes['concept_ids'],
        ...     pre_outcome_days=180
        ... )
        >>> print(result['sql'])
        >>> if result['is_valid']:
        ...     print(f"Estimated cost: ${result['validation']['estimated_cost_usd']}")
    """
    logger.info(
        "generate_cohort_sql_called",
        exposure_count=len(exposure_concept_ids),
        outcome_count=len(outcome_concept_ids),
        pre_outcome_days=pre_outcome_days,
        backend=backend,
        validate=validate,
    )

    try:
        # Use dedicated sqlgen module
        from omop_mcp.tools.sqlgen import generate_cohort_sql as generate_sql

        result = await generate_sql(
            exposure_concept_ids=exposure_concept_ids,
            outcome_concept_ids=outcome_concept_ids,
            time_window_days=pre_outcome_days,
            backend=backend,
            validate=validate,
        )

        response = {
            "sql": result.sql,
            "validation": result.validation.model_dump() if result.validation else None,
            "concept_counts": result.concept_counts,
            "backend": result.backend,
            "dialect": result.dialect,
            "is_valid": result.is_valid,
            "timestamp": result.timestamp.isoformat(),
        }

        logger.info(
            "generate_cohort_sql_success",
            backend=backend,
            is_valid=result.is_valid,
            sql_length=len(result.sql),
        )

        return response

    except Exception as e:
        logger.error(
            "generate_cohort_sql_failed",
            backend=backend,
            error=str(e),
            exc_info=True,
        )
        raise


@mcp.tool()
async def get_information_schema(
    ctx: Context,
    table_name: str | None = None,
    backend: str = "bigquery",
) -> dict[str, Any]:
    """
    Get OMOP database schema information.

    This tool provides detailed schema information for OMOP CDM tables,
    including column definitions, data types, and OMOP-specific descriptions.
    Useful for understanding table structures before writing queries.

    Args:
        table_name: Specific OMOP table (e.g., 'condition_occurrence', 'person')
        backend: Database backend to query ("bigquery", "snowflake", "duckdb")

    Returns:
        Dictionary with:
        - table_name: Name of the table
        - description: OMOP CDM description of the table
        - is_omop_standard: Whether this is a standard OMOP table
        - columns: List of column definitions with types and descriptions
        - column_count: Total number of columns
        - backend: Backend used for schema query

    Example:
        >>> # Get schema for condition_occurrence table
        >>> schema = await get_information_schema(
        ...     ctx,
        ...     table_name="condition_occurrence",
        ...     backend="bigquery"
        ... )
        >>> print(f"Table has {schema['column_count']} columns")
        >>> for col in schema['columns']:
        ...     print(f"{col['name']}: {col['type']} - {col['description']}")
    """
    logger.info(
        "get_information_schema_called",
        table_name=table_name,
        backend=backend,
    )

    try:
        if table_name:
            # Get specific table schema
            result = await get_table_schema(table_name, backend)
        else:
            # Get all tables schema
            result = await get_all_tables_schema(backend, include_non_omop=False)

        logger.info(
            "get_information_schema_success",
            table_name=table_name,
            backend=backend,
        )

        return result

    except Exception as e:
        logger.error(
            "get_information_schema_failed",
            table_name=table_name,
            backend=backend,
            error=str(e),
            exc_info=True,
        )
        raise


@mcp.tool()
async def select_query(
    ctx: Context,
    sql: str,
    validate: bool = True,
    execute: bool = True,
    backend: str = "bigquery",
    limit: int = 1000,
) -> dict[str, Any]:
    """
    Execute a SELECT query with security validation.

    This tool allows direct SQL execution with comprehensive security checks:
    - Only SELECT statements are allowed
    - OMOP table allowlist validation (if enabled)
    - PHI column blocking
    - Cost estimation and limits
    - Automatic row limiting

    Args:
        sql: SQL SELECT statement to execute
        validate: Run validation before execution (default: True)
        execute: Execute query or return SQL only (default: True)
        backend: Database backend ("bigquery", "snowflake", "duckdb")
        limit: Maximum rows to return (default: 1000)

    Returns:
        Dictionary with:
        - sql: SQL query (with LIMIT applied if needed)
        - results: Query results (if execute=True)
        - row_count: Number of rows returned
        - validation: Validation result
        - estimated_cost_usd: Estimated cost (BigQuery only)
        - estimated_bytes: Estimated bytes scanned
        - backend: Backend used
        - execution_time_ms: Query execution time

    Example:
        >>> # Count patients with diabetes
        >>> result = await select_query(
        ...     ctx,
        ...     sql="SELECT COUNT(DISTINCT person_id) FROM condition_occurrence WHERE condition_concept_id = 201826",
        ...     backend="bigquery",
        ...     execute=True
        ... )
        >>> print(f"Found {result['results'][0]['patient_count']} patients")
    """
    logger.info(
        "select_query_called",
        sql_length=len(sql),
        validate=validate,
        execute=execute,
        backend=backend,
        limit=limit,
    )

    try:
        import time

        from omop_mcp.backends.registry import get_backend

        # Validate SQL if requested
        validation_result = None
        if validate:
            validation_result = await validate_sql_comprehensive(
                sql, backend, limit, check_cost=True
            )

            if not validation_result.valid:
                return {
                    "sql": sql,
                    "results": None,
                    "row_count": None,
                    "validation": validation_result.model_dump(),
                    "estimated_cost_usd": validation_result.estimated_cost_usd,
                    "estimated_bytes": validation_result.estimated_bytes,
                    "backend": backend,
                    "error": validation_result.error_message,
                }

        # Execute query if requested
        results = None
        row_count = None
        execution_time_ms = None

        if execute:
            start_time = time.time()

            try:
                backend_impl = get_backend(backend)

                # Apply row limit to SQL
                sql_with_limit = sql
                if "LIMIT" not in sql.upper():
                    sql_with_limit = f"{sql.rstrip()}\nLIMIT {limit}"

                # Execute query
                results = await backend_impl.execute_query(sql_with_limit, limit)
                row_count = len(results)

                execution_time_ms = int((time.time() - start_time) * 1000)

            except Exception as e:
                logger.error("query_execution_failed", error=str(e))
                return {
                    "sql": sql,
                    "results": None,
                    "row_count": None,
                    "validation": validation_result.model_dump() if validation_result else None,
                    "estimated_cost_usd": (
                        validation_result.estimated_cost_usd if validation_result else 0.0
                    ),
                    "estimated_bytes": (
                        validation_result.estimated_bytes if validation_result else 0
                    ),
                    "backend": backend,
                    "error": str(e),
                }

        logger.info(
            "select_query_success",
            sql_length=len(sql),
            execute=execute,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
        )

        return {
            "sql": sql,
            "results": results,
            "row_count": row_count,
            "validation": validation_result.model_dump() if validation_result else None,
            "estimated_cost_usd": (
                validation_result.estimated_cost_usd if validation_result else 0.0
            ),
            "estimated_bytes": validation_result.estimated_bytes if validation_result else 0,
            "backend": backend,
            "execution_time_ms": execution_time_ms,
        }

    except Exception as e:
        logger.error(
            "select_query_failed",
            sql=sql[:100],
            backend=backend,
            error=str(e),
            exc_info=True,
        )
        raise


# ============================================================================
# MCP Resources
# ============================================================================


@mcp.resource("omop://concept/{concept_id}")
async def get_concept(concept_id: int) -> str:
    """
    Get concept details by ID (cacheable).

    Returns JSON with concept details from ATHENA API.
    """
    result = await resources.get_concept_resource(concept_id)
    import json

    return json.dumps(result, indent=2)


@mcp.resource("athena://search")
async def search_concepts(
    query: str,
    cursor: str | None = None,
    page_size: int = 50,
    domain: str | None = None,
    vocabulary: str | None = None,
    standard_only: bool = True,
) -> str:
    """
    Paginated concept search.

    Returns JSON with concepts and next_cursor for pagination.
    """
    result = await resources.search_concepts_resource(
        query=query,
        cursor=cursor,
        page_size=page_size,
        domain=domain,
        vocabulary=vocabulary,
        standard_only=standard_only,
    )
    import json

    return json.dumps(result, indent=2)


@mcp.resource("backend://capabilities")
async def backend_capabilities() -> str:
    """
    List available backends and their capabilities.

    Returns JSON with backend information.
    """
    result = await resources.get_backend_capabilities()
    import json

    return json.dumps(result, indent=2)


# ============================================================================
# MCP Prompts
# ============================================================================


@mcp.prompt()
async def cohort_sql_template(
    exposure_concepts: list[dict[str, Any]],
    outcome_concepts: list[dict[str, Any]],
    time_window_days: int,
    backend_dialect: str = "bigquery",
) -> str:
    """
    Template for cohort SQL generation.

    Provides AI-ready prompt for generating OMOP CDM cohort identification SQL.
    """
    result = await prompts.get_prompt(
        "cohort/sql",
        {
            "exposure_concepts": exposure_concepts,
            "outcome_concepts": outcome_concepts,
            "time_window_days": time_window_days,
            "backend_dialect": backend_dialect,
        },
    )
    return str(result["content"])


@mcp.prompt()
async def analysis_discovery_workflow(
    clinical_question: str,
    domains: list[str] | None = None,
) -> str:
    """
    Template for systematic concept discovery.

    Guides users through discovering OMOP concepts for clinical research questions.
    """
    result = await prompts.get_prompt(
        "analysis/discovery",
        {
            "clinical_question": clinical_question,
            "domains": domains,
        },
    )
    return str(result["content"])


@mcp.prompt()
async def multi_step_query_workflow(
    concept_ids: list[int],
    domain: str,
) -> str:
    """
    Template for cost-aware query execution.

    Guides users through multi-step query workflow with cost estimation.
    """
    result = await prompts.get_prompt(
        "query/multi-step",
        {
            "concept_ids": concept_ids,
            "domain": domain,
        },
    )
    return str(result["content"])


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Run the OMOP MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="OMOP MCP Server")
    parser.add_argument(
        "--stdio", action="store_true", help="Run in stdio mode (for MCP Inspector)"
    )
    parser.add_argument("--http", action="store_true", help="Run HTTP server")
    parser.add_argument("--port", type=int, default=8000, help="HTTP server port (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP server host (default: 0.0.0.0)")

    args = parser.parse_args()

    logger.info(
        "omop_mcp_server_starting",
        log_level=config.log_level,
        stdio=args.stdio,
        http=args.http,
        port=args.port if args.http else None,
    )

    if args.http:
        logger.info("starting_http_server", host=args.host, port=args.port)
        # FastMCP HTTP server
        import uvicorn

        uvicorn.run(
            mcp.get_asgi_app(),
            host=args.host,
            port=args.port,
            log_level=config.log_level.lower(),
        )
    elif args.stdio:
        logger.info("starting_stdio_server")
        # FastMCP stdio server (for MCP Inspector)
        mcp.run(transport="stdio")
    else:
        # Default to stdio
        logger.info("starting_stdio_server_default")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
