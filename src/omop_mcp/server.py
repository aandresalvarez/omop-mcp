"""
OMOP MCP Server - FastMCP implementation with stdio and HTTP transports.

Provides tools for OMOP concept discovery, SQL generation, and analytical queries.
"""

from typing import Any

import structlog
from mcp.server.fastmcp import Context, FastMCP

from omop_mcp.config import config
from omop_mcp.models import (
    CohortSQLResult,
    ConceptDiscoveryResult,
    QueryOMOPResult,
)
from omop_mcp.tools.athena import AthenaAPIClient
from omop_mcp.tools.athena import discover_concepts as athena_discover_concepts

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


@mcp.tool(deferred=False)  # Set to True when implementing async approval workflow
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
        from omop_mcp.backends.registry import get_backend

        backend_impl = get_backend(backend)

        # Build SQL using backend
        cohort_parts = await backend_impl.build_cohort_sql(
            exposure_ids=exposure_concept_ids,
            outcome_ids=outcome_concept_ids,
            pre_outcome_days=pre_outcome_days,
        )

        sql = cohort_parts.to_sql()

        # Validate if requested
        validation_result = None
        if validate:
            validation_result = await backend_impl.validate_sql(sql)

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
            sql_length=len(sql),
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
