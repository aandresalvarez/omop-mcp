"""
OMOP MCP Resources - Cacheable data endpoints.

Provides MCP resources for:
- omop://concept/{id} - Concept details (JSON, cacheable)
- athena://search?query={q}&cursor={c} - Paginated ATHENA search
- backend://capabilities - Available backends and their features
"""

from typing import Any

import structlog

from omop_mcp.backends.registry import get_backend, list_backends
from omop_mcp.config import config
from omop_mcp.tools.athena import AthenaAPIClient

logger = structlog.get_logger(__name__)


# ============================================================================
# Resource Handlers
# ============================================================================


async def get_concept_resource(concept_id: int) -> dict[str, Any]:
    """
    Fetch concept details from ATHENA API.

    Resource URI: omop://concept/{concept_id}

    Returns cacheable concept JSON with:
    - concept_id, concept_name, concept_code
    - domain_id, vocabulary_id, concept_class_id
    - standard_concept, invalid_reason

    Args:
        concept_id: OMOP concept ID

    Returns:
        Dictionary with concept details

    Raises:
        ValueError: If concept_id is invalid or not found

    Example:
        >>> concept = await get_concept_resource(313217)
        >>> print(concept['concept_name'])
        'Atrial fibrillation'
    """
    if concept_id <= 0:
        raise ValueError(f"Invalid concept_id: {concept_id}")

    logger.info("get_concept_resource", concept_id=concept_id)

    try:
        client = AthenaAPIClient(base_url=config.athena_base_url)

        # Get concept details using athena-client
        concept = client.get_concept_by_id(concept_id)

        if not concept:
            raise ValueError(f"Concept {concept_id} not found")

        # Convert OMOPConcept to dictionary
        result = {
            "concept_id": concept.concept_id,
            "concept_name": concept.concept_name,
            "concept_code": concept.concept_code,
            "domain_id": concept.domain_id,
            "vocabulary_id": concept.vocabulary_id,
            "concept_class_id": concept.concept_class_id,
            "standard_concept": concept.standard_concept,
            "invalid_reason": concept.invalid_reason,
        }

        logger.info("get_concept_resource_success", concept_id=concept_id)
        return result

    except Exception as e:
        logger.error(
            "get_concept_resource_failed",
            concept_id=concept_id,
            error=str(e),
            exc_info=True,
        )
        raise


async def search_concepts_resource(
    query: str,
    cursor: str | None = None,
    page_size: int = 50,
    domain: str | None = None,
    vocabulary: str | None = None,
    standard_only: bool = True,
) -> dict[str, Any]:
    """
    Paginated ATHENA concept search.

    Resource URI: athena://search?query={q}&cursor={c}&domain={d}

    Uses cursor-based pagination for efficient traversal of large result sets.

    Args:
        query: Search query (clinical text)
        cursor: Pagination cursor (optional, for next page)
        page_size: Results per page (default: 50, max: 100)
        domain: Filter by OMOP domain (Condition, Drug, etc.)
        vocabulary: Filter by vocabulary (SNOMED, RxNorm, etc.)
        standard_only: Return only standard concepts

    Returns:
        Dictionary with:
        - concepts: List of concept dictionaries
        - next_cursor: Cursor for next page (null if last page)
        - total_count: Total results available
        - page_size: Results in this page

    Example:
        >>> page1 = await search_concepts_resource("diabetes", page_size=20)
        >>> print(f"Found {len(page1['concepts'])} concepts")
        >>>
        >>> # Get next page
        >>> if page1['next_cursor']:
        ...     page2 = await search_concepts_resource(
        ...         "diabetes",
        ...         cursor=page1['next_cursor']
        ...     )
    """
    # Validate pagination
    page_size = min(page_size, 100)  # Cap at 100

    logger.info(
        "search_concepts_resource",
        query=query,
        cursor=cursor,
        page_size=page_size,
        domain=domain,
        vocabulary=vocabulary,
    )

    try:
        client = AthenaAPIClient(base_url=config.athena_base_url)

        # Parse cursor (format: "offset:{n}")
        offset = 0
        if cursor:
            if cursor.startswith("offset:"):
                try:
                    offset = int(cursor.split(":")[1])
                except (IndexError, ValueError) as e:
                    raise ValueError(f"Invalid cursor format: {cursor}") from e
            else:
                raise ValueError(f"Invalid cursor format: {cursor}")

        # Search concepts - athena-client doesn't support pagination directly,
        # so we fetch more than needed and slice
        limit = offset + page_size + 100  # Fetch extra to check if there's more

        result = client.search_concepts(
            query=query,
            domain=domain,
            vocabulary=vocabulary,
            standard_only=standard_only,
            limit=limit,
        )

        # Slice to get current page
        concepts_page = result[offset : offset + page_size]

        # Convert to dictionaries
        concepts = [
            {
                "concept_id": c.concept_id,
                "concept_name": c.concept_name,
                "concept_code": c.concept_code,
                "domain_id": c.domain_id,
                "vocabulary_id": c.vocabulary_id,
                "concept_class_id": c.concept_class_id,
                "standard_concept": c.standard_concept,
                "invalid_reason": c.invalid_reason,
            }
            for c in concepts_page
        ]

        total_count = len(result)  # Approximate total

        # Calculate next cursor
        next_offset = offset + len(concepts)
        next_cursor = None
        if next_offset < total_count:
            next_cursor = f"offset:{next_offset}"

        response = {
            "concepts": concepts,
            "next_cursor": next_cursor,
            "total_count": total_count,
            "page_size": len(concepts),
            "query": query,
            "domain": domain,
            "vocabulary": vocabulary,
            "standard_only": standard_only,
        }

        logger.info(
            "search_concepts_resource_success",
            query=query,
            result_count=len(concepts),
            has_next=next_cursor is not None,
        )

        return response

    except Exception as e:
        logger.error(
            "search_concepts_resource_failed",
            query=query,
            error=str(e),
            exc_info=True,
        )
        raise


async def get_backend_capabilities() -> dict[str, Any]:
    """
    List available backends and their capabilities.

    Resource URI: backend://capabilities

    Returns information about all configured backends including:
    - name: Backend identifier
    - dialect: SQL dialect (bigquery, postgres, etc.)
    - features: List of supported features
    - status: live, beta, or deprecated

    Features include:
    - dry_run: Supports query validation without execution
    - cost_estimate: Can estimate query cost
    - execute: Can execute queries
    - mutations: Allows DELETE/UPDATE (always false for OMOP)

    Returns:
        Dictionary with:
        - backends: List of backend dictionaries
        - default_backend: Default backend name
        - count: Number of available backends

    Example:
        >>> caps = await get_backend_capabilities()
        >>> for backend in caps['backends']:
        ...     print(f"{backend['name']}: {backend['dialect']}")
        bigquery: bigquery
        postgres: postgresql
    """
    logger.info("get_backend_capabilities")

    try:
        backend_names = list_backends()
        backends_info = []

        for name in backend_names:
            try:
                backend = get_backend(name)

                # Determine status based on implementation
                status = "live"
                if name == "postgres":
                    # Check if postgres is fully implemented
                    if not hasattr(backend, "execute_query"):
                        status = "beta"

                backend_info = {
                    "name": name,
                    "dialect": backend.dialect,
                    "features": [
                        "dry_run",
                        "cost_estimate",
                        "execute",
                        # Note: mutations always false for OMOP (read-only)
                    ],
                    "status": status,
                }

                backends_info.append(backend_info)

            except Exception as e:
                logger.warning(
                    "backend_unavailable",
                    backend=name,
                    error=str(e),
                )
                continue

        # Determine default backend
        default_backend = "bigquery"
        if config.bigquery_project_id:
            default_backend = "bigquery"
        elif config.postgres_dsn:
            default_backend = "postgres"

        response = {
            "backends": backends_info,
            "default_backend": default_backend,
            "count": len(backends_info),
        }

        logger.info(
            "get_backend_capabilities_success",
            backend_count=len(backends_info),
            default=default_backend,
        )

        return response

    except Exception as e:
        logger.error(
            "get_backend_capabilities_failed",
            error=str(e),
            exc_info=True,
        )
        raise
