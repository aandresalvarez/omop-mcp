# OMOP MCP Server

> A Model Context Protocol (MCP) server for intelligent OMOP Common Data Model (CDM) exploration, concept discovery, and cohort query generation.

[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 What Can This MCP Do?

This MCP server enables AI assistants (Claude, custom agents) to work seamlessly with OMOP CDM databases through natural language. Below are real-world use cases to help you understand its capabilities.

---

## 📋 Use Cases

### 1. 🔍 **Clinical Concept Discovery**

**Scenario**: You need to find OMOP standard concepts for a clinical term.

**What you can ask:**
- *"Find all OMOP concepts for Type 2 Diabetes"*
- *"Map ICD-10 code E11.9 to OMOP standard concepts"*
- *"What are the SNOMED codes for influenza?"*

**What happens:**
1. The MCP searches the ATHENA vocabulary service
2. Returns standard concepts with IDs, names, vocabularies, and domains
3. Shows relationships (parent concepts, mappings, child concepts)
4. Filters by domain (Condition, Drug, Procedure) if specified

**Example output:**
```json
{
  "concepts": [
    {
      "concept_id": 201826,
      "concept_name": "Type 2 diabetes mellitus",
      "domain_id": "Condition",
      "vocabulary_id": "SNOMED",
      "standard_concept": "S"
    }
  ],
  "relationships": {...}
}
```

---

### 2. 📊 **Patient Count Queries**

**Scenario**: You want to know how many patients have a specific condition in your database.

**What you can ask:**
- *"How many patients have influenza?"*
- *"Count patients with Type 2 Diabetes"*
- *"How many people are on Metformin?"*

**What happens:**
1. MCP discovers the relevant OMOP concepts (e.g., influenza → concept IDs 4171852, 4171853)
2. Generates and validates SQL query against your database
3. Optionally executes the query and returns results
4. Shows estimated query cost (for BigQuery)

**Example workflow:**
```
User: "How many patients with flu?"
→ Step 1: discover_concepts("flu") → [4171852, 4171853]
→ Step 2: query_omop(type="count", concept_ids=[...]) → {"patient_count": 1234}
```

---

### 3. 🧬 **Demographic Breakdowns**

**Scenario**: You need demographic analysis of patients with a condition.

**What you can ask:**
- *"Show age and gender distribution of diabetic patients"*
- *"Break down flu patients by demographics"*
- *"What's the age distribution of patients on statins?"*

**What happens:**
1. MCP finds the relevant concepts
2. Generates SQL joining person table for demographics
3. Groups by gender and age
4. Returns breakdown with patient counts

**Example output:**
```json
{
  "results": [
    {"gender_concept_id": 8507, "age_years": 65, "patient_count": 145},
    {"gender_concept_id": 8532, "age_years": 58, "patient_count": 132},
    ...
  ]
}
```

---

### 4. 🔗 **Concept Relationship Exploration**

**Scenario**: You need to explore concept hierarchies and mappings.

**What you can ask:**
- *"Show me all child concepts under 'Diabetes Mellitus'"*
- *"What does ICD-10 E11.9 map to in SNOMED?"*
- *"Find parent concepts for Metformin 500mg"*

**What happens:**
1. MCP fetches relationships from ATHENA
2. Filters by relationship type (Maps to, Subsumes, Is a)
3. Returns hierarchical concept tree
4. Shows vocabulary crosswalks (ICD-10 → SNOMED, etc.)

**Use for:**
- Building comprehensive concept sets
- Understanding vocabulary mappings
- Creating inclusion/exclusion criteria

---

### 5. 💊 **Cohort SQL Generation**

**Scenario**: You need to define a research cohort with temporal logic.

**What you can ask:**
- *"Generate SQL for patients on Metformin who developed acute kidney injury within 90 days"*
- *"Create a cohort of diabetics who had a stroke within 1 year"*
- *"Find patients with exposure X followed by outcome Y"*

**What happens:**
1. MCP uses concept IDs for exposure and outcome
2. Generates SQL with temporal constraints
3. Includes deduplication logic (first exposure per patient)
4. Validates query and estimates cost
5. Returns executable SQL for your platform (BigQuery or Postgres)

**Example SQL output:**
```sql
WITH exposure AS (
  SELECT DISTINCT person_id, drug_exposure_start_date AS exposure_date
  FROM drug_exposure
  WHERE drug_concept_id IN (1503297)  -- Metformin
),
outcome AS (
  SELECT DISTINCT person_id, condition_start_date AS outcome_date
  FROM condition_occurrence
  WHERE condition_concept_id IN (46271022)  -- Acute kidney injury
),
cohort AS (
  SELECT e.person_id, e.exposure_date, o.outcome_date,
    DATE_DIFF(o.outcome_date, e.exposure_date, DAY) AS days_to_outcome
  FROM exposure e
  INNER JOIN outcome o ON e.person_id = o.person_id
  WHERE e.exposure_date <= o.outcome_date
    AND DATE_DIFF(o.outcome_date, e.exposure_date, DAY) <= 90
)
SELECT * FROM cohort
QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY exposure_date) = 1;
```

---

### 6. 🌐 **Cross-Vocabulary Mapping**

**Scenario**: You have codes from multiple vocabularies and need to standardize them.

**What you can ask:**
- *"Map these ICD-10 codes to SNOMED: E11.9, E10.9, I10"*
- *"Convert RxNorm codes to OMOP standard drug concepts"*
- *"What are the standard equivalents for these ICD-9 codes?"*

**What happens:**
1. MCP searches each code in its source vocabulary
2. Follows "Maps to" relationships to standard concepts
3. Returns both source and standard concepts
4. Ensures all concepts are ready for cohort queries

**Why it matters:**
- Electronic Health Records use different coding systems
- OMOP requires standard concepts for queries
- One query captures data from all source vocabularies

---

### 7. 🔄 **Multi-Backend Portability**

**Scenario**: You need the same cohort query for different database platforms.

**What you can ask:**
- *"Generate this cohort query for both BigQuery and Postgres"*
- *"Show me the cost difference between running this on BigQuery vs Postgres"*

**What happens:**
1. MCP generates dialect-specific SQL
2. BigQuery version uses UNNEST, QUALIFY, backtick-quoted tables
3. Postgres version uses arrays, subqueries, schema.table format
4. Both return identical results from OMOP CDM data

**Supported backends:**
- ✅ **BigQuery** (full support, cost estimates)
- ✅ **Postgres** (full support, EXPLAIN plans)
- 🔜 **Snowflake** (planned)
- 🔜 **DuckDB** (planned)

---

### 8. 💰 **Cost Estimation & Validation**

**Scenario**: You want to check query cost before running expensive analytics.

**What you can ask:**
- *"How much will it cost to query all diabetes patients with cardiovascular events?"*
- *"Estimate the cost before running this cohort query"*
- *"Validate this SQL without executing it"*

**What happens:**
1. MCP runs BigQuery dry-run validation
2. Returns estimated bytes scanned
3. Calculates approximate cost (BigQuery: $5/TB)
4. Warns if cost exceeds configured threshold (default: $1)
5. Requires confirmation for expensive queries

**Safety features:**
- 🚫 Blocks queries over cost limit
- 📊 Shows query plan details
- ⏱️ Estimates execution time
- 🔒 Prevents accidental expensive runs

---

### 9. 🛡️ **Secure, Governed Queries**

**Scenario**: You need enterprise-grade security and audit trails.

**What you can ask:**
- *"Run this query with my team's credentials"*
- *"Show me the audit log for executed queries"*
- *"Check if I have permission to list patient IDs"*

**What happens:**
1. MCP validates OAuth2.1 bearer token
2. Checks user roles and permissions
3. Blocks PHI-returning queries in production (e.g., patient lists)
4. Logs all queries with user ID, timestamp, cost, results
5. Enforces row limits (max 1000 rows)
6. Blocks mutating queries (DELETE, UPDATE, DROP)

**Security controls:**
- 🔐 OAuth2.1 authentication
- 👥 Role-based authorization
- 📝 Complete audit trail
- 🚫 Mutation blocking
- 💵 Cost caps
- ⏰ Query timeouts (30s default)

---

### 10. 🧪 **Exploratory Data Analysis**

**Scenario**: You're exploring a new OMOP dataset and want to understand what's in it.

**What you can ask:**
- *"What are the top 10 most common conditions in this database?"*
- *"Show me the drug exposure distribution"*
- *"What's the age range of patients in the dataset?"*
- *"How many patients have enrollment data?"*

**What happens:**
1. MCP generates exploratory SQL queries
2. Runs aggregations across core OMOP tables
3. Returns summary statistics
4. Helps you understand data completeness

**Great for:**
- Data quality assessment
- Study feasibility analysis
- Understanding data coverage
- Identifying common vs. rare conditions

---

## 🚀 Quick Start

### For Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "omop": {
      "command": "uvx",
      "args": ["omop-mcp"],
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "BIGQUERY_PROJECT_ID": "your-project",
        "BIGQUERY_DATASET_ID": "omop_cdm"
      }
    }
  }
}
```

### For Custom Applications

```python
from omop_mcp import OMOPClient

client = OMOPClient()

# Discover concepts
result = await client.discover_concepts("type 2 diabetes")
concept_ids = [c.concept_id for c in result.concepts]

# Query database
counts = await client.query_omop(
    query_type="count",
    concept_ids=concept_ids,
    domain="Condition"
)
print(f"Found {counts['results'][0]['patient_count']} patients")
```

---

## 🛠️ Available MCP Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `discover_concepts` | Search ATHENA for OMOP concepts | *"Find diabetes concepts"* |
| `get_concept_relationships` | Explore concept hierarchies | *"Show child concepts for 201826"* |
| `query_omop` | Execute analytical queries | *"Count patients with flu"* |
| `generate_cohort_sql` | Create temporal cohort queries | *"Metformin → AKI within 90 days"* |

---

## 📊 Example Workflow

### Research Question: *"How many patients developed acute kidney injury after starting Metformin?"*

```
1. User asks the question
   ↓
2. MCP discovers concepts:
   - Metformin → 1503297 (Drug)
   - Acute kidney injury → 46271022 (Condition)
   ↓
3. MCP generates cohort SQL with 90-day temporal window
   ↓
4. MCP validates query (estimated cost: $0.08)
   ↓
5. User approves execution
   ↓
6. MCP returns results:
   - 1,234 patients
   - Median time to event: 45 days
   - SQL available for reproduction
```

---

## 🎓 Who Should Use This?

- **Clinical Researchers**: Build cohorts faster with natural language
- **Data Scientists**: Generate validated SQL without memorizing OMOP schema
- **Healthcare Analysts**: Explore OMOP datasets interactively
- **Informaticists**: Map clinical terminologies automatically
- **Study Coordinators**: Assess feasibility with quick patient counts
- **AI Developers**: Integrate OMOP capabilities into health AI applications

---

## 🔗 Resources

- [OMOP Common Data Model](https://ohdsi.github.io/CommonDataModel/)
- [ATHENA Vocabulary Browser](https://athena.ohdsi.org)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [Implementation Plan](./plan/plan.md)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 💡 Need Help?

- 📚 [Documentation](./docs/)
- 💬 [Discussions](https://github.com/aandresalvarez/omop-mcp/discussions)
- 🐛 [Issues](https://github.com/aandresalvarez/omop-mcp/issues)

---

**Built with ❤️ for the OHDSI community**
