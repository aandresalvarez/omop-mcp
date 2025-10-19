# PydanticAI Agents for OMOP MCP

This directory contains intelligent agents built with [PydanticAI](https://ai.pydantic.dev/) that assist with OMOP Common Data Model queries.

## Overview

The agents use Large Language Models (LLMs) to understand natural language queries and generate validated SQL for OMOP CDM databases. They provide reasoning, explanations, and suggestions to help researchers work with complex medical data.

## Available Agents

### 1. Concept Discovery Agent (`concept_agent.py`)

**Purpose**: Find relevant OMOP concepts from natural language descriptions.

**Capabilities**:
- Natural language concept search
- Domain-specific filtering (Condition, Drug, Procedure, etc.)
- Intelligent ranking and selection
- Concept refinement based on additional criteria

**Example**:
```python
from omop_mcp.agents import ConceptDiscoveryAgent

agent = ConceptDiscoveryAgent()

# Find concepts
result = await agent.find_concepts(
    "type 2 diabetes with complications",
    domain="Condition",
    max_results=10
)

print(f"Found {len(result.concepts)} concepts")
print(f"Reasoning: {result.reasoning}")
for concept in result.concepts:
    print(f"  {concept.concept_id}: {concept.concept_name}")
```

**Key Features**:
- Uses ATHENA vocabulary API for concept search
- Filters by standard concepts
- Provides explanations for selections
- Supports concept refinement workflows

### 2. SQL Generation Agent (`sql_agent.py`)

**Purpose**: Generate validated OMOP SQL queries from research questions.

**Capabilities**:
- Cohort SQL generation (exposure → outcome)
- Simple analytical queries (count, breakdown, list)
- SQL validation with cost estimation
- Query optimization and suggestions

**Example**:
```python
from omop_mcp.agents import SQLGenerationAgent

agent = SQLGenerationAgent()

# Generate SQL for research question
result = await agent.generate_sql(
    research_question="Find patients exposed to statins who developed myopathy within 90 days",
    exposure_concept_ids=[1539403],  # Statins
    outcome_concept_ids=[4002599],   # Myopathy
    time_window_days=90
)

print(f"Query type: {result.query_type}")
print(f"Valid: {result.is_valid}")
print(f"Explanation: {result.explanation}")
print(f"\nSQL:\n{result.sql}")
```

**Key Features**:
- Intelligent query type selection
- Temporal logic handling
- Cost estimation before execution
- Plain language explanations
- Optimization suggestions

## Architecture

### Tool Integration

The agents use existing OMOP MCP tools as sub-tools:
- `tools/athena.py` - ATHENA vocabulary API
- `tools/sqlgen.py` - SQL generation functions
- `tools/query.py` - Query execution (future)

### Agent Flow

```
User Query
    ↓
[Agent Reasoning]
    ↓
[Tool Selection & Execution]
    ↓
[Result Synthesis]
    ↓
Structured Result + Explanation
```

### Models

Each agent uses Pydantic models for:
- **Request**: Input validation and typing
- **Result**: Structured output with metadata
- **Context**: Shared state during execution

## Configuration

### Model Selection

Agents can use different LLMs based on complexity:

```python
# For complex SQL reasoning (default)
sql_agent = SQLGenerationAgent(model="openai:gpt-4o")

# For cost-effective concept discovery
concept_agent = ConceptDiscoveryAgent(model="openai:gpt-4o-mini")

# For local/private deployment
agent = SQLGenerationAgent(model="ollama:llama3")
```

### Supported Models

- OpenAI: `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`
- Anthropic: `claude-3-5-sonnet-20241022`, `claude-3-opus-latest`
- Ollama: `llama3`, `mistral`, etc.
- Gemini: `gemini-1.5-pro`, `gemini-1.5-flash`

## Usage Patterns

### 1. Two-Step Workflow: Discovery → SQL

```python
# Step 1: Find concepts
concept_agent = ConceptDiscoveryAgent()
concepts = await concept_agent.find_concepts(
    "patients with heart failure",
    domain="Condition"
)

# Step 2: Generate SQL
sql_agent = SQLGenerationAgent()
result = await sql_agent.generate_sql(
    research_question="Count heart failure patients",
    concept_ids=[concept.concept_id for concept in concepts.concepts],
    domain="Condition"
)
```

### 2. Concept Refinement

```python
# Initial broad search
initial = await agent.find_concepts("diabetes")

# Refine to specific type
refined = await agent.refine_concepts(
    initial.concepts,
    "only type 2 diabetes, exclude type 1 and gestational"
)
```

### 3. SQL Optimization

```python
# Generate initial SQL
result = await sql_agent.generate_sql(...)

# Optimize if needed
optimized = await sql_agent.optimize_sql(
    result.sql,
    performance_feedback="Query scans 500GB and takes 45 seconds"
)
```

## Testing

The agents include comprehensive test coverage:

```bash
# Run agent tests
pytest tests/test_agents.py -v

# Test with mock LLM (fast, deterministic)
pytest tests/test_agents.py::test_concept_agent_with_mock

# Test with real LLM (requires API key)
pytest tests/test_agents.py::test_concept_agent_integration -m integration
```

## Best Practices

### 1. Cost Management

- Use `gpt-4o-mini` for simple tasks
- Use `gpt-4o` only for complex SQL generation
- Consider caching repeated queries
- Monitor token usage with `logfire`

### 2. Error Handling

```python
try:
    result = await agent.find_concepts("query")
except ValidationError as e:
    logger.error("Invalid input", error=e)
except LLMError as e:
    logger.error("LLM API error", error=e)
```

### 3. Observability

All agents emit structured logs via `structlog`:

```python
import structlog

logger = structlog.get_logger(__name__)

# Logs include:
# - agent_searching_concepts
# - agent_generating_sql
# - find_concepts_success
# - generate_sql_failed
```

## Future Enhancements

### Planned Agents

1. **Query Optimizer Agent** - Advanced query optimization
2. **Data Quality Agent** - Validate data quality issues
3. **Cohort Builder Agent** - Interactive cohort definition
4. **Analysis Agent** - Statistical analysis suggestions

### Planned Features

- Multi-agent workflows (concept → SQL → execution → analysis)
- Interactive clarification questions
- Query result explanation
- Performance benchmarking

## Dependencies

```toml
dependencies = [
    "pydantic-ai>=0.0.13",  # Agent framework
    "openai>=1.0.0",        # OpenAI API
    "structlog>=24.0.0",    # Structured logging
    "logfire>=0.60.0",      # Observability
]
```

## Contributing

When adding new agents:

1. Extend base agent pattern from existing agents
2. Define clear Request/Result models
3. Register tools with `@agent.tool` decorator
4. Write comprehensive system prompts
5. Add tests with mocked LLM responses
6. Document usage patterns and examples

## License

Same as parent project (MIT).

---

**Status**: ✅ Production Ready
**Tests**: Full coverage with mocks and integration tests
**Documentation**: Complete with examples
