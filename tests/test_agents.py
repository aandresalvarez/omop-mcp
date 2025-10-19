"""Tests for PydanticAI agents."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from omop_mcp.agents.concept_agent import (
    ConceptDiscoveryAgent,
    ConceptSearchResult,
)
from omop_mcp.agents.sql_agent import (
    SQLGenerationAgent,
    SQLGenerationResult,
)
from omop_mcp.models import ConceptDiscoveryResult, OMOPConcept


class TestConceptDiscoveryAgent:
    """Test Concept Discovery Agent."""

    @pytest.fixture
    def mock_concepts(self):
        """Create mock OMOP concepts for testing."""
        return [
            OMOPConcept(
                id=201826,
                name="Type 2 diabetes mellitus",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept="S",
                code="44054006",
                invalidReason=None,
            ),
            OMOPConcept(
                id=201254,
                name="Diabetes mellitus",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept="S",
                code="73211009",
                invalidReason=None,
            ),
        ]

    @pytest.fixture
    def mock_discovery_result(self, mock_concepts):
        """Create mock concept discovery result."""
        return ConceptDiscoveryResult(
            query="diabetes",
            concepts=mock_concepts,
        )

    def test_agent_initialization(self):
        """Test agent can be initialized."""
        agent = ConceptDiscoveryAgent(model="test")
        assert agent.model == "test"
        assert agent.agent is not None

    @pytest.mark.asyncio
    async def test_find_concepts_with_mock_llm(self, mock_concepts, mock_discovery_result):
        """Test concept discovery with mocked LLM and API."""
        # Mock the discover_concepts function
        with patch("omop_mcp.agents.concept_agent.discover_concepts") as mock_discover:
            mock_discover.return_value = mock_discovery_result

            # Use test model for predictable responses
            agent = ConceptDiscoveryAgent(model="test")

            # Mock the agent to return a structured result
            mock_result = ConceptSearchResult(
                concepts=mock_concepts,
                reasoning="Found 2 relevant diabetes concepts from SNOMED vocabulary",
                concept_ids=[201826, 201254],
                total_found=2,
                filters_applied=["standard_only", "domain=Condition"],
            )

            with patch.object(agent.agent, "run", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = MagicMock(output=mock_result)

                result = await agent.find_concepts("diabetes", domain="Condition", max_results=10)

                assert isinstance(result, ConceptSearchResult)
                assert len(result.concepts) == 2
                assert result.concept_ids == [201826, 201254]
                assert "diabetes" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_find_concepts_without_domain(self, mock_discovery_result):
        """Test concept discovery without domain filter."""
        with patch("omop_mcp.agents.concept_agent.discover_concepts") as mock_discover:
            mock_discover.return_value = mock_discovery_result

            agent = ConceptDiscoveryAgent(model="test")
            mock_result = ConceptSearchResult(
                concepts=mock_discovery_result.concepts,
                reasoning="Found concepts across all domains",
                concept_ids=[201826, 201254],
                total_found=2,
                filters_applied=["standard_only"],
            )

            with patch.object(agent.agent, "run", new_callable=AsyncMock) as mock_run:
                mock_run.return_value = MagicMock(output=mock_result)

                result = await agent.find_concepts("diabetes", domain=None)

                assert len(result.concepts) == 2
                # No domain filter should be applied
                assert "domain" not in str(result.filters_applied).lower()

    @pytest.mark.asyncio
    async def test_refine_concepts(self, mock_concepts):
        """Test concept refinement."""
        agent = ConceptDiscoveryAgent(model="test")

        # Mock refined result (only Type 2 diabetes)
        refined_result = ConceptSearchResult(
            concepts=[mock_concepts[0]],  # Only Type 2
            reasoning="Filtered to only Type 2 diabetes, excluding Type 1",
            concept_ids=[201826],
            total_found=1,
            filters_applied=["type_2_only"],
        )

        with patch.object(agent.agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = MagicMock(output=refined_result)

            result = await agent.refine_concepts(
                mock_concepts, "only type 2 diabetes, exclude type 1"
            )

            assert len(result.concepts) == 1
            assert result.concepts[0].concept_id == 201826
            assert "type 2" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_agent_error_handling(self):
        """Test agent error handling."""
        agent = ConceptDiscoveryAgent(model="test")

        with patch.object(agent.agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = ValueError("LLM API error")

            with pytest.raises(ValueError, match="LLM API error"):
                await agent.find_concepts("test query")


class TestSQLGenerationAgent:
    """Test SQL Generation Agent."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self):
        """Test SQL agent can be initialized."""
        agent = SQLGenerationAgent(model="test")
        assert agent.model == "test"
        assert agent.agent is not None

    @pytest.mark.asyncio
    async def test_generate_cohort_sql_with_mock(self):
        """Test cohort SQL generation with mocked LLM."""
        agent = SQLGenerationAgent(model="test")

        # Mock result
        mock_result = SQLGenerationResult(
            sql="SELECT * FROM cohort",
            query_type="cohort",
            explanation="This query finds patients with exposure followed by outcome within 90 days",
            is_valid=True,
            estimated_cost_usd=0.05,
            backend="bigquery",
            suggestions=["Consider adding indexes on concept_id columns"],
        )

        with patch.object(agent.agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = MagicMock(output=mock_result)

            result = await agent.generate_sql(
                research_question="Find patients with statin exposure and myopathy outcome",
                exposure_concept_ids=[1539403],
                outcome_concept_ids=[4002599],
                time_window_days=90,
            )

            assert isinstance(result, SQLGenerationResult)
            assert result.query_type == "cohort"
            assert result.is_valid is True
            assert "cohort" in result.sql.lower()
            assert len(result.explanation) > 0

    @pytest.mark.asyncio
    async def test_generate_count_sql(self):
        """Test count query generation."""
        agent = SQLGenerationAgent(model="test")

        mock_result = SQLGenerationResult(
            sql="SELECT COUNT(*) FROM condition_occurrence",
            query_type="count",
            explanation="This query counts patients with the specified condition",
            is_valid=True,
            estimated_cost_usd=0.01,
            backend="bigquery",
            suggestions=[],
        )

        with patch.object(agent.agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = MagicMock(output=mock_result)

            result = await agent.generate_sql(
                research_question="How many patients have diabetes?",
                concept_ids=[201826],
                domain="Condition",
            )

            assert result.query_type == "count"
            assert "count" in result.sql.lower()

    @pytest.mark.asyncio
    async def test_optimize_sql(self):
        """Test SQL optimization."""
        agent = SQLGenerationAgent(model="test")

        original_sql = "SELECT * FROM condition_occurrence WHERE condition_concept_id = 201826"

        mock_result = SQLGenerationResult(
            sql="SELECT person_id FROM condition_occurrence WHERE condition_concept_id = 201826",
            query_type="optimized",
            explanation="Optimized by selecting only needed columns instead of *",
            is_valid=True,
            estimated_cost_usd=0.02,
            backend="bigquery",
            suggestions=["Add index on condition_concept_id", "Consider partitioning"],
        )

        with patch.object(agent.agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = MagicMock(output=mock_result)

            result = await agent.optimize_sql(
                original_sql,
                performance_feedback="Query scans 500GB",
            )

            assert "person_id" in result.sql
            assert "*" not in result.sql
            assert len(result.suggestions) > 0

    @pytest.mark.asyncio
    async def test_sql_agent_validation_check(self):
        """Test that agent checks SQL validation."""
        agent = SQLGenerationAgent(model="test")

        # Mock result with validation failure
        mock_result = SQLGenerationResult(
            sql="SELECT * FROM invalid_table",
            query_type="cohort",
            explanation="Generated query for cohort analysis",
            is_valid=False,
            estimated_cost_usd=None,
            backend="bigquery",
            suggestions=["Fix table name - invalid_table does not exist"],
        )

        with patch.object(agent.agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = MagicMock(output=mock_result)

            result = await agent.generate_sql(
                research_question="test query",
                concept_ids=[123],
                domain="Condition",
            )

            assert result.is_valid is False
            assert len(result.suggestions) > 0

    @pytest.mark.asyncio
    async def test_sql_agent_error_handling(self):
        """Test SQL agent error handling."""
        agent = SQLGenerationAgent(model="test")

        with patch.object(agent.agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = RuntimeError("Database connection failed")

            with pytest.raises(RuntimeError, match="Database connection failed"):
                await agent.generate_sql(
                    research_question="test",
                    concept_ids=[123],
                    domain="Condition",
                )


class TestAgentIntegration:
    """Integration tests for agent workflows."""

    @pytest.mark.asyncio
    async def test_concept_to_sql_workflow(self):
        """Test full workflow: concept discovery → SQL generation."""
        # Create mock data
        mock_concepts = [
            OMOPConcept(
                id=201826,
                name="Type 2 diabetes mellitus",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept="S",
                code="44054006",
                invalidReason=None,
            ),
            OMOPConcept(
                id=201254,
                name="Diabetes mellitus",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept="S",
                code="73211009",
                invalidReason=None,
            ),
        ]

        mock_discovery_result = ConceptDiscoveryResult(
            query="diabetes",
            concepts=mock_concepts,
        )

        # Step 1: Discover concepts
        with patch("omop_mcp.agents.concept_agent.discover_concepts") as mock_discover:
            mock_discover.return_value = mock_discovery_result

            concept_agent = ConceptDiscoveryAgent(model="test")
            concept_result = ConceptSearchResult(
                concepts=mock_concepts,
                reasoning="Found diabetes concepts",
                concept_ids=[201826, 201254],
                total_found=2,
                filters_applied=[],
            )

            with patch.object(
                concept_agent.agent, "run", new_callable=AsyncMock
            ) as mock_concept_run:
                mock_concept_run.return_value = MagicMock(output=concept_result)

                concepts = await concept_agent.find_concepts("diabetes")

                # Step 2: Generate SQL from concepts
                sql_agent = SQLGenerationAgent(model="test")
                sql_result = SQLGenerationResult(
                    sql="SELECT COUNT(*) FROM condition_occurrence WHERE condition_concept_id IN (201826, 201254)",
                    query_type="count",
                    explanation="Count patients with discovered diabetes concepts",
                    is_valid=True,
                    estimated_cost_usd=0.01,
                    backend="bigquery",
                    suggestions=[],
                )

                with patch.object(sql_agent.agent, "run", new_callable=AsyncMock) as mock_sql_run:
                    mock_sql_run.return_value = MagicMock(output=sql_result)

                    sql = await sql_agent.generate_sql(
                        research_question="Count diabetes patients",
                        concept_ids=concepts.concept_ids,
                        domain="Condition",
                    )

                    assert len(concepts.concept_ids) == 2
                    assert sql.is_valid is True
                    assert "201826" in sql.sql or "201254" in sql.sql
