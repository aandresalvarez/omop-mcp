"""Concept Discovery Agent using PydanticAI.

This agent helps users find relevant OMOP concepts from natural language descriptions.
It uses the ATHENA API to search for concepts and provides intelligent filtering and
ranking based on the user's research context.
"""

import structlog
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from omop_mcp.models import OMOPConcept
from omop_mcp.tools.athena import discover_concepts

logger = structlog.get_logger(__name__)


class ConceptSearchRequest(BaseModel):
    """Request for concept discovery."""

    query: str = Field(..., description="Natural language description of concepts to find")
    domain: str | None = Field(None, description="OMOP domain filter (Condition, Drug, etc.)")
    max_results: int = Field(20, ge=1, le=100, description="Maximum concepts to return")
    require_standard: bool = Field(True, description="Only return standard concepts")


class ConceptSearchResult(BaseModel):
    """Result from concept discovery with explanations."""

    concepts: list[OMOPConcept] = Field(default_factory=list)
    reasoning: str = Field(..., description="Explanation of concept selection")
    concept_ids: list[int] = Field(default_factory=list)
    total_found: int = Field(0, description="Total concepts found before filtering")
    filters_applied: list[str] = Field(default_factory=list)


class ConceptDiscoveryAgent:
    """
    PydanticAI agent for intelligent concept discovery.

    This agent helps researchers find relevant OMOP concepts by:
    1. Understanding natural language queries
    2. Searching ATHENA vocabulary
    3. Filtering and ranking results
    4. Providing explanations for selections

    Example:
        >>> agent = ConceptDiscoveryAgent()
        >>> result = await agent.find_concepts(
        ...     "patients with type 2 diabetes",
        ...     domain="Condition"
        ... )
        >>> print(f"Found {len(result.concepts)} concepts")
        >>> print(result.reasoning)
    """

    def __init__(self, model: str = "openai:gpt-4o-mini"):
        """
        Initialize the concept discovery agent.

        Args:
            model: LLM model to use (default: gpt-4o-mini for cost efficiency)
        """
        self.model = model
        self.agent = Agent(
            model=self.model,
            output_type=ConceptSearchResult,
            system_prompt=self._get_system_prompt(),
            deps_type=ConceptSearchRequest,
        )

        # Register the discover_concepts tool
        @self.agent.tool
        def search_concepts(
            ctx: RunContext[ConceptSearchRequest],
            query: str,
            domain: str | None = None,
            max_results: int = 20,
        ) -> dict:
            """
            Search ATHENA vocabulary for OMOP concepts.

            Args:
                ctx: PydanticAI context
                query: Search query
                domain: OMOP domain filter
                max_results: Maximum results

            Returns:
                Dictionary with concepts and metadata
            """
            logger.info(
                "agent_searching_concepts",
                query=query,
                domain=domain,
                max_results=max_results,
            )

            # Call the existing discover_concepts function
            result = discover_concepts(
                query=query,
                domain=domain,
                limit=max_results,
            )

            return {
                "concepts": [c.model_dump() for c in result.concepts],
                "total_found": len(result.concepts),
                "query": query,
            }

        logger.info("concept_discovery_agent_initialized", model=self.model)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are an expert OMOP vocabulary specialist helping researchers find relevant medical concepts.

Your role is to:
1. Understand the user's research question or clinical description
2. Search the ATHENA OMOP vocabulary using the search_concepts tool
3. Analyze and filter the results to find the most relevant concepts
4. Provide clear reasoning for your selections

When searching:
- Use specific medical terminology when possible
- Consider synonyms and related terms
- Filter by domain (Condition, Drug, Procedure, etc.) when appropriate
- Prioritize standard concepts (standard_concept = 'S')
- Look for concepts with high clinical relevance

When explaining your results:
- Describe why each concept was selected
- Note any important distinctions or relationships
- Suggest if additional searches might be needed
- Warn about any ambiguities or limitations

Always provide the concept_ids list for downstream SQL generation."""

    async def find_concepts(
        self,
        query: str,
        domain: str | None = None,
        max_results: int = 20,
        require_standard: bool = True,
    ) -> ConceptSearchResult:
        """
        Find relevant OMOP concepts from natural language description.

        Args:
            query: Natural language description (e.g., "diabetes with complications")
            domain: OMOP domain filter (Condition, Drug, Procedure, etc.)
            max_results: Maximum concepts to return
            require_standard: Only return standard concepts

        Returns:
            ConceptSearchResult with concepts and reasoning

        Example:
            >>> agent = ConceptDiscoveryAgent()
            >>> result = await agent.find_concepts(
            ...     "type 2 diabetes mellitus",
            ...     domain="Condition",
            ...     max_results=10
            ... )
            >>> for concept in result.concepts:
            ...     print(f"{concept.concept_id}: {concept.concept_name}")
        """
        logger.info(
            "find_concepts_requested",
            query=query,
            domain=domain,
            max_results=max_results,
        )

        request = ConceptSearchRequest(
            query=query,
            domain=domain,
            max_results=max_results,
            require_standard=require_standard,
        )

        try:
            # Run the agent with the request
            result = await self.agent.run(
                f"Find OMOP concepts for: {query}",
                deps=request,
            )

            logger.info(
                "find_concepts_success",
                query=query,
                concepts_found=len(result.output.concepts),
            )

            return ConceptSearchResult(**result.output.model_dump())

        except Exception as e:
            logger.error(
                "find_concepts_failed",
                query=query,
                error=str(e),
                exc_info=True,
            )
            raise

    async def refine_concepts(
        self,
        concepts: list[OMOPConcept],
        refinement_query: str,
    ) -> ConceptSearchResult:
        """
        Refine an existing list of concepts based on additional criteria.

        Args:
            concepts: Existing concept list
            refinement_query: Additional filtering/refinement criteria

        Returns:
            ConceptSearchResult with refined concepts

        Example:
            >>> # Initial search
            >>> result1 = await agent.find_concepts("diabetes")
            >>> # Refine to only Type 2
            >>> result2 = await agent.refine_concepts(
            ...     result1.concepts,
            ...     "only type 2 diabetes, exclude type 1"
            ... )
        """
        logger.info(
            "refine_concepts_requested",
            initial_count=len(concepts),
            refinement=refinement_query,
        )

        # Create a refinement request
        concept_summary = ", ".join(f"{c.concept_id}:{c.concept_name}" for c in concepts[:5])
        prompt = f"""Refine this concept list based on new criteria.

Initial concepts: {concept_summary} (and {len(concepts) - 5} more)
Refinement: {refinement_query}

Analyze the concepts and determine which ones match the refinement criteria.
Provide reasoning for inclusions/exclusions."""

        request = ConceptSearchRequest(
            query=refinement_query,
            domain=None,
            max_results=len(concepts),
            require_standard=True,
        )

        try:
            result = await self.agent.run(prompt, deps=request)

            logger.info(
                "refine_concepts_success",
                initial_count=len(concepts),
                refined_count=len(result.output.concepts),
            )

            return ConceptSearchResult(**result.output.model_dump())

        except Exception as e:
            logger.error(
                "refine_concepts_failed",
                error=str(e),
                exc_info=True,
            )
            raise
