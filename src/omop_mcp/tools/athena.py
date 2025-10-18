"""
ATHENA API client for OMOP concept discovery.

Uses athena-client library to search for concepts and retrieve relationships.
"""

from __future__ import annotations

from datetime import datetime

import structlog
from athena_client import AthenaClient  # type: ignore[import-untyped]
from athena_client.models import ConceptType  # type: ignore[import-untyped]
from pydantic import ValidationError

from omop_mcp.config import config
from omop_mcp.models import (
    ConceptDiscoveryResult,
    ConceptRelationship,
    OMOPConcept,
)

logger = structlog.get_logger(__name__)


class AthenaAPIClient:
    """
    Client for ATHENA vocabulary API using athena-client library.

    Provides methods to:
    - Search for concepts by term
    - Retrieve concept details by ID
    - Get concept relationships
    """

    def __init__(self, base_url: str | None = None):
        """
        Initialize ATHENA client.

        Args:
            base_url: ATHENA API base URL (defaults to config.athena_base_url)
        """
        self.base_url = base_url or config.athena_base_url
        self.client = AthenaClient(base_url=self.base_url)
        logger.info("athena_client_initialized", base_url=self.base_url)

    def _concept_to_omop(self, athena_concept) -> OMOPConcept:
        """
        Convert athena-client Concept to OMOPConcept.

        athena-client returns Concept with fields:
        - id, name, domain, vocabulary, className, standardConcept, code, invalidReason, score
        """
        # Map standardConcept enum to string
        standard_concept = None
        if hasattr(athena_concept, "standardConcept") and athena_concept.standardConcept:
            if athena_concept.standardConcept == ConceptType.STANDARD:
                standard_concept = "S"
            elif athena_concept.standardConcept == ConceptType.CLASSIFICATION:
                standard_concept = "C"

        # Handle both search results (Concept) and details (ConceptDetails)
        domain_val: str = str(
            getattr(athena_concept, "domain", None) or getattr(athena_concept, "domainId", "")
        )
        vocab_val: str = str(
            getattr(athena_concept, "vocabulary", None)
            or getattr(athena_concept, "vocabularyId", "")
        )
        class_val: str = str(
            getattr(athena_concept, "className", None)
            or getattr(athena_concept, "conceptClassId", "")
        )
        code_val: str = str(
            getattr(athena_concept, "code", None) or getattr(athena_concept, "conceptCode", "")
        )

        return OMOPConcept(
            id=int(athena_concept.id),
            name=athena_concept.name,
            domain=domain_val,
            vocabulary=vocab_val,
            className=class_val,
            standardConcept=standard_concept,
            code=code_val,
            invalidReason=getattr(athena_concept, "invalidReason", None),
            score=getattr(athena_concept, "score", None),
        )

    def search_concepts(
        self,
        query: str,
        *,
        domain: str | None = None,
        vocabulary: str | None = None,
        concept_class: str | None = None,
        standard_only: bool = False,
        limit: int = 50,
    ) -> list[OMOPConcept]:
        """
        Search for OMOP concepts by term.

        Args:
            query: Search term (e.g., "diabetes", "influenza")
            domain: Filter by domain (e.g., "Condition", "Drug", "Measurement")
            vocabulary: Filter by vocabulary (e.g., "SNOMED", "RxNorm", "LOINC")
            concept_class: Filter by concept class
            standard_only: If True, return only standard concepts
            limit: Maximum number of results

        Returns:
            List of matching OMOP concepts
        """
        logger.info(
            "searching_concepts",
            query=query,
            domain=domain,
            vocabulary=vocabulary,
            concept_class=concept_class,
            standard_only=standard_only,
            limit=limit,
        )

        try:
            # Use athena-client basic search
            search_result = self.client.search(query)

            # Convert athena-client results to our OMOPConcept model
            # SearchResult itself is iterable
            concepts = []
            for athena_concept in search_result:
                try:
                    concept = self._concept_to_omop(athena_concept)

                    # Apply client-side filters
                    if domain and concept.domain_id != domain:
                        continue
                    if vocabulary and concept.vocabulary_id != vocabulary:
                        continue
                    if concept_class and concept.concept_class_id != concept_class:
                        continue
                    if standard_only and not concept.is_standard():
                        continue

                    concepts.append(concept)

                    if len(concepts) >= limit:
                        break

                except (ValidationError, AttributeError) as e:
                    logger.warning(
                        "concept_validation_failed",
                        concept_id=getattr(athena_concept, "id", None),
                        error=str(e),
                    )
                    continue

            logger.info("search_complete", query=query, result_count=len(concepts))
            return concepts

        except Exception as e:
            logger.error("search_failed", query=query, error=str(e), exc_info=True)
            raise

    def get_concept_by_id(self, concept_id: int) -> OMOPConcept | None:
        """
        Retrieve a single concept by its ID.

        Args:
            concept_id: OMOP concept ID

        Returns:
            Concept if found, None otherwise
        """
        logger.info("fetching_concept", concept_id=concept_id)

        try:
            # athena-client uses .details() method for single concept
            result = self.client.details(concept_id)

            if not result:
                logger.warning("concept_not_found", concept_id=concept_id)
                return None

            concept = self._concept_to_omop(result)
            logger.info("concept_fetched", concept_id=concept_id, concept_name=concept.concept_name)
            return concept

        except Exception as e:
            logger.error("fetch_failed", concept_id=concept_id, error=str(e), exc_info=True)
            raise

    def get_concept_relationships(
        self,
        concept_id: int,
        *,
        relationship_id: str | None = None,
    ) -> list[ConceptRelationship]:
        """
        Get relationships for a concept.

        Args:
            concept_id: OMOP concept ID
            relationship_id: Filter by relationship type (e.g., "Maps to", "Subsumes")

        Returns:
            List of concept relationships
        """
        logger.info(
            "fetching_relationships",
            concept_id=concept_id,
            relationship_id=relationship_id,
        )

        try:
            # athena-client uses .relationships() method
            results = self.client.relationships(concept_id)

            relationships = []
            for athena_rel in results:
                try:
                    # athena-client returns relationship objects with:
                    # - id, name, sourceId, targetId, reverseRelationship
                    rel_name = getattr(athena_rel, "name", "")

                    # Filter by relationship type if specified
                    if relationship_id and rel_name != relationship_id:
                        continue

                    rel = ConceptRelationship(
                        concept_id_1=concept_id,
                        concept_id_2=int(athena_rel.targetId),
                        relationship_id=str(athena_rel.id),
                        relationship_name=rel_name,
                    )
                    relationships.append(rel)

                except (ValidationError, AttributeError) as e:
                    logger.warning(
                        "relationship_validation_failed",
                        concept_id=concept_id,
                        error=str(e),
                    )
                    continue

            logger.info(
                "relationships_fetched",
                concept_id=concept_id,
                count=len(relationships),
            )
            return relationships

        except Exception as e:
            logger.error(
                "fetch_relationships_failed",
                concept_id=concept_id,
                error=str(e),
                exc_info=True,
            )
            raise


def discover_concepts(
    query: str,
    *,
    domain: str | None = None,
    vocabulary: str | None = None,
    standard_only: bool = True,
    limit: int = 50,
) -> ConceptDiscoveryResult:
    """
    Discover OMOP concepts by search term.

    This is the main entry point for concept discovery, wrapping AthenaAPIClient
    with a simpler interface and returning a structured result.

    Args:
        query: Search term (e.g., "diabetes", "influenza")
        domain: Filter by domain (e.g., "Condition", "Drug")
        vocabulary: Filter by vocabulary (e.g., "SNOMED", "RxNorm")
        standard_only: If True, return only standard concepts (default: True)
        limit: Maximum number of results

    Returns:
        ConceptDiscoveryResult with matched concepts and metadata

    Example:
        >>> result = discover_concepts("diabetes", domain="Condition")
        >>> print(f"Found {len(result.concepts)} concepts")
        >>> print(f"Standard concept IDs: {result.concept_ids}")
    """
    logger.info(
        "discover_concepts_called",
        query=query,
        domain=domain,
        vocabulary=vocabulary,
        standard_only=standard_only,
        limit=limit,
    )

    client = AthenaAPIClient()
    concepts = client.search_concepts(
        query=query,
        domain=domain,
        vocabulary=vocabulary,
        standard_only=standard_only,
        limit=limit,
    )

    result = ConceptDiscoveryResult(
        query=query,
        concepts=concepts,
        search_metadata={
            "domain": domain,
            "vocabulary": vocabulary,
            "standard_only": standard_only,
            "limit": limit,
        },
        timestamp=datetime.now(),
    )

    logger.info(
        "discovery_complete",
        query=query,
        total_concepts=len(concepts),
        standard_concepts=len(result.standard_concepts),
        concept_ids=result.concept_ids,
    )

    return result
