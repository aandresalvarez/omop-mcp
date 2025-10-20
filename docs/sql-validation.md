# SQL Validation & Security

The OMOP MCP server implements comprehensive SQL validation and security measures to protect healthcare data and ensure safe query execution.

## Overview

The SQL validation system provides multiple layers of security:

1. **Syntax Validation** - Ensures SQL queries are syntactically correct
2. **Security Validation** - Blocks dangerous operations (DELETE, UPDATE, DROP, etc.)
3. **Table Allowlist** - Restricts access to approved OMOP CDM tables
4. **Column Blocking** - Prevents access to PHI-sensitive columns
5. **Row Limiting** - Prevents excessive data retrieval
6. **Cost Validation** - BigQuery dry-run validation with cost limits

## Security Features

### Mutation Blocking

Only SELECT statements and CTEs (Common Table Expressions) are allowed. All mutating operations are blocked:

```python
# ❌ Blocked operations
DELETE FROM person WHERE person_id = 123
UPDATE person SET gender_concept_id = 8507
DROP TABLE person
INSERT INTO person VALUES (...)
CREATE TABLE custom_table (...)
ALTER TABLE person ADD COLUMN custom_field
```

```python
# ✅ Allowed operations
SELECT * FROM person WHERE person_id = 123
SELECT COUNT(*) FROM condition_occurrence
SELECT p.person_id, c.condition_concept_id
FROM person p
JOIN condition_occurrence c ON p.person_id = c.person_id

# ✅ CTE (Common Table Expression) statements also allowed
WITH patients AS (SELECT person_id FROM person)
SELECT COUNT(*) FROM patients

WITH RECURSIVE hierarchy AS (SELECT * FROM concept)
SELECT * FROM hierarchy
```

### OMOP Table Allowlist

When `STRICT_TABLE_VALIDATION=true`, only approved OMOP CDM tables are accessible:

**Allowed Tables:**
- `person` - Patient demographics
- `condition_occurrence` - Medical conditions
- `drug_exposure` - Medication records
- `procedure_occurrence` - Procedures performed
- `measurement` - Lab results and vital signs
- `observation` - Clinical observations
- `visit_occurrence` - Healthcare encounters
- `death` - Mortality data
- `location` - Geographic information
- `care_site` - Healthcare facilities
- `provider` - Healthcare providers
- `concept` - OMOP concept definitions
- `vocabulary` - Vocabulary metadata
- `concept_relationship` - Concept relationships
- `concept_ancestor` - Concept hierarchies

**Configuration:**
```bash
# Enable strict table validation
STRICT_TABLE_VALIDATION=true

# Customize allowed tables
OMOP_ALLOWED_TABLES=person,condition_occurrence,drug_exposure
```

### PHI Column Blocking

Sensitive source value columns are blocked by default:

**Blocked Columns:**
- `person_source_value` - Original patient identifiers
- `provider_source_value` - Original provider identifiers
- `location_source_value` - Original location identifiers
- `care_site_source_value` - Original facility identifiers

**Configuration:**
```bash
# Customize blocked columns
OMOP_BLOCKED_COLUMNS=person_source_value,provider_source_value,custom_phi_field

# Enable PHI protection mode
PHI_MODE=true
```

### Row Limiting

All queries are automatically limited to prevent excessive data retrieval:

```python
# Original query
SELECT * FROM person

# Automatically becomes
SELECT * FROM person
LIMIT 1000
```

**Configuration:**
```bash
# Set default row limit
DEFAULT_ROW_LIMIT=1000

# Maximum row limit
MAX_ROW_LIMIT=10000
```

### Cost Validation

For BigQuery backends, queries are validated for cost before execution:

```python
# Query cost validation
validation_result = await validate_sql_comprehensive(
    sql="SELECT * FROM large_table",
    backend="bigquery",
    check_cost=True
)

if validation_result.estimated_cost_usd > 1.0:
    raise CostLimitExceededError("Query cost exceeds limit")
```

**Configuration:**
```bash
# Set cost limit
MAX_COST_USD=1.0

# Disable cost checking
DISABLE_COST_VALIDATION=false
```

## Error Types

The validation system raises specific exceptions for different security violations:

### SecurityViolationError
Base exception for all security violations.

### SQLSyntaxError
Raised when SQL syntax is invalid:
```python
try:
    validate_sql_syntax("SELCT * FROM person")
except SQLSyntaxError as e:
    print(f"Syntax error: {e}")
```

### TableNotAllowedError
Raised when accessing non-allowlisted tables:
```python
try:
    validate_table_allowlist("SELECT * FROM custom_table")
except TableNotAllowedError as e:
    print(f"Table not allowed: {e}")
```

### ColumnBlockedError
Raised when accessing blocked PHI columns:
```python
try:
    validate_column_blocklist("SELECT person_source_value FROM person")
except ColumnBlockedError as e:
    print(f"Column blocked: {e}")
```

### CostLimitExceededError
Raised when query cost exceeds limit:
```python
try:
    await validate_sql_comprehensive(sql, backend="bigquery", check_cost=True)
except CostLimitExceededError as e:
    print(f"Cost limit exceeded: {e}")
```

## Usage Examples

### Basic Validation

```python
from omop_mcp.tools.sql_validator import validate_sql_comprehensive

# Validate a query
result = await validate_sql_comprehensive(
    sql="SELECT person_id, gender_concept_id FROM person LIMIT 100",
    backend="bigquery",
    limit=1000,
    check_cost=True
)

if result.valid:
    print(f"Query is valid. Estimated cost: ${result.estimated_cost_usd}")
else:
    print(f"Query failed: {result.error_message}")
```

### Schema-Aware Validation

```python
from omop_mcp.tools.schema import get_table_schema
from omop_mcp.tools.sql_validator import validate_sql_comprehensive

# Get table schema first
schema = await get_table_schema("person", "bigquery")
print(f"Person table has {schema['column_count']} columns")

# Validate query against schema
result = await validate_sql_comprehensive(
    sql="SELECT person_id, gender_concept_id FROM person",
    backend="bigquery"
)
```

### Custom Configuration

```python
from omop_mcp.config import OMOPConfig

# Create custom config
config = OMOPConfig(
    strict_table_validation=True,
    omop_allowed_tables=["person", "condition_occurrence"],
    omop_blocked_columns=["person_source_value"],
    max_query_cost_usd=0.5
)

# Use in validation
result = await validate_sql_comprehensive(
    sql="SELECT * FROM person",
    backend="bigquery"
)
```

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STRICT_TABLE_VALIDATION` | `false` | Enable strict OMOP table allowlist |
| `OMOP_ALLOWED_TABLES` | See above | Comma-separated list of allowed tables |
| `OMOP_BLOCKED_COLUMNS` | See above | Comma-separated list of blocked columns |
| `PHI_MODE` | `false` | Enable enhanced PHI protection |
| `MAX_COST_USD` | `1.0` | Maximum query cost in USD |
| `DEFAULT_ROW_LIMIT` | `1000` | Default row limit for queries |
| `MAX_ROW_LIMIT` | `10000` | Maximum allowed row limit |

### Python Configuration

```python
from omop_mcp.config import OMOPConfig

config = OMOPConfig(
    # SQL validation settings
    strict_table_validation=True,
    omop_allowed_tables=[
        "person", "condition_occurrence", "drug_exposure",
        "procedure_occurrence", "measurement", "observation"
    ],
    omop_blocked_columns=[
        "person_source_value", "provider_source_value",
        "location_source_value", "care_site_source_value"
    ],
    phi_mode=True,
    max_query_cost_usd=0.5,

    # Other settings
    allow_patient_list=False,
    query_timeout_sec=30
)
```

## Best Practices

### 1. Enable Strict Validation in Production

```bash
# Production environment
STRICT_TABLE_VALIDATION=true
PHI_MODE=true
MAX_COST_USD=0.1
ALLOW_PATIENT_LIST=false
```

### 2. Use Appropriate Row Limits

```python
# For exploratory queries
limit = 100

# For analysis queries
limit = 1000

# For reporting queries
limit = 10000
```

### 3. Monitor Query Costs

```python
# Always check cost for large queries
result = await validate_sql_comprehensive(
    sql=large_query,
    backend="bigquery",
    check_cost=True
)

if result.estimated_cost_usd > 0.1:
    logger.warning(f"Expensive query: ${result.estimated_cost_usd}")
```

### 4. Handle Validation Errors Gracefully

```python
try:
    result = await validate_sql_comprehensive(sql, backend="bigquery")
except SQLValidationError as e:
    logger.error(f"Query validation failed: {e}")
    return {"error": str(e), "valid": False}
```

## Integration with MCP Tools

The SQL validation is automatically applied to all MCP tools that execute SQL:

### get_information_schema
```python
# Automatically validates schema queries
schema = await get_information_schema(
    table_name="person",
    backend="bigquery"
)
```

### select_query
```python
# Automatically validates and executes queries
result = await select_query(
    sql="SELECT COUNT(*) FROM person",
    validate=True,
    execute=True,
    backend="bigquery",
    limit=1000
)
```

## Troubleshooting

### Common Issues

**1. "Table not in allowlist" error**
```bash
# Solution: Add table to allowlist or disable strict validation
OMOP_ALLOWED_TABLES=person,condition_occurrence,custom_table
# OR
STRICT_TABLE_VALIDATION=false
```

**2. "Column contains PHI and is blocked" error**
```bash
# Solution: Remove column from blocklist or use different columns
OMOP_BLOCKED_COLUMNS=provider_source_value
# OR query different columns
SELECT person_id, gender_concept_id FROM person
```

**3. "Query cost exceeds limit" error**
```bash
# Solution: Increase cost limit or optimize query
MAX_COST_USD=5.0
# OR add LIMIT clause
SELECT * FROM large_table LIMIT 1000
```

### Debug Mode

Enable debug logging to see validation details:

```python
import structlog
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)
```

## Security Considerations

### Data Privacy
- Never disable PHI column blocking in production
- Use appropriate row limits to prevent data exfiltration
- Monitor query patterns for unusual access

### Cost Management
- Set appropriate cost limits for your budget
- Use dry-run validation before expensive queries
- Monitor BigQuery usage and costs

### Access Control
- Use strict table validation in production
- Regularly review and update allowlists
- Implement additional authentication as needed

## Performance Impact

The validation system adds minimal overhead:

- **Syntax validation**: ~1ms per query
- **Security validation**: ~1ms per query
- **Table/column validation**: ~2ms per query
- **Cost validation**: ~100-500ms (BigQuery dry-run)

Total validation overhead is typically <1 second per query.

## Future Enhancements

Planned improvements to the validation system:

1. **Query Pattern Analysis** - Detect unusual query patterns
2. **Dynamic Cost Limits** - Adjust limits based on user/role
3. **Audit Logging** - Enhanced query audit trails
4. **Machine Learning** - Anomaly detection for queries
5. **Real-time Monitoring** - Live query monitoring dashboard
