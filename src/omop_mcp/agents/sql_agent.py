"""SQL Generation Agent using PydanticAI.

This agent helps users generate OMOP SQL queries from research questions.
It determines the appropriate query type, generates validated SQL, and provides
explanations for the generated queries.
"""

import structlog
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from omop_mcp.tools.sqlgen import (
    format_sql,
    generate_cohort_sql,
    generate_simple_query,
)

logger = structlog.get_logger(__name__)


class SQLGenerationRequest(BaseModel):
    """Request for SQL generation."""

    research_question: str = Field(..., description="Research question in natural language")
    exposure_concept_ids: list[int] | None = Field(
        None, description="Exposure concept IDs (for cohort queries)"
    )
    outcome_concept_ids: list[int] | None = Field(
        None, description="Outcome concept IDs (for cohort queries)"
    )
    concept_ids: list[int] | None = Field(None, description="Concept IDs (for simple queries)")
    domain: str | None = Field(None, description="OMOP domain")
    backend: str = Field("bigquery", description="Database backend")
    time_window_days: int = Field(90, description="Time window for cohort queries")


class SQLGenerationResult(BaseModel):
    """Result from SQL generation with explanations."""

    sql: str = Field(..., description="Generated SQL query")
    query_type: str = Field(..., description="Type of query (cohort, count, etc.)")
    explanation: str = Field(..., description="Explanation of the query logic")
    is_valid: bool = Field(..., description="Whether SQL passed validation")
    estimated_cost_usd: float | None = Field(None, description="Estimated query cost")
    backend: str = Field(..., description="Database backend used")
    suggestions: list[str] = Field(default_factory=list, description="Suggestions for improvement")


class SQLGenerationAgent:
    """
    PydanticAI agent for intelligent SQL generation.

    This agent helps researchers generate OMOP SQL queries by:
    1. Understanding research questions
    2. Determining appropriate query type
    3. Generating validated SQL
    4. Providing explanations and suggestions

    Example:
        >>> agent = SQLGenerationAgent()
        >>> result = await agent.generate_sql(
        ...     research_question="Find patients exposed to metformin who developed lactic acidosis",
        ...     exposure_concept_ids=[1503297],
        ...     outcome_concept_ids=[443530],
        ... )
        >>> print(result.sql)
        >>> print(result.explanation)
    """

    def __init__(self, model: str = "openai:gpt-4o"):
        """
        Initialize the SQL generation agent.

        Args:
            model: LLM model to use (default: gpt-4o for complex SQL reasoning)
        """
        self.model = model
        self.agent = Agent(
            model=self.model,
            output_type=SQLGenerationResult,
            system_prompt=self._get_system_prompt(),
            deps_type=SQLGenerationRequest,
        )

        # Register SQL generation tools
        @self.agent.tool
        async def generate_cohort_query(
            ctx: RunContext[SQLGenerationRequest],
            exposure_concept_ids: list[int],
            outcome_concept_ids: list[int],
            time_window_days: int = 90,
            backend: str = "bigquery",
        ) -> dict:
            """
            Generate SQL for cohort queries (exposure → outcome).

            Args:
                ctx: PydanticAI context
                exposure_concept_ids: Exposure concept IDs
                outcome_concept_ids: Outcome concept IDs
                time_window_days: Time window in days
                backend: Database backend

            Returns:
                Dictionary with SQL and metadata
            """
            logger.info(
                "agent_generating_cohort_sql",
                exposure_count=len(exposure_concept_ids),
                outcome_count=len(outcome_concept_ids),
                time_window=time_window_days,
            )

            result = await generate_cohort_sql(
                exposure_concept_ids=exposure_concept_ids,
                outcome_concept_ids=outcome_concept_ids,
                time_window_days=time_window_days,
                backend=backend,
                validate=True,
            )

            return {
                "sql": result.sql,
                "is_valid": result.is_valid,
                "validation": result.validation.model_dump() if result.validation else None,
                "backend": result.backend,
                "dialect": result.dialect,
            }

        @self.agent.tool
        async def generate_analytical_query(
            ctx: RunContext[SQLGenerationRequest],
            concept_ids: list[int],
            domain: str,
            query_type: str = "count",
            backend: str = "bigquery",
        ) -> dict:
            """
            Generate SQL for simple analytical queries.

            Args:
                ctx: PydanticAI context
                concept_ids: Concept IDs to query
                domain: OMOP domain
                query_type: Type of query (count, breakdown, list_patients)
                backend: Database backend

            Returns:
                Dictionary with SQL and metadata
            """
            logger.info(
                "agent_generating_analytical_sql",
                concept_count=len(concept_ids),
                domain=domain,
                query_type=query_type,
            )

            result = await generate_simple_query(
                concept_ids=concept_ids,
                domain=domain,
                query_type=query_type,
                backend=backend,
                validate=True,
            )

            return result

        @self.agent.tool
        def format_query(
            ctx: RunContext[SQLGenerationRequest],
            sql: str,
        ) -> str:
            """
            Format SQL for readability.

            Args:
                ctx: PydanticAI context
                sql: SQL to format

            Returns:
                Formatted SQL string
            """
            return format_sql(sql)

        logger.info("sql_generation_agent_initialized", model=self.model)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are an expert OMOP SQL generation specialist helping researchers create database queries.

Your role is to:
1. Understand the research question and required data
2. Determine the appropriate query type:
   - Cohort queries: Exposure → outcome temporal relationships
   - Count queries: Patient/event counts
   - Breakdown queries: Demographic or temporal distributions
   - List queries: Individual patient records
3. Generate validated, efficient SQL using the available tools
4. Provide clear explanations of query logic
5. Suggest improvements or alternatives

Query Type Selection:
- Use cohort queries when looking for temporal relationships (A then B)
- Use count queries for prevalence or simple counts
- Use breakdown queries for stratification analysis
- Use list queries carefully (can return large result sets)

Best Practices:
- Always validate SQL before returning
- Consider cost implications (estimated_cost_usd)
- Explain time windows and temporal logic
- Suggest indexes or optimizations when relevant
- Warn about potential privacy/PHI concerns

OMOP CDM Tables:
- person: Demographics
- condition_occurrence: Diagnoses
- drug_exposure: Medications
- procedure_occurrence: Procedures
- measurement: Lab results, vitals
- observation: Other clinical observations

Always provide explanations in plain language that researchers without SQL expertise can understand."""

    async def generate_sql(
        self,
        research_question: str,
        exposure_concept_ids: list[int] | None = None,
        outcome_concept_ids: list[int] | None = None,
        concept_ids: list[int] | None = None,
        domain: str | None = None,
        backend: str = "bigquery",
        time_window_days: int = 90,
    ) -> SQLGenerationResult:
        """
        Generate SQL from research question.

        Args:
            research_question: Research question in natural language
            exposure_concept_ids: Exposure concept IDs (for cohort queries)
            outcome_concept_ids: Outcome concept IDs (for cohort queries)
            concept_ids: Concept IDs (for simple queries)
            domain: OMOP domain
            backend: Database backend
            time_window_days: Time window for cohort queries

        Returns:
            SQLGenerationResult with SQL and explanations

        Example:
            >>> agent = SQLGenerationAgent()
            >>> result = await agent.generate_sql(
            ...     "Find patients with diabetes who had an MI within 90 days",
            ...     exposure_concept_ids=[201826],
            ...     outcome_concept_ids=[4329847],
            ...     time_window_days=90
            ... )
            >>> print(result.sql)
        """
        logger.info(
            "generate_sql_requested",
            research_question=research_question,
            has_exposure=exposure_concept_ids is not None,
            has_outcome=outcome_concept_ids is not None,
            has_concepts=concept_ids is not None,
        )

        request = SQLGenerationRequest(
            research_question=research_question,
            exposure_concept_ids=exposure_concept_ids,
            outcome_concept_ids=outcome_concept_ids,
            concept_ids=concept_ids,
            domain=domain,
            backend=backend,
            time_window_days=time_window_days,
        )

        try:
            # Run the agent with the request
            result = await self.agent.run(
                f"""Generate SQL for this research question: {research_question}

Available data:
- Exposure concept IDs: {exposure_concept_ids or 'None'}
- Outcome concept IDs: {outcome_concept_ids or 'None'}
- Concept IDs: {concept_ids or 'None'}
- Domain: {domain or 'Not specified'}
- Backend: {backend}
- Time window: {time_window_days} days

Analyze the question and generate appropriate SQL.""",
                deps=request,
            )

            logger.info(
                "generate_sql_success",
                research_question=research_question,
                query_type=result.output.query_type,
                is_valid=result.output.is_valid,
            )

            return SQLGenerationResult(**result.output.model_dump())

        except Exception as e:
            logger.error(
                "generate_sql_failed",
                research_question=research_question,
                error=str(e),
                exc_info=True,
            )
            raise

    async def optimize_sql(
        self,
        sql: str,
        performance_feedback: str | None = None,
    ) -> SQLGenerationResult:
        """
        Optimize existing SQL query.

        Args:
            sql: Existing SQL query
            performance_feedback: Optional feedback about performance issues

        Returns:
            SQLGenerationResult with optimized SQL

        Example:
            >>> result = await agent.optimize_sql(
            ...     original_sql,
            ...     performance_feedback="Query takes 45 seconds, scans 500GB"
            ... )
        """
        logger.info("optimize_sql_requested", sql_length=len(sql))

        feedback_text = (
            f"\n\nPerformance feedback: {performance_feedback}" if performance_feedback else ""
        )

        request = SQLGenerationRequest(
            research_question=f"Optimize this SQL query{feedback_text}",
            exposure_concept_ids=None,
            outcome_concept_ids=None,
            concept_ids=None,
            domain=None,
            backend="bigquery",
            time_window_days=90,
        )

        try:
            result = await self.agent.run(
                f"""Analyze and optimize this OMOP SQL query:

```sql
{sql}
```
{feedback_text}

Provide:
1. Optimized version of the SQL
2. Explanation of changes made
3. Suggestions for further improvements
4. Any concerns or warnings""",
                deps=request,
            )

            logger.info("optimize_sql_success", original_length=len(sql))

            return SQLGenerationResult(**result.output.model_dump())

        except Exception as e:
            logger.error("optimize_sql_failed", error=str(e), exc_info=True)
            raise
