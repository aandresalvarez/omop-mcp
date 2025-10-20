# MCP Tools API Reference

This document provides a comprehensive reference for all MCP tools available in the OMOP MCP server.

## Overview

The OMOP MCP server provides 6 core tools for healthcare data analysis:

- **Concept Discovery**: Search OMOP vocabulary for medical concepts
- **Concept Relationships**: Explore concept mappings and hierarchies
- **Analytical Queries**: Execute structured OMOP queries
- **Cohort SQL Generation**: Generate SQL for exposure-outcome studies
- **Schema Introspection**: Get database schema information
- **Direct SQL Execution**: Execute SQL with security validation

## Tool Reference

### discover_concepts

Search ATHENA vocabulary for OMOP concepts matching clinical terms.

**Parameters:**
- `clinical_text` (string, required): Clinical term to search (e.g., "type 2 diabetes", "influenza")
- `domain` (string, optional): Filter by OMOP domain (Condition, Drug, Procedure, Measurement, Observation, Device, Visit, Death)
- `vocabulary` (string, optional): Filter by vocabulary (SNOMED, RxNorm, LOINC, ICD10CM, ICD10PCS, CPT4, HCPCS, NDC, UMLS, ATC)
- `standard_only` (boolean, optional): Return only standard concepts (default: true)
- `limit` (integer, optional): Maximum number of concepts to return (default: 50, max: 100)

**Returns:**
```json
{
  "query": "diabetes",
  "concepts": [
    {
      "concept_id": 201826,
      "concept_name": "Type 2 diabetes mellitus",
      "domain_id": "Condition",
      "vocabulary_id": "SNOMED",
      "concept_class_id": "Clinical Finding",
      "standard_concept": "S",
      "concept_code": "44054006",
      "invalid_reason": null,
      "score": 0.95
    }
  ],
  "concept_ids": [201826, 201254, 201820],
  "standard_concepts": [
    {
      "concept_id": 201826,
      "concept_name": "Type 2 diabetes mellitus",
      "domain_id": "Condition",
      "vocabulary_id": "SNOMED",
      "concept_class_id": "Clinical Finding",
      "standard_concept": "S",
      "concept_code": "44054006",
      "invalid_reason": null,
      "score": 0.95
    }
  ],
  "search_metadata": {
    "domain": "Condition",
    "vocabulary": "SNOMED",
    "standard_only": true,
    "limit": 50
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Example Usage:**
```python
result = await discover_concepts(
    ctx,
    clinical_text="hypertension",
    domain="Condition",
    vocabulary="SNOMED",
    standard_only=True,
    limit=20
)
```

**Error Cases:**
- `ValidationError`: Invalid parameters (limit > 100, empty clinical_text)
- `AthenaAPIError`: ATHENA API unavailable or rate limited
- `TimeoutError`: Request timeout exceeded

---

### get_concept_relationships

Get relationships for an OMOP concept (maps to, subsumes, is a, etc.).

**Parameters:**
- `concept_id` (integer, required): OMOP concept ID
- `relationship_id` (string, optional): Specific relationship type (e.g., "Maps to", "Subsumes", "Is a")

**Returns:**
```json
{
  "concept_id": 201826,
  "concept_name": "Type 2 diabetes mellitus",
  "relationships": [
    {
      "relationship_id": "Maps to",
      "concept_id_1": 201826,
      "concept_id_2": 201820,
      "concept_name_2": "Diabetes mellitus",
      "relationship_type": "Maps to",
      "valid_start_date": "1970-01-01",
      "valid_end_date": "2099-12-31",
      "invalid_reason": null
    }
  ],
  "total_relationships": 15,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Example Usage:**
```python
result = await get_concept_relationships(
    ctx,
    concept_id=201826,
    relationship_id="Maps to"
)
```

**Error Cases:**
- `ConceptNotFoundError`: Concept ID does not exist
- `AthenaAPIError`: ATHENA API unavailable

---

### query_omop

Execute analytical queries on OMOP data (counts, demographics, prevalence).

**Parameters:**
- `query_type` (string, required): Type of query ("count", "demographics", "prevalence", "cohort")
- `concept_ids` (array of integers, required): List of OMOP concept IDs
- `domain` (string, optional): OMOP domain (default: "Condition")
- `backend` (string, optional): Database backend ("bigquery", "snowflake", "duckdb", default: "bigquery")
- `execute` (boolean, optional): Execute query or return SQL only (default: true)
- `limit` (integer, optional): Maximum rows to return (default: 1000)

**Returns:**
```json
{
  "query_type": "count",
  "concept_ids": [201826, 201254],
  "domain": "Condition",
  "backend": "bigquery",
  "sql": "SELECT COUNT(DISTINCT person_id) as patient_count FROM condition_occurrence WHERE condition_concept_id IN (201826, 201254)",
  "results": [
    {
      "patient_count": 1234
    }
  ],
  "execution_time_ms": 1250,
  "estimated_cost_usd": 0.012,
  "estimated_bytes": 2300000,
  "validation": {
    "valid": true,
    "error_message": null,
    "estimated_cost_usd": 0.012,
    "estimated_bytes": 2300000
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Query Types:**

**Count Query:**
```python
result = await query_omop(
    ctx,
    query_type="count",
    concept_ids=[201826, 201254],
    domain="Condition",
    execute=True
)
```

**Demographics Query:**
```python
result = await query_omop(
    ctx,
    query_type="demographics",
    concept_ids=[201826],
    domain="Condition",
    execute=True
)
# Returns age, gender, race, ethnicity breakdowns
```

**Prevalence Query:**
```python
result = await query_omop(
    ctx,
    query_type="prevalence",
    concept_ids=[201826],
    domain="Condition",
    execute=True
)
# Returns prevalence by age group, gender, etc.
```

**Error Cases:**
- `ValidationError`: Invalid query_type or concept_ids
- `BackendError`: Database connection or execution error
- `CostLimitExceededError`: Query cost exceeds limit
- `SecurityViolationError`: Query violates security policies

---

### generate_cohort_sql

Generate SQL for cohort definition with exposure → outcome logic.

**Parameters:**
- `exposure_concept_ids` (array of integers, required): Concept IDs for exposure events
- `outcome_concept_ids` (array of integers, required): Concept IDs for outcome events
- `pre_outcome_days` (integer, optional): Maximum days between exposure and outcome (default: 90)
- `backend` (string, optional): Database backend ("bigquery", "snowflake", "duckdb", default: "bigquery")
- `validate` (boolean, optional): Run dry-run validation (default: true)

**Returns:**
```json
{
  "sql": "WITH exposure AS (\n  SELECT DISTINCT person_id, drug_exposure_start_date AS exposure_date\n  FROM drug_exposure\n  WHERE drug_concept_id IN (1503297)\n),\noutcome AS (\n  SELECT DISTINCT person_id, condition_start_date AS outcome_date\n  FROM condition_occurrence\n  WHERE condition_concept_id IN (46271022)\n),\ncohort AS (\n  SELECT e.person_id, e.exposure_date, o.outcome_date,\n    DATE_DIFF(o.outcome_date, e.exposure_date, DAY) AS days_to_outcome\n  FROM exposure e\n  INNER JOIN outcome o ON e.person_id = o.person_id\n  WHERE e.exposure_date <= o.outcome_date\n    AND DATE_DIFF(o.outcome_date, e.exposure_date, DAY) <= 90\n)\nSELECT * FROM cohort\nQUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY exposure_date) = 1;",
  "validation": {
    "valid": true,
    "error_message": null,
    "estimated_cost_usd": 0.045,
    "estimated_bytes": 4500000
  },
  "concept_counts": {
    "exposure": 1,
    "outcome": 1
  },
  "backend": "bigquery",
  "dialect": "bigquery",
  "is_valid": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Example Usage:**
```python
result = await generate_cohort_sql(
    ctx,
    exposure_concept_ids=[1503297],  # Metformin
    outcome_concept_ids=[46271022],  # Acute kidney injury
    pre_outcome_days=90,
    backend="bigquery",
    validate=True
)
```

**Error Cases:**
- `ValidationError`: Invalid concept IDs or parameters
- `SQLGenerationError`: Failed to generate valid SQL
- `CostLimitExceededError`: Generated SQL exceeds cost limit

---

### get_information_schema

Get OMOP database schema information including table structures and column definitions.

**Parameters:**
- `table_name` (string, optional): Specific OMOP table (e.g., "condition_occurrence", "person")
- `backend` (string, optional): Database backend ("bigquery", "snowflake", "duckdb", default: "bigquery")

**Returns:**

**Single Table Schema:**
```json
{
  "table_name": "condition_occurrence",
  "description": "Medical conditions and diagnoses",
  "is_omop_standard": true,
  "columns": [
    {
      "name": "condition_occurrence_id",
      "type": "INTEGER",
      "nullable": false,
      "default": null,
      "position": 1,
      "description": "Unique identifier for condition occurrence",
      "is_omop_standard": true
    },
    {
      "name": "person_id",
      "type": "INTEGER",
      "nullable": false,
      "default": null,
      "position": 2,
      "description": "Person identifier",
      "is_omop_standard": true
    }
  ],
  "column_count": 15,
  "backend": "bigquery",
  "schema_source": "INFORMATION_SCHEMA"
}
```

**All Tables Schema:**
```json
{
  "tables": {
    "person": {
      "table_name": "person",
      "description": "Patient demographics and basic information",
      "is_omop_standard": true,
      "columns": [...],
      "column_count": 15,
      "backend": "bigquery"
    },
    "condition_occurrence": {
      "table_name": "condition_occurrence",
      "description": "Medical conditions and diagnoses",
      "is_omop_standard": true,
      "columns": [...],
      "column_count": 15,
      "backend": "bigquery"
    }
  },
  "total_tables": 15,
  "omop_tables": 15,
  "backend": "bigquery",
  "include_non_omop": false
}
```

**Example Usage:**
```python
# Get specific table schema
schema = await get_information_schema(
    ctx,
    table_name="condition_occurrence",
    backend="bigquery"
)

# Get all tables schema
all_schemas = await get_information_schema(
    ctx,
    table_name=None,
    backend="bigquery"
)
```

**Error Cases:**
- `TableNotFoundError`: Table does not exist in database
- `BackendError`: Database connection or query error
- `PermissionError`: Insufficient permissions to access schema

---

### select_query

Execute direct SQL queries with comprehensive security validation.

**Parameters:**
- `sql` (string, required): SQL SELECT statement to execute
- `validate` (boolean, optional): Run validation before execution (default: true)
- `execute` (boolean, optional): Execute query or return SQL only (default: true)
- `backend` (string, optional): Database backend ("bigquery", "snowflake", "duckdb", default: "bigquery")
- `limit` (integer, optional): Maximum rows to return (default: 1000)

**Returns:**
```json
{
  "sql": "SELECT condition_concept_id, COUNT(DISTINCT person_id) as patient_count\nFROM condition_occurrence\nWHERE condition_concept_id IN (201826, 201254)\nGROUP BY condition_concept_id\nLIMIT 1000",
  "results": [
    {
      "condition_concept_id": 201826,
      "patient_count": 856
    },
    {
      "condition_concept_id": 201254,
      "patient_count": 234
    }
  ],
  "row_count": 2,
  "validation": {
    "valid": true,
    "error_message": null,
    "estimated_cost_usd": 0.023,
    "estimated_bytes": 2300000
  },
  "estimated_cost_usd": 0.023,
  "estimated_bytes": 2300000,
  "backend": "bigquery",
  "execution_time_ms": 1850
}
```

**Example Usage:**
```python
result = await select_query(
    ctx,
    sql="SELECT COUNT(DISTINCT person_id) FROM condition_occurrence WHERE condition_concept_id = 201826",
    validate=True,
    execute=True,
    backend="bigquery",
    limit=1000
)
```

**Security Features:**
- **Statement Validation**: Only SELECT statements allowed
- **Table Allowlist**: Only OMOP CDM tables accessible (if strict validation enabled)
- **Column Blocking**: PHI columns blocked by default
- **Cost Limits**: Query cost validation and limits
- **Row Limiting**: Automatic LIMIT injection

**Error Cases:**
- `SQLSyntaxError`: Invalid SQL syntax
- `SecurityViolationError`: Dangerous operations detected (DELETE, UPDATE, etc.)
- `TableNotAllowedError`: Non-allowlisted table accessed
- `ColumnBlockedError`: Blocked PHI column accessed
- `CostLimitExceededError`: Query cost exceeds limit
- `BackendError`: Database execution error

## Data Models

### OMOPConcept

```json
{
  "concept_id": 201826,
  "concept_name": "Type 2 diabetes mellitus",
  "domain_id": "Condition",
  "vocabulary_id": "SNOMED",
  "concept_class_id": "Clinical Finding",
  "standard_concept": "S",
  "concept_code": "44054006",
  "invalid_reason": null,
  "score": 0.95
}
```

### SQLValidationResult

```json
{
  "valid": true,
  "error_message": null,
  "estimated_cost_usd": 0.023,
  "estimated_bytes": 2300000
}
```

### ConceptDiscoveryResult

```json
{
  "query": "diabetes",
  "concepts": [OMOPConcept],
  "concept_ids": [201826, 201254],
  "standard_concepts": [OMOPConcept],
  "search_metadata": {
    "domain": "Condition",
    "vocabulary": "SNOMED",
    "standard_only": true,
    "limit": 50
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### QueryOMOPResult

```json
{
  "query_type": "count",
  "concept_ids": [201826],
  "domain": "Condition",
  "backend": "bigquery",
  "sql": "SELECT COUNT(DISTINCT person_id) as patient_count FROM condition_occurrence WHERE condition_concept_id IN (201826)",
  "results": [{"patient_count": 1234}],
  "execution_time_ms": 1250,
  "estimated_cost_usd": 0.012,
  "estimated_bytes": 2300000,
  "validation": SQLValidationResult,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### CohortSQLResult

```json
{
  "sql": "WITH exposure AS (...), outcome AS (...), cohort AS (...) SELECT * FROM cohort",
  "validation": SQLValidationResult,
  "concept_counts": {
    "exposure": 1,
    "outcome": 1
  },
  "backend": "bigquery",
  "dialect": "bigquery",
  "is_valid": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Error Handling

### Error Types

**ValidationError**
- **Code**: `VALIDATION_ERROR`
- **Message**: "Invalid parameters provided"
- **Details**: Parameter validation failed

**SecurityViolationError**
- **Code**: `SECURITY_VIOLATION`
- **Message**: "Mutating queries not allowed"
- **Details**: Dangerous SQL operations detected

**CostLimitExceededError**
- **Code**: `COST_LIMIT_EXCEEDED`
- **Message**: "Query cost $2.50 exceeds limit $1.00"
- **Details**: Query cost exceeds configured limit

**BackendError**
- **Code**: `BACKEND_ERROR`
- **Message**: "Database connection failed"
- **Details**: Backend-specific error information

**TimeoutError**
- **Code**: `TIMEOUT_ERROR`
- **Message**: "Query timed out after 30 seconds"
- **Details**: Query execution timeout

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid parameters provided",
    "details": {
      "field": "limit",
      "value": 150,
      "constraint": "max 100"
    }
  }
}
```

## Rate Limits

- **ATHENA API**: 100 requests per minute per IP
- **Database Queries**: No built-in rate limiting (configure at backend level)
- **Cost Limits**: Configurable per query and per time period

## Authentication

### OAuth 2.1 (Production)

```bash
# Environment variables
OAUTH_ISSUER=https://your-auth-provider.com
OAUTH_AUDIENCE=omop-mcp-api
```

### Client Authentication

Include Bearer token in requests:

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
```

## Performance Considerations

### Query Optimization

- **Use LIMIT clauses**: Always limit result sets for exploration
- **Filter early**: Use WHERE clauses to reduce data scanned
- **Index-aware queries**: Structure queries to use available indexes
- **Batch operations**: Group related queries together

### Caching

- **ATHENA API**: LRU cache with 1000 entries
- **Query Results**: TTL-based cache (1 hour default)
- **Schema Info**: Long-term cache (24 hours)

### Cost Management

- **BigQuery**: Dry-run validation with cost estimation
- **Snowflake**: Warehouse size optimization
- **DuckDB**: In-memory execution limits

## Examples

### Complete Workflow: Diabetes Analysis

```python
# 1. Discover diabetes concepts
diabetes_concepts = await discover_concepts(
    ctx,
    clinical_text="type 2 diabetes",
    domain="Condition",
    standard_only=True,
    limit=10
)

# 2. Get concept relationships
relationships = await get_concept_relationships(
    ctx,
    concept_id=diabetes_concepts["concept_ids"][0]
)

# 3. Query patient counts
patient_counts = await query_omop(
    ctx,
    query_type="count",
    concept_ids=diabetes_concepts["concept_ids"],
    domain="Condition",
    execute=True
)

# 4. Get demographics breakdown
demographics = await query_omop(
    ctx,
    query_type="demographics",
    concept_ids=diabetes_concepts["concept_ids"],
    domain="Condition",
    execute=True
)

# 5. Generate cohort SQL for diabetes + complications
cohort_sql = await generate_cohort_sql(
    ctx,
    exposure_concept_ids=diabetes_concepts["concept_ids"],
    outcome_concept_ids=[46271022],  # Acute kidney injury
    pre_outcome_days=90,
    validate=True
)
```

### Schema Exploration

```python
# 1. Get all available tables
all_tables = await get_information_schema(ctx, backend="bigquery")

# 2. Get specific table details
person_schema = await get_information_schema(
    ctx,
    table_name="person",
    backend="bigquery"
)

# 3. Execute custom query
custom_result = await select_query(
    ctx,
    sql="SELECT gender_concept_id, COUNT(*) as count FROM person GROUP BY gender_concept_id",
    validate=True,
    execute=True,
    backend="bigquery"
)
```

This API reference provides comprehensive documentation for all MCP tools, enabling developers to build powerful healthcare data analysis applications.
