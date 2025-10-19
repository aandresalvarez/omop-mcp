"""
OMOP MCP Prompts - Reusable templates for SQL synthesis and cohort analysis.

Provides MCP prompts for:
- prompt://cohort/sql - Template for cohort SQL generation with AI
- prompt://analysis/discovery - Template for concept discovery workflow
"""

from typing import Any

# ============================================================================
# Prompt Templates
# ============================================================================


def get_cohort_sql_prompt(
    exposure_concepts: list[dict[str, Any]],
    outcome_concepts: list[dict[str, Any]],
    time_window_days: int,
    backend_dialect: str,
) -> str:
    """
    Generate a prompt template for cohort SQL synthesis.

    This prompt guides AI models (like GPT-4) to generate valid OMOP CDM SQL
    for cohort identification with exposure → outcome logic.

    Args:
        exposure_concepts: List of exposure concept dictionaries
        outcome_concepts: List of outcome concept dictionaries
        time_window_days: Maximum days between exposure and outcome
        backend_dialect: SQL dialect (bigquery, postgresql, etc.)

    Returns:
        Formatted prompt string

    Example:
        >>> exposure = [{"concept_id": 1234, "concept_name": "Statin"}]
        >>> outcome = [{"concept_id": 5678, "concept_name": "Myopathy"}]
        >>> prompt = get_cohort_sql_prompt(exposure, outcome, 180, "bigquery")
    """
    exposure_list = "\n".join(
        f"  - {c['concept_id']}: {c['concept_name']}" for c in exposure_concepts
    )
    outcome_list = "\n".join(
        f"  - {c['concept_id']}: {c['concept_name']}" for c in outcome_concepts
    )

    return f"""You are an expert OMOP CDM analyst. Generate SQL to identify a cohort where:

1. **Exposure**: Patients have any of these concepts:
{exposure_list}

2. **Outcome**: Followed by any of these outcomes within {time_window_days} days:
{outcome_list}

**Requirements**:
- Use OMOP CDM v5.4 standard tables
- Target SQL dialect: {backend_dialect}
- Return: person_id, exposure_date, outcome_date, days_between
- Include only patients with BOTH exposure and outcome
- Filter: outcome_date BETWEEN exposure_date AND exposure_date + {time_window_days}
- Deduplicate using QUALIFY ROW_NUMBER() (if {backend_dialect} supports it)

**Tables**:
- drug_exposure (drug_concept_id)
- condition_occurrence (condition_concept_id)
- procedure_occurrence (procedure_concept_id)
- measurement (measurement_concept_id)

**Example Structure**:
```sql
WITH exposures AS (
  SELECT person_id, drug_concept_id AS exposure_concept_id,
         drug_exposure_start_date AS exposure_date
  FROM drug_exposure
  WHERE drug_concept_id IN ({", ".join(str(c["concept_id"]) for c in exposure_concepts)})
),
outcomes AS (
  SELECT person_id, condition_concept_id AS outcome_concept_id,
         condition_start_date AS outcome_date
  FROM condition_occurrence
  WHERE condition_concept_id IN ({", ".join(str(c["concept_id"]) for c in outcome_concepts)})
)
SELECT
  e.person_id,
  e.exposure_date,
  o.outcome_date,
  DATE_DIFF(o.outcome_date, e.exposure_date, DAY) AS days_between
FROM exposures e
JOIN outcomes o
  ON e.person_id = o.person_id
  AND o.outcome_date BETWEEN e.exposure_date
      AND DATE_ADD(e.exposure_date, INTERVAL {time_window_days} DAY)
QUALIFY ROW_NUMBER() OVER (PARTITION BY e.person_id ORDER BY e.exposure_date) = 1
```

Generate production-ready SQL following this pattern.
"""


def get_analysis_discovery_prompt(
    clinical_question: str,
    domains: list[str] | None = None,
) -> str:
    """
    Generate a prompt template for guided concept discovery.

    This prompt helps AI models conduct systematic concept discovery
    for clinical research questions.

    Args:
        clinical_question: The clinical question to investigate
        domains: OMOP domains to focus on (Condition, Drug, etc.)

    Returns:
        Formatted prompt string

    Example:
        >>> prompt = get_analysis_discovery_prompt(
        ...     "What is the risk of myopathy with statin use?",
        ...     domains=["Drug", "Condition"]
        ... )
    """
    domain_filter = ""
    if domains:
        domain_filter = f"\n**Focus Domains**: {', '.join(domains)}"

    return f"""You are conducting an OMOP CDM research analysis.

**Clinical Question**: {clinical_question}
{domain_filter}

**Your Task**: Systematically discover relevant OMOP concepts using these steps:

1. **Identify Key Entities**:
   - Break down the question into: exposure, outcome, covariates, population
   - Example: "risk of myopathy with statin use" → exposure=statins, outcome=myopathy

2. **Discover Concepts**:
   - Use `discover_concepts(clinical_text, domain)` for each entity
   - Review returned concepts for relevance and standard_concept="S"
   - Collect concept_ids for each entity group

3. **Validate Concepts**:
   - Use `get_concept_relationships(concept_id)` to explore hierarchies
   - Check for parent/child concepts you might have missed
   - Verify concepts are appropriate for your analysis

4. **Query Planning**:
   - Use `query_omop(query_type="count", ...)` to estimate patient counts
   - Verify sufficient sample size before full analysis
   - Check estimated query costs

5. **Execute Analysis**:
   - Run analytical queries (count, breakdown, etc.)
   - Document concept sets used
   - Report results with concept names and IDs

**Best Practices**:
- Always discover concepts BEFORE querying
- Use standard concepts (standard_concept="S") when possible
- Validate query costs before execution
- Document your concept selection rationale

Begin by identifying the key entities in the clinical question.
"""


def get_multi_step_query_prompt(
    concept_ids: list[int],
    domain: str,
) -> str:
    """
    Generate a prompt template for multi-step analytical queries.

    This prompt guides users through the cost-aware query execution workflow.

    Args:
        concept_ids: List of OMOP concept IDs discovered
        domain: OMOP domain of the concepts

    Returns:
        Formatted prompt string

    Example:
        >>> prompt = get_multi_step_query_prompt([313217, 316866], "Condition")
    """
    return f"""You have discovered {len(concept_ids)} concepts in domain: {domain}

**Concept IDs**: {", ".join(map(str, concept_ids))}

**Next Steps - Cost-Aware Query Execution**:

1. **Estimate Cost** (DRY RUN):
   ```
   query_omop(
       query_type="count",
       concept_ids=[{", ".join(map(str, concept_ids))}],
       domain="{domain}",
       execute=False  # DRY RUN - no data returned
   )
   ```
   This returns: estimated_cost_usd, estimated_bytes, SQL

2. **Review Estimate**:
   - Check if estimated_cost_usd is acceptable
   - Default cost cap: $1.00 USD (configurable via MAX_QUERY_COST_USD)
   - Review generated SQL for correctness

3. **Execute Query** (if cost acceptable):
   ```
   query_omop(
       query_type="count",
       concept_ids=[{", ".join(map(str, concept_ids))}],
       domain="{domain}",
       execute=True  # EXECUTE - returns results
   )
   ```

4. **Available Query Types**:
   - `count`: Count distinct patients
   - `breakdown`: Group by demographics (age, gender)
   - `list_patients`: Return patient IDs (requires ALLOW_PATIENT_LIST=true)

**Security Notes**:
- All queries are read-only (no DELETE/UPDATE/DROP)
- Row limit: 1000 rows maximum
- Cost cap: $1.00 USD default (blocks expensive queries)
- PHI protection: list_patients requires explicit permission

Proceed with Step 1 (dry run) to estimate query cost.
"""


# ============================================================================
# Prompt Registry
# ============================================================================


async def get_prompt(prompt_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Get a prompt template by ID with arguments.

    Args:
        prompt_id: Prompt identifier (e.g., "cohort/sql")
        arguments: Template arguments

    Returns:
        Dictionary with:
        - name: Prompt name
        - description: Prompt description
        - content: Rendered prompt text

    Raises:
        ValueError: If prompt_id is invalid or required arguments missing

    Example:
        >>> prompt = await get_prompt(
        ...     "cohort/sql",
        ...     {
        ...         "exposure_concepts": [...],
        ...         "outcome_concepts": [...],
        ...         "time_window_days": 180,
        ...         "backend_dialect": "bigquery"
        ...     }
        ... )
    """
    if prompt_id == "cohort/sql":
        required = ["exposure_concepts", "outcome_concepts", "time_window_days", "backend_dialect"]
        missing = [arg for arg in required if arg not in arguments]
        if missing:
            raise ValueError(f"Missing required arguments: {', '.join(missing)}")

        content = get_cohort_sql_prompt(
            exposure_concepts=arguments["exposure_concepts"],
            outcome_concepts=arguments["outcome_concepts"],
            time_window_days=arguments["time_window_days"],
            backend_dialect=arguments["backend_dialect"],
        )

        return {
            "name": "Cohort SQL Generation",
            "description": "Template for generating OMOP CDM cohort identification SQL",
            "arguments": arguments,
            "content": content,
        }

    elif prompt_id == "analysis/discovery":
        required = ["clinical_question"]
        missing = [arg for arg in required if arg not in arguments]
        if missing:
            raise ValueError(f"Missing required arguments: {', '.join(missing)}")

        content = get_analysis_discovery_prompt(
            clinical_question=arguments["clinical_question"],
            domains=arguments.get("domains"),
        )

        return {
            "name": "Concept Discovery Workflow",
            "description": "Systematic approach to discovering OMOP concepts for clinical questions",
            "arguments": arguments,
            "content": content,
        }

    elif prompt_id == "query/multi-step":
        required = ["concept_ids", "domain"]
        missing = [arg for arg in required if arg not in arguments]
        if missing:
            raise ValueError(f"Missing required arguments: {', '.join(missing)}")

        content = get_multi_step_query_prompt(
            concept_ids=arguments["concept_ids"],
            domain=arguments["domain"],
        )

        return {
            "name": "Multi-Step Query Execution",
            "description": "Cost-aware workflow for executing analytical queries",
            "arguments": arguments,
            "content": content,
        }

    else:
        raise ValueError(f"Unknown prompt_id: {prompt_id}")


async def list_prompts() -> list[dict[str, Any]]:
    """
    List all available prompts.

    Returns:
        List of prompt metadata dictionaries

    Example:
        >>> prompts = await list_prompts()
        >>> for p in prompts:
        ...     print(f"{p['id']}: {p['name']}")
    """
    return [
        {
            "id": "cohort/sql",
            "name": "Cohort SQL Generation",
            "description": "Template for generating OMOP CDM cohort identification SQL",
            "arguments": [
                {
                    "name": "exposure_concepts",
                    "type": "array",
                    "required": True,
                    "description": "List of exposure concept dictionaries",
                },
                {
                    "name": "outcome_concepts",
                    "type": "array",
                    "required": True,
                    "description": "List of outcome concept dictionaries",
                },
                {
                    "name": "time_window_days",
                    "type": "integer",
                    "required": True,
                    "description": "Maximum days between exposure and outcome",
                },
                {
                    "name": "backend_dialect",
                    "type": "string",
                    "required": True,
                    "description": "SQL dialect (bigquery, postgresql, etc.)",
                },
            ],
        },
        {
            "id": "analysis/discovery",
            "name": "Concept Discovery Workflow",
            "description": "Systematic approach to discovering OMOP concepts for clinical questions",
            "arguments": [
                {
                    "name": "clinical_question",
                    "type": "string",
                    "required": True,
                    "description": "The clinical question to investigate",
                },
                {
                    "name": "domains",
                    "type": "array",
                    "required": False,
                    "description": "OMOP domains to focus on",
                },
            ],
        },
        {
            "id": "query/multi-step",
            "name": "Multi-Step Query Execution",
            "description": "Cost-aware workflow for executing analytical queries",
            "arguments": [
                {
                    "name": "concept_ids",
                    "type": "array",
                    "required": True,
                    "description": "List of OMOP concept IDs",
                },
                {
                    "name": "domain",
                    "type": "string",
                    "required": True,
                    "description": "OMOP domain",
                },
            ],
        },
    ]
