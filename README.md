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
- ✅ **BigQuery** (full support, cost estimates, dry-run validation)
- ✅ **Snowflake** (full support, EXPLAIN validation, enterprise ready)
- ✅ **DuckDB** (full support, local execution, zero setup, free!)
- ✅ **Universal SQL Translation** (10+ dialects via SQLGlot)

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

## ✨ New Features

### 🤖 AI-Powered Agents (PydanticAI)

Natural language interface for OMOP queries with intelligent concept discovery and SQL generation:

```python
from omop_mcp.agents import ConceptDiscoveryAgent, SQLGenerationAgent

# AI-powered concept discovery
agent = ConceptDiscoveryAgent()
result = await agent.run("Find all diabetes medications")
# Returns structured list of drug concepts with confidence scores

# AI-powered SQL generation
sql_agent = SQLGenerationAgent()
cohort_sql = await sql_agent.run(
    "Patients on metformin who developed kidney problems within 90 days"
)
# Returns complete, validated cohort SQL
```

### 🗄️ Multi-Database Support

Query OMOP CDM across different database platforms with automatic SQL translation:

**DuckDB (Local Development):**
```python
from omop_mcp.backends import DuckDBBackend

# Zero setup - works immediately!
backend = DuckDBBackend()  # In-memory by default
results = await backend.execute_query("SELECT COUNT(*) FROM person")
# Fast, free, local execution - perfect for development!
```

**Snowflake (Enterprise):**
```python
from omop_mcp.backends import SnowflakeBackend

# Enterprise cloud data warehouse
backend = SnowflakeBackend()
parts = await backend.build_cohort_sql(
    exposure_ids=[1234],
    outcome_ids=[5678],
    pre_outcome_days=30
)
# Production-ready with EXPLAIN validation
```

**BigQuery (Cloud-Scale):**
```python
from omop_mcp.backends import BigQueryBackend

# Google Cloud Platform
backend = BigQueryBackend()
validation = await backend.validate_sql(sql)  # Dry-run with cost estimate
```

### 🔄 Universal SQL Translation

Translate queries between 10+ SQL dialects automatically:

```python
from omop_mcp.backends import translate_sql

# Translate BigQuery SQL to Snowflake
bigquery_sql = "SELECT DATE_DIFF(end_date, start_date, DAY) FROM visits"
snowflake_sql = translate_sql(bigquery_sql, "bigquery", "snowflake")
# Result: "SELECT DATEDIFF(DAY, start_date, end_date) FROM visits"

# Translate to DuckDB
duckdb_sql = translate_sql(bigquery_sql, "bigquery", "duckdb")
# Result: "SELECT date_diff('day', start_date, end_date) FROM visits"
```

**Supported Dialects:**
- BigQuery, Snowflake, DuckDB
- PostgreSQL, MySQL, SQLite
- Redshift, Spark, Trino, Presto

### 📊 Data Export Tools

Export OMOP data in standardized formats:

```python
from omop_mcp.tools.export import (
    export_concept_set,
    export_sql_query,
    export_query_results,
    export_cohort_definition
)

# Export concept set to CSV
await export_concept_set(
    concepts=concept_list,
    format="csv",
    output_path="diabetes_concepts.csv"
)

# Export SQL query with metadata
await export_sql_query(
    sql=cohort_sql,
    metadata={"description": "Diabetes cohort", "author": "researcher"},
    output_path="cohort_query.json"
)

# Export query results
await export_query_results(
    results=query_results,
    format="json",
    output_path="cohort_results.json",
    include_metadata=True
)
```

**Supported Formats:** JSON, CSV with automatic type handling

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (uses modern type hints)
- **OMOP CDM database** (BigQuery or Postgres)
- **ATHENA API access** (public, no key required)

### Installation

#### Quick Install with UV Extras

```bash
# Local development (DuckDB only)
uv pip install omop-mcp[duckdb]

# Cloud analytics (BigQuery + Snowflake)
uv pip install omop-mcp[cloud]

# All backends
uv pip install omop-mcp[all-backends]

# Development with all tools
uv pip install omop-mcp[dev,all-backends]
```

#### Traditional Installation

```bash
# Install from PyPI (when published)
pip install omop-mcp

# Or install from source
git clone https://github.com/aandresalvarez/omop-mcp.git
cd omop-mcp
uv sync
```

### Configuration

Copy `.env.example` to `.env` and customize for your environment:

```bash
cp .env.example .env
```

Or set environment variables directly:

```bash
# Required: Database backend
BACKEND_TYPE=bigquery  # or "snowflake" or "duckdb"

# For BigQuery
BIGQUERY_PROJECT_ID=your-gcp-project
BIGQUERY_DATASET_ID=omop_cdm
BIGQUERY_CREDENTIALS_PATH=/path/to/service-account.json

# Alternative: Use Application Default Credentials (ADC)
# BIGQUERY_CREDENTIALS_PATH=  # Leave empty to use ADC
#
# ADC Authentication Methods:
# 1. User credentials (development):
#    gcloud auth application-default login
#
# 2. Service account via environment variable:
#    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
#
# 3. Metadata service (GCP environments - Cloud Run, Compute Engine, etc.):
#    Automatically available - no additional setup needed
#
# 4. Workload Identity (Kubernetes):
#    Configured via service account annotations

# For Snowflake
SNOWFLAKE_ACCOUNT=your-account.snowflakecomputing.com
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=omop_db
SNOWFLAKE_SCHEMA=cdm
SNOWFLAKE_WAREHOUSE=compute_wh

# For DuckDB (local/embedded - no credentials needed!)
DUCKDB_DATABASE_PATH=:memory:  # or "./omop.duckdb" for persistent
DUCKDB_SCHEMA=main

# Optional: Security
MAX_COST_USD=1.0          # Cost limit for BigQuery queries
MAX_QUERY_TIMEOUT_SEC=30  # Query timeout
PHI_MODE=false            # Set true to allow patient_id queries

# Optional: OAuth (for production)
OAUTH_ISSUER=https://your-auth-provider.com
OAUTH_AUDIENCE=omop-mcp-api
```

### Running the Server

#### Authentication Methods

The OMOP MCP server supports multiple authentication methods for BigQuery access:

**Method 1: Service Account (Recommended for Production)**
```bash
# Download service account key
gcloud iam service-accounts keys create omop-mcp-key.json \
    --iam-account=omop-mcp-server@your-project-id.iam.gserviceaccount.com

# Set environment variable
BIGQUERY_CREDENTIALS_PATH=/path/to/omop-mcp-key.json
```

**Method 2: Application Default Credentials (ADC)**
```bash
# Option 1: User credentials (development)
gcloud auth application-default login

# Option 2: Service account via environment variable
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Option 3: Metadata service (GCP environments)
# Automatically available in Cloud Run, Compute Engine, etc.

# Leave credentials path empty to use ADC
BIGQUERY_CREDENTIALS_PATH=
```

**Authentication Priority:**
1. Service account JSON file (if `BIGQUERY_CREDENTIALS_PATH` is set and file exists)
2. Application Default Credentials (ADC)
   - `GOOGLE_APPLICATION_CREDENTIALS` environment variable
   - Metadata service (GCP environments)
   - User credentials (`gcloud auth application-default login`)

#### Start the Server

#### Option 1: As MCP Server (for Claude Desktop, etc.)

Add to your MCP client configuration (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "omop": {
      "command": "uv",
      "args": ["run", "omop-mcp"],
      "env": {
        "BIGQUERY_PROJECT_ID": "your-project",
        "BIGQUERY_DATASET_ID": "omop_cdm",
        "BIGQUERY_CREDENTIALS_PATH": "/path/to/credentials.json"
      }
    }
  }
}
```

Restart Claude Desktop, and you'll see OMOP tools available.

#### Option 2: Direct Python Usage

```python
import asyncio
from omop_mcp.tools.athena import discover_concepts
from omop_mcp.tools.query import query_by_concepts

async def main():
    # Step 1: Discover concepts
    result = await discover_concepts(
        query="type 2 diabetes",
        domain="Condition",
        standard_only=True
    )

    print(f"Found {len(result.concepts)} concepts:")
    for concept in result.concepts:
        print(f"  - {concept.concept_name} ({concept.concept_id})")

    # Step 2: Query database
    concept_ids = [c.concept_id for c in result.concepts]
    query_result = await query_by_concepts(
        query_type="count",
        concept_ids=concept_ids,
        domain="Condition",
        backend="bigquery",
        execute=True
    )

    print(f"\nSQL Generated:\n{query_result.sql}")
    print(f"\nPatient count: {query_result.results[0]['patient_count']}")
    print(f"Estimated cost: ${query_result.estimated_cost_usd:.4f}")

asyncio.run(main())
```

#### Option 3: As Standalone Server

```bash
# Run MCP server on stdio
uv run python -m omop_mcp.server

# Or with explicit backend
BACKEND_TYPE=postgres uv run python -m omop_mcp.server
```

---

## 🛠️ Available MCP Tools

### Core Tools

| Tool | Purpose | Input Parameters | Returns |
|------|---------|------------------|---------|
| `discover_concepts` | Search ATHENA for concepts | `query`, `domain`, `vocabulary`, `standard_only`, `limit` | `ConceptDiscoveryResult` |
| `get_concept_relationships` | Explore concept hierarchies | `concept_id`, `relationship_id` | List of `ConceptRelationship` |
| `query_omop` | Execute analytical queries | `query_type`, `concept_ids`, `domain`, `backend`, `execute` | `QueryOMOPResult` |
| `generate_cohort_sql` | Create temporal cohort queries | `exposure_ids`, `outcome_ids`, `time_window`, `dialect` | SQL string |

### Direct SQL Tools (New! 🎉)

| Tool | Purpose | Input Parameters | Returns |
|------|---------|------------------|---------|
| `get_information_schema` | Get database schema info | `table_name`, `backend` | Table/column definitions |
| `select_query` | Execute direct SQL with validation | `sql`, `validate`, `execute`, `backend`, `limit` | Query results + metadata |

### Export Tools (New! 🎉)

| Tool | Purpose | Input Parameters | Returns |
|------|---------|------------------|---------|
| `export_concept_set` | Export concepts to JSON/CSV | `concepts`, `format`, `output_path` | Saved file path |
| `export_sql_query` | Export SQL with metadata | `sql`, `metadata`, `output_path` | Saved file path |
| `export_query_results` | Export results to JSON/CSV | `results`, `format`, `output_path`, `include_metadata` | Saved file path |
| `export_cohort_definition` | Export complete cohort definition | `definition`, `output_path` | Saved file path |

### SQL Tools (New! 🎉)

| Tool | Purpose | Input Parameters | Returns |
|------|---------|------------------|---------|
| `translate_sql` | Cross-dialect SQL translation | `sql`, `source_dialect`, `target_dialect` | Translated SQL |
| `validate_sql` | Validate SQL syntax | `sql`, `dialect` | Validation result |
| `format_sql` | Pretty-print SQL | `sql`, `dialect`, `pretty` | Formatted SQL |

### AI Agent Tools (New! 🤖)

| Tool | Purpose | Input Parameters | Returns |
|------|---------|------------------|---------|
| `concept_discovery_agent` | AI-powered concept search | `question`, `domains` | Structured concept list |
| `sql_generation_agent` | AI-powered SQL generation | `description`, `exposure`, `outcome` | Complete cohort SQL |

### Resources (Cacheable Data)

| Resource | URI Pattern | Description |
|----------|-------------|-------------|
| Concept by ID | `omop://concept/{id}` | Fetch single concept details |
| Search concepts | `athena://search?query={q}&domain={d}` | Paginated concept search |
| Backend capabilities | `backend://capabilities` | List available database backends |

### Prompts (AI Guidance)

| Prompt | Purpose | Arguments | Output |
|--------|---------|-----------|--------|
| `cohort/sql` | Guide SQL generation | `exposure`, `outcome`, `time_window`, `dialect` | SQL generation template |
| `analysis/discovery` | Guide concept discovery | `question`, `domains` | Systematic discovery workflow |
| `query/multi-step` | Guide query execution | `concept_ids`, `domain` | Cost-aware execution guide |

---

## 📚 Documentation

### Core Documentation

- **[SQL Validation & Security](docs/sql-validation.md)** - Comprehensive security features, table allowlists, PHI protection
- **[Execution & Caching Architecture](docs/execution-caching.md)** - Performance optimization, caching strategies, monitoring
- **[API Reference](docs/api/tools.md)** - Complete tool documentation with examples

### Integration Guides

- **[Claude Desktop Integration](docs/integrations/claude-desktop.md)** - Complete setup guide for Claude Desktop
- **[LibreChat + Ollama Integration](docs/integrations/librechat-ollama.md)** - Local deployment with LibreChat and Ollama
- **[Generic MCP Client Guide](docs/integrations/generic-mcp-client.md)** - Integration with any MCP-compatible client

### Configuration

- **[Environment Configuration](.env.example)** - Complete configuration reference with examples
- **[Comprehensive Configuration Guide](docs/configuration.md)** - Detailed setup for all environments, databases, and AI clients
- **[UV Extras Installation](pyproject.toml)** - Backend-specific installation options

---

## 🔒 Security Features

The OMOP MCP server implements comprehensive security measures to protect healthcare data:

### SQL Safety Layer
- **Only SELECT statements allowed** - Blocks all mutating operations (DELETE, UPDATE, DROP, etc.)
- **OMOP table allowlist** - Restricts access to approved OMOP CDM tables only
- **PHI column blocking** - Prevents access to sensitive source value columns
- **Automatic row limiting** - Prevents excessive data retrieval
- **Cost validation** - BigQuery dry-run validation with cost limits

### Configuration Options
```bash
# Enable strict table validation
STRICT_TABLE_VALIDATION=true

# Block PHI columns
OMOP_BLOCKED_COLUMNS=person_source_value,provider_source_value

# Set cost limits
MAX_COST_USD=1.0

# Disable patient ID queries in production
ALLOW_PATIENT_LIST=false
```

### Error Types
- `SecurityViolationError` - Dangerous SQL operations detected
- `TableNotAllowedError` - Non-allowlisted table accessed
- `ColumnBlockedError` - Blocked PHI column accessed
- `CostLimitExceededError` - Query cost exceeds limit

See [SQL Validation Documentation](docs/sql-validation.md) for complete security details.

---

## 📚 Detailed Examples

### Example 1: Basic Concept Discovery

```python
from omop_mcp.tools.athena import discover_concepts

# Search for flu concepts
result = await discover_concepts(
    query="influenza",
    domain="Condition",
    standard_only=True,
    limit=10
)

print(f"Found {len(result.concepts)} concepts")
for concept in result.concepts:
    print(f"{concept.concept_id}: {concept.concept_name}")
    print(f"  Domain: {concept.domain_id}, Vocabulary: {concept.vocabulary_id}")
    print(f"  Standard: {concept.is_standard()}, Valid: {concept.is_valid()}")
```

**Output:**
```
Found 3 concepts
4171852: Influenza
  Domain: Condition, Vocabulary: SNOMED
  Standard: True, Valid: True
4171853: Influenza due to seasonal influenza virus
  Domain: Condition, Vocabulary: SNOMED
  Standard: True, Valid: True
```

### Example 2: Patient Count Query

```python
from omop_mcp.tools.query import query_by_concepts

# Count patients with diabetes (concept IDs from discovery)
result = await query_by_concepts(
    query_type="count",
    concept_ids=[201826, 201254],  # Type 2 diabetes concepts
    domain="Condition",
    backend="bigquery",
    execute=False  # Dry-run first
)

print(f"SQL: {result.sql}")
print(f"Estimated cost: ${result.estimated_cost_usd:.4f}")
print(f"Estimated bytes: {result.estimated_bytes:,}")

# If cost acceptable, execute
if result.estimated_cost_usd < 0.10:
    result = await query_by_concepts(
        query_type="count",
        concept_ids=[201826, 201254],
        domain="Condition",
        backend="bigquery",
        execute=True  # Actually run it
    )
    print(f"Patient count: {result.results[0]['patient_count']}")
```

### Example 3: Demographic Breakdown

```python
# Get age/gender breakdown for diabetes patients
result = await query_by_concepts(
    query_type="breakdown",
    concept_ids=[201826],
    domain="Condition",
    backend="bigquery",
    execute=True
)

print("Demographics:")
for row in result.results:
    gender = "Male" if row['gender_concept_id'] == 8507 else "Female"
    print(f"  {gender}, Age {row['age_years']}: {row['patient_count']} patients")
```

**Output:**
```
Demographics:
  Male, Age 65: 145 patients
  Female, Age 58: 132 patients
  Male, Age 72: 98 patients
  ...
```

### Example 4: Multi-Step Workflow (Discovery → Query)

```python
async def analyze_condition(condition_name: str):
    """Complete workflow: discover concepts and query database."""

    # Step 1: Discover concepts
    print(f"Discovering concepts for '{condition_name}'...")
    discovery = await discover_concepts(
        query=condition_name,
        domain="Condition",
        standard_only=True
    )

    if not discovery.concepts:
        print("No concepts found!")
        return

    print(f"Found {len(discovery.concepts)} concepts:")
    for c in discovery.concepts:
        print(f"  - {c.concept_name} ({c.concept_id})")

    # Step 2: Estimate query cost
    concept_ids = [c.concept_id for c in discovery.concepts]
    print("\nEstimating query cost...")
    estimate = await query_by_concepts(
        query_type="count",
        concept_ids=concept_ids,
        domain="Condition",
        backend="bigquery",
        execute=False
    )
    print(f"Estimated cost: ${estimate.estimated_cost_usd:.4f}")

    # Step 3: Execute if cost acceptable
    if estimate.estimated_cost_usd < 1.0:
        print("\nExecuting query...")
        result = await query_by_concepts(
            query_type="count",
            concept_ids=concept_ids,
            domain="Condition",
            backend="bigquery",
            execute=True
        )
        patient_count = result.results[0]['patient_count']
        print(f"✅ Found {patient_count:,} patients with {condition_name}")
    else:
        print("❌ Query too expensive, skipping execution")

# Run the workflow
await analyze_condition("type 2 diabetes")
```

### Example 5: Cross-Domain Query (Drugs + Conditions)

```python
# Find patients on Metformin who developed acute kidney injury
from omop_mcp.tools.athena import discover_concepts

# Discover drug concept
drug_result = await discover_concepts(query="metformin", domain="Drug")
drug_ids = [c.concept_id for c in drug_result.concepts]

# Discover condition concept
condition_result = await discover_concepts(query="acute kidney injury", domain="Condition")
condition_ids = [c.concept_id for c in condition_result.concepts]

# Query drug exposures
drug_query = await query_by_concepts(
    query_type="count",
    concept_ids=drug_ids,
    domain="Drug",
    backend="bigquery",
    execute=True
)

# Query condition occurrences
condition_query = await query_by_concepts(
    query_type="count",
    concept_ids=condition_ids,
    domain="Condition",
    backend="bigquery",
    execute=True
)

print(f"Patients on Metformin: {drug_query.results[0]['patient_count']}")
print(f"Patients with AKI: {condition_query.results[0]['patient_count']}")
```

### Example 6: Using MCP Resources (Caching)

```python
from omop_mcp.resources import get_concept_resource, search_concepts_resource

# Get single concept (cacheable by MCP client)
concept_resource = await get_concept_resource(concept_id=201826)
print(concept_resource)  # Returns concept with URI omop://concept/201826

# Search with pagination (cacheable)
page1 = await search_concepts_resource(
    query="diabetes",
    domain="Condition",
    cursor=None,  # First page
    page_size=50
)

print(f"Found {len(page1['concepts'])} concepts")
print(f"Next cursor: {page1['next_cursor']}")

# Get next page using cursor
page2 = await search_concepts_resource(
    query="diabetes",
    domain="Condition",
    cursor=page1['next_cursor'],
    page_size=50
)
```

### Example 7: Using MCP Prompts (AI Guidance)

```python
from omop_mcp.prompts import get_prompt

# Get SQL generation guidance
prompt = await get_prompt(
    prompt_id="cohort/sql",
    arguments={
        "exposure": "Metformin",
        "outcome": "Acute Kidney Injury",
        "time_window": "90 days",
        "dialect": "bigquery"
    }
)

print(prompt["messages"][0]["content"]["text"])
# Returns detailed prompt with SQL template, best practices, and examples
```

### Example 8: Local Development with DuckDB (New! 🎉)

```python
from omop_mcp.backends import DuckDBBackend, translate_query

# Step 1: Develop and test locally with DuckDB (FREE!)
duckdb_backend = DuckDBBackend()  # Zero setup required!

# Build cohort SQL
parts = await duckdb_backend.build_cohort_sql(
    exposure_ids=[1503297],  # Metformin
    outcome_ids=[46271022],  # Acute kidney injury
    pre_outcome_days=90
)

# Test locally (instant, free)
local_results = await duckdb_backend.execute_query(
    parts.to_sql(),
    limit=10
)
print(f"✅ Found {len(local_results)} matching records locally")

# Step 2: Translate to production database
bigquery_sql = translate_query(parts.to_sql(), "duckdb", "bigquery")
snowflake_sql = translate_query(parts.to_sql(), "duckdb", "snowflake")

# Step 3: Run on production (after local validation)
from omop_mcp.backends import BigQueryBackend
bigquery_backend = BigQueryBackend()
validation = await bigquery_backend.validate_sql(bigquery_sql)
print(f"💰 Estimated cost: ${validation.estimated_cost_usd:.2f}")

if validation.estimated_cost_usd < 1.0:
    prod_results = await bigquery_backend.execute_query(bigquery_sql)
    print(f"🚀 Production results: {len(prod_results)} records")
```

**Why this workflow?**
- 🆓 **Free local testing** - No cloud costs during development
- ⚡ **Instant iteration** - Test changes in milliseconds
- ✅ **Validate before deploy** - Catch errors locally
- 💰 **Cost-conscious** - Only pay for production queries
- 🔄 **Cross-platform** - Same SQL works on BigQuery, Snowflake, DuckDB

### Example 9: AI-Powered Concept Discovery (New! 🤖)

```python
from omop_mcp.agents import ConceptDiscoveryAgent

# Initialize AI agent
agent = ConceptDiscoveryAgent()

# Natural language concept search
result = await agent.run(
    "Find all concepts related to type 2 diabetes and its complications"
)

print(f"Found {len(result.concepts)} concepts:")
for concept in result.concepts[:5]:
    print(f"  - {concept.concept_name} ({concept.concept_id})")
    print(f"    Domain: {concept.domain_id}, Confidence: {concept.confidence}")

# Agent automatically:
# - Understands medical context
# - Searches multiple domains
# - Filters for relevance
# - Returns structured results
```

### Example 10: AI-Powered SQL Generation (New! 🤖)

```python
from omop_mcp.agents import SQLGenerationAgent

# Initialize SQL agent
agent = SQLGenerationAgent()

# Generate cohort SQL from natural language
result = await agent.run(
    description="Patients on metformin who developed acute kidney injury within 90 days",
    exposure="metformin",
    outcome="acute kidney injury"
)

print("Generated SQL:")
print(result.sql)
print(f"\nExposure concepts: {result.exposure_ids}")
print(f"Outcome concepts: {result.outcome_ids}")
print(f"Validation: {'✅ Valid' if result.validation.valid else '❌ Invalid'}")

# Agent automatically:
# - Discovers relevant concepts
# - Generates cohort SQL
# - Validates syntax
# - Returns complete, executable query
```

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

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=omop_mcp --cov-report=html

# Run specific test categories
uv run pytest tests/test_integration.py  # E2E workflows
uv run pytest tests/test_athena.py       # ATHENA API
uv run pytest tests/test_query_security.py  # Security guards

# Run with verbose output
uv run pytest -v
```

**Test Coverage:** 173 tests, 100% passing ✅
- Unit tests: 161 (models, backends, tools, resources, prompts, agents, export, sqlgen, dialect)
- Integration tests: 12 (E2E discover→query workflows, multi-backend, cross-dialect translation)
- Coverage areas:
  - ✅ Core OMOP tools (athena, query, sqlgen)
  - ✅ AI agents (concept discovery, SQL generation)
  - ✅ Export tools (JSON, CSV, all data types)
  - ✅ Multi-backend (BigQuery, Snowflake, DuckDB)
  - ✅ SQL translation (10+ dialects)
  - ✅ Security & validation

---

## 👨‍💻 Development

### Quick Start

```bash
# Clone and setup
git clone https://github.com/aandresalvarez/omop-mcp.git
cd omop-mcp

# Install with all dev dependencies
uv sync --extra dev

# Run quality checks
make check           # Format, lint, typecheck, test
make check-all       # All checks + pylint + pyright + security
```

### Quality Tools

This project uses comprehensive quality infrastructure for healthcare-grade code:

#### **Code Quality**
```bash
make format          # Black + ruff auto-formatting
make lint            # Ruff linting
make pylint          # Strict linting
make typecheck       # mypy type checking
make pyright         # pyright type checking
```

#### **Security Scanning** 🔒
```bash
make security        # bandit (Python security) + pip-audit (vulnerabilities)
make audit           # Comprehensive: security + safety dependency scan
```

#### **SQL Quality** (Critical for OMOP queries)
```bash
make sql-lint        # Lint SQL files with sqlfluff
make sql-fix         # Auto-fix SQL formatting
```

#### **Testing & Coverage**
```bash
make test            # Run pytest
make coverage        # Detailed coverage report (HTML + JSON + terminal)
```

### Available Make Targets

```bash
make help            # Show all available commands

# Setup
make dev             # Full development setup (venv + deps + tools)

# Quality checks
make check           # Standard checks (format, lint, typecheck, test)
make check-all       # ALL checks including security
make pre-commit      # Run pre-commit hooks

# Security
make security        # Security scans (bandit + pip-audit)
make audit           # Full security audit (+ safety)

# SQL
make sql-lint        # Lint SQL with sqlfluff
make sql-fix         # Auto-format SQL

# Testing
make test            # Run tests
make coverage        # Generate coverage reports

# Server
make http            # Run MCP server (HTTP mode)
make stdio           # Run MCP server (stdio mode)
```

### CI/CD

GitHub Actions automatically runs on every push:
- ✅ **Tests** (Python 3.11, 3.12)
- ✅ **Code quality** (format, lint)
- ✅ **Type checking** (mypy, pyright)
- ✅ **Security scanning** (bandit, pip-audit, safety)
- ✅ **SQL quality** (sqlfluff)
- ✅ **Coverage reporting**

See [`.github/workflows/quality.yml`](.github/workflows/quality.yml) for details.

### Pre-commit Hooks

Install git hooks for automatic quality checks:

```bash
make pre-commit-install
```

This runs formatting, linting, and type checking before each commit.

---

## 🔧 Troubleshooting

### Common Issues

**Problem:** "Backend not found: bigquery"
```bash
# Solution: Install backend dependencies
uv pip install google-cloud-bigquery
# Or use DuckDB for local development (no setup required!)
export BACKEND_TYPE=duckdb
```

**Problem:** "ATHENA API timeout"
```bash
# Solution: The public ATHENA API can be slow. Increase timeout:
export ATHENA_TIMEOUT_SEC=60
# Or use cached results from MCP resources
```

**Problem:** "Query exceeds cost limit"
```bash
# Solution: Increase cost cap or optimize query
export MAX_COST_USD=5.0
# Or run with execute=False to see SQL first
```

**Problem:** "concept_ids cannot be empty"
```bash
# Solution: Discovery returned no results. Try broader search:
result = await discover_concepts(
    query="diabetes",  # Broader term
    standard_only=False  # Include non-standard
)
```

**Problem:** "OAuth token invalid"
```bash
# Solution: Check token format and issuer
# Token must be Bearer JWT with correct audience
export OAUTH_AUDIENCE=omop-mcp-api
```

### Debugging Tips

**Enable debug logging:**
```python
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)
```

**Check backend connectivity:**
```python
from omop_mcp.backends.registry import list_backends, get_backend, get_supported_dialects

# List all registered backends
backends = list_backends()
print(f"Available backends: {backends}")

# Check supported SQL dialects
dialects = get_supported_dialects()
print(f"Supported dialects: {dialects}")

# Get specific backend
backend = get_backend("duckdb")  # or "bigquery" or "snowflake"
print(f"Connected to: {backend.name} (dialect: {backend.dialect})")
```

**Test SQL translation:**
```python
from omop_mcp.backends import translate_sql, validate_sql

# Translate SQL between dialects
bigquery_sql = "SELECT DATE_DIFF(end_date, start_date, DAY) FROM visits"
snowflake_sql = translate_sql(bigquery_sql, "bigquery", "snowflake")
print(f"Translated SQL: {snowflake_sql}")

# Validate SQL for specific dialect
is_valid, error = validate_sql(snowflake_sql, "snowflake")
print(f"Valid: {is_valid}, Error: {error}")
```

**Validate SQL without execution:**
```python
result = await query_by_concepts(
    query_type="count",
    concept_ids=[201826],
    domain="Condition",
    backend="bigquery",
    execute=False  # SQL only, no execution
)
print(result.sql)
print(f"Cost: ${result.estimated_cost_usd}")
```

---

## 🚀 Performance Tips

### General Tips
1. **Use MCP Resources for caching**: Resources are cached by MCP clients
2. **Batch concept lookups**: Search once, query multiple times
3. **Start with execute=False**: Validate SQL and cost before running
4. **Use standard_only=True**: Reduces search result size
5. **Set appropriate limits**: Default is 50 concepts, increase if needed

### Backend-Specific Tips

**DuckDB (Local Development):**
- ✅ **Instant startup**: In-memory mode (`:memory:`) is fastest
- ✅ **Free testing**: No cloud costs, iterate rapidly
- ✅ **File-based persistence**: Use `./omop.duckdb` for persistent storage
- ✅ **Import Parquet**: DuckDB can query Parquet files directly
- ⚡ **Performance**: ~1-10GB datasets run in seconds

**BigQuery (Cloud-Scale):**
- 💰 **Enable query result caching**: Results cached for 24 hours (free!)
- 📊 **Partition tables**: Use partitioned OMOP tables for cost reduction
- 🔍 **Use dry-run first**: Check cost before execution
- 💵 **Monitor costs**: Set `MAX_COST_USD` to prevent expensive queries
- ⚡ **Performance**: Scales to petabytes

**Snowflake (Enterprise):**
- ❄️ **Use warehouse sizes appropriately**: Start with X-Small for dev
- 🔄 **Enable result cache**: Snowflake caches identical queries
- 📈 **Scale compute**: Adjust warehouse size based on query complexity
- 💰 **Suspend warehouses**: Auto-suspend after 5 minutes of inactivity
- ⚡ **Performance**: Excellent for complex analytics

### Local → Production Workflow
```python
# 1. Develop locally with DuckDB (free, fast)
duckdb_backend = DuckDBBackend()
local_results = await duckdb_backend.execute_query(sql, limit=10)

# 2. Translate to production dialect
prod_sql = translate_sql(sql, "duckdb", "bigquery")

# 3. Validate cost before production run
bigquery_backend = BigQueryBackend()
validation = await bigquery_backend.validate_sql(prod_sql)
print(f"Cost: ${validation.estimated_cost_usd:.2f}")

# 4. Execute on production if cost acceptable
if validation.estimated_cost_usd < 1.0:
    prod_results = await bigquery_backend.execute_query(prod_sql)
```

**This workflow saves money and time by validating locally first!**

---

## 🔐 Security Best Practices

1. **Use OAuth in production**: Enable `OAUTH_ISSUER` and `OAUTH_AUDIENCE`
2. **Set cost limits**: Default is $1, adjust based on your budget
3. **Disable PHI mode**: Set `PHI_MODE=false` to block patient ID queries
4. **Use service accounts**: For BigQuery, use dedicated service account with read-only access
5. **Prefer ADC in cloud environments**: Use Application Default Credentials for Cloud Run, Compute Engine, etc.
6. **Enable audit logging**: All queries are logged with structlog
7. **Set query timeouts**: Default 30s, adjust as needed

---

## 🔗 Resources

### Official Documentation
- [OMOP Common Data Model](https://ohdsi.github.io/CommonDataModel/)
- [ATHENA Vocabulary Browser](https://athena.ohdsi.org)
- [Model Context Protocol](https://modelcontextprotocol.io)

### Project Documentation
- [Implementation Plan](./plan/plan.md)
- [Development Progress](./WEEK2_PROGRESS.md)
- [Integration Tests](./INTEGRATION_TESTS_COMPLETE.md)

### Feature Documentation
- [SQL Generation Module](./SQLGEN_EXTRACTION_COMPLETE.md)
- [PydanticAI Agents](./PYDANTIC_AI_AGENTS_COMPLETE.md)
- [Export Tools](./EXPORT_TOOLS_COMPLETE.md)
- [Additional Backends](./ADDITIONAL_BACKENDS_COMPLETE.md)
- [Optional Enhancements Summary](./OPTIONAL_ENHANCEMENTS_COMPLETE.md)

### Agent Documentation
- [Concept Discovery Agent](./agents/cd/README.md)
- [Query Builder Agent](./agents/qb/README.md)

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
