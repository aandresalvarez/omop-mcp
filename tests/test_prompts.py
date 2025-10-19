"""
Tests for MCP prompts module.
"""

import pytest
from omop_mcp import prompts


@pytest.mark.asyncio
async def test_get_cohort_sql_prompt():
    """Test cohort SQL prompt generation."""
    exposure = [{"concept_id": 1234, "concept_name": "Statin"}]
    outcome = [{"concept_id": 5678, "concept_name": "Myopathy"}]

    prompt_text = prompts.get_cohort_sql_prompt(
        exposure_concepts=exposure,
        outcome_concepts=outcome,
        time_window_days=180,
        backend_dialect="bigquery",
    )

    # Verify key components
    assert "Statin" in prompt_text
    assert "Myopathy" in prompt_text
    assert "180 days" in prompt_text
    assert "bigquery" in prompt_text
    assert "OMOP CDM" in prompt_text
    assert "1234" in prompt_text
    assert "5678" in prompt_text


@pytest.mark.asyncio
async def test_get_analysis_discovery_prompt():
    """Test analysis discovery prompt generation."""
    prompt_text = prompts.get_analysis_discovery_prompt(
        clinical_question="What is the risk of myopathy with statin use?",
        domains=["Drug", "Condition"],
    )

    # Verify key components
    assert "myopathy with statin use" in prompt_text
    assert "Drug" in prompt_text
    assert "Condition" in prompt_text
    assert "discover_concepts" in prompt_text
    assert "systematic" in prompt_text.lower()


@pytest.mark.asyncio
async def test_get_multi_step_query_prompt():
    """Test multi-step query prompt generation."""
    prompt_text = prompts.get_multi_step_query_prompt(
        concept_ids=[313217, 316866],
        domain="Condition",
    )

    # Verify key components
    assert "313217" in prompt_text
    assert "316866" in prompt_text
    assert "Condition" in prompt_text
    assert "execute=False" in prompt_text
    assert "DRY RUN" in prompt_text
    assert "query_omop" in prompt_text


@pytest.mark.asyncio
async def test_get_prompt_cohort_sql():
    """Test get_prompt with cohort/sql ID."""
    result = await prompts.get_prompt(
        "cohort/sql",
        {
            "exposure_concepts": [{"concept_id": 1, "concept_name": "Drug A"}],
            "outcome_concepts": [{"concept_id": 2, "concept_name": "Event B"}],
            "time_window_days": 90,
            "backend_dialect": "postgresql",
        },
    )

    assert result["name"] == "Cohort SQL Generation"
    assert "content" in result
    assert "Drug A" in result["content"]
    assert "Event B" in result["content"]
    assert "90 days" in result["content"]


@pytest.mark.asyncio
async def test_get_prompt_analysis_discovery():
    """Test get_prompt with analysis/discovery ID."""
    result = await prompts.get_prompt(
        "analysis/discovery",
        {
            "clinical_question": "Test question?",
            "domains": ["Condition"],
        },
    )

    assert result["name"] == "Concept Discovery Workflow"
    assert "content" in result
    assert "Test question?" in result["content"]
    assert "Condition" in result["content"]


@pytest.mark.asyncio
async def test_get_prompt_query_multi_step():
    """Test get_prompt with query/multi-step ID."""
    result = await prompts.get_prompt(
        "query/multi-step",
        {
            "concept_ids": [123, 456],
            "domain": "Drug",
        },
    )

    assert result["name"] == "Multi-Step Query Execution"
    assert "content" in result
    assert "123" in result["content"]
    assert "456" in result["content"]
    assert "Drug" in result["content"]


@pytest.mark.asyncio
async def test_get_prompt_missing_arguments():
    """Test get_prompt with missing required arguments."""
    with pytest.raises(ValueError, match="Missing required arguments"):
        await prompts.get_prompt(
            "cohort/sql",
            {
                "exposure_concepts": [],
                # Missing outcome_concepts, time_window_days, backend_dialect
            },
        )


@pytest.mark.asyncio
async def test_get_prompt_invalid_id():
    """Test get_prompt with invalid prompt ID."""
    with pytest.raises(ValueError, match="Unknown prompt_id"):
        await prompts.get_prompt("invalid/prompt", {})


@pytest.mark.asyncio
async def test_list_prompts():
    """Test listing all available prompts."""
    prompt_list = await prompts.list_prompts()

    assert len(prompt_list) == 3
    assert any(p["id"] == "cohort/sql" for p in prompt_list)
    assert any(p["id"] == "analysis/discovery" for p in prompt_list)
    assert any(p["id"] == "query/multi-step" for p in prompt_list)

    # Verify structure
    for prompt in prompt_list:
        assert "id" in prompt
        assert "name" in prompt
        assert "description" in prompt
        assert "arguments" in prompt
        assert isinstance(prompt["arguments"], list)


@pytest.mark.asyncio
async def test_prompt_arguments_schema():
    """Test that prompt arguments have proper schema."""
    prompt_list = await prompts.list_prompts()
    cohort_prompt = next(p for p in prompt_list if p["id"] == "cohort/sql")

    # Verify argument schema
    for arg in cohort_prompt["arguments"]:
        assert "name" in arg
        assert "type" in arg
        assert "required" in arg
        assert "description" in arg

    # Verify required fields
    required_args = [a["name"] for a in cohort_prompt["arguments"] if a["required"]]
    assert "exposure_concepts" in required_args
    assert "outcome_concepts" in required_args
    assert "time_window_days" in required_args
    assert "backend_dialect" in required_args
