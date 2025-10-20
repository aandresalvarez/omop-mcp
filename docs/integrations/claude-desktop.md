# Claude Desktop Integration Guide

This guide will help you set up the OMOP MCP server with Claude Desktop for seamless healthcare data analysis.

## Prerequisites

- **Claude Desktop** installed and running
- **Python 3.11+** installed
- **OMOP CDM database** access (BigQuery, Snowflake, or DuckDB)
- **OpenAI API key** (for AI agents)

## Quick Setup (5 minutes)

### 1. Install OMOP MCP Server

```bash
# Clone the repository
git clone https://github.com/aandresalvarez/omop-mcp.git
cd omop-mcp

# Install with UV (recommended)
uv pip install -e ".[dev]"

# Or install with pip
pip install -e ".[dev]"
```

### 2. Configure Environment

Create a `.env` file in the omop-mcp directory:

```bash
# Required: OpenAI API key for AI agents
OPENAI_API_KEY=sk-your-openai-api-key-here

# Required: Database backend
BACKEND_TYPE=bigquery  # or "snowflake" or "duckdb"

# For BigQuery
BIGQUERY_PROJECT_ID=your-gcp-project
BIGQUERY_DATASET_ID=omop_cdm
BIGQUERY_CREDENTIALS_PATH=/path/to/service-account.json

# For Snowflake
SNOWFLAKE_ACCOUNT=your-account.snowflakecomputing.com
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=omop_db
SNOWFLAKE_SCHEMA=cdm
SNOWFLAKE_WAREHOUSE=compute_wh

# For DuckDB (local development - no credentials needed!)
DUCKDB_DATABASE_PATH=:memory:  # or "./omop.duckdb" for persistent
DUCKDB_SCHEMA=main

# Optional: Security settings
MAX_COST_USD=1.0          # Cost limit for BigQuery queries
ALLOW_PATIENT_LIST=false  # Block patient ID queries in production
QUERY_TIMEOUT_SEC=30      # Query timeout
```

### 3. Configure Claude Desktop

Add the OMOP MCP server to your Claude Desktop configuration:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "omop-mcp": {
      "command": "uv",
      "args": ["run", "python", "-m", "omop_mcp.server", "--stdio"],
      "cwd": "/path/to/omop-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-your-openai-api-key-here",
        "BIGQUERY_PROJECT_ID": "your-gcp-project",
        "BIGQUERY_DATASET_ID": "omop_cdm",
        "BIGQUERY_CREDENTIALS_PATH": "/path/to/service-account.json"
      }
    }
  }
}
```

### 4. Restart Claude Desktop

Close and restart Claude Desktop to load the new MCP server configuration.

## Verification

Open Claude Desktop and test the integration:

```
You: "Can you help me find OMOP concepts for diabetes?"

Claude: I'll help you discover diabetes-related OMOP concepts using the OMOP MCP server.

[Claude uses the discover_concepts tool]

I found several diabetes-related concepts:
- Type 2 diabetes mellitus (concept_id: 201826)
- Type 1 diabetes mellitus (concept_id: 201254)
- Diabetes mellitus (concept_id: 201820)

Would you like me to generate a query to count patients with these conditions?
```

## Configuration Examples

### BigQuery Setup

```json
{
  "mcpServers": {
    "omop-mcp": {
      "command": "uv",
      "args": ["run", "python", "-m", "omop_mcp.server", "--stdio"],
      "cwd": "/path/to/omop-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-your-key",
        "BACKEND_TYPE": "bigquery",
        "BIGQUERY_PROJECT_ID": "your-project",
        "BIGQUERY_DATASET_ID": "omop_cdm",
        "BIGQUERY_CREDENTIALS_PATH": "/path/to/credentials.json",
        "MAX_COST_USD": "5.0"
      }
    }
  }
}
```

### Snowflake Setup

```json
{
  "mcpServers": {
    "omop-mcp": {
      "command": "uv",
      "args": ["run", "python", "-m", "omop_mcp.server", "--stdio"],
      "cwd": "/path/to/omop-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-your-key",
        "BACKEND_TYPE": "snowflake",
        "SNOWFLAKE_ACCOUNT": "your-account.snowflakecomputing.com",
        "SNOWFLAKE_USER": "your_username",
        "SNOWFLAKE_PASSWORD": "your_password",
        "SNOWFLAKE_DATABASE": "omop_db",
        "SNOWFLAKE_SCHEMA": "cdm",
        "SNOWFLAKE_WAREHOUSE": "compute_wh"
      }
    }
  }
}
```

### DuckDB Local Development

```json
{
  "mcpServers": {
    "omop-mcp": {
      "command": "uv",
      "args": ["run", "python", "-m", "omop_mcp.server", "--stdio"],
      "cwd": "/path/to/omop-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-your-key",
        "BACKEND_TYPE": "duckdb",
        "DUCKDB_DATABASE_PATH": "./synthetic_data/synthea.duckdb"
      }
    }
  }
}
```

## Usage Examples

### 1. Concept Discovery

```
You: "Find all concepts related to hypertension"

Claude: I'll search for hypertension concepts in the OMOP vocabulary.

[Uses discover_concepts tool]

Found 15 hypertension-related concepts:
- Essential hypertension (concept_id: 320128)
- Hypertension (concept_id: 316866)
- Malignant hypertension (concept_id: 317009)
- Secondary hypertension (concept_id: 317002)

These are all standard SNOMED concepts in the Condition domain.
```

### 2. Patient Count Queries

```
You: "How many patients have diabetes in the database?"

Claude: I'll count patients with diabetes using the discovered concepts.

[Uses discover_concepts then query_omop tools]

Found 1,234 patients with diabetes conditions:
- Type 2 diabetes: 856 patients
- Type 1 diabetes: 234 patients
- Other diabetes: 144 patients

The query scanned 2.3GB of data with an estimated cost of $0.012.
```

### 3. Schema Exploration

```
You: "What columns are available in the condition_occurrence table?"

Claude: I'll get the schema information for the condition_occurrence table.

[Uses get_information_schema tool]

The condition_occurrence table has 15 columns:
- condition_occurrence_id: Unique identifier for condition occurrence
- person_id: Person identifier
- condition_concept_id: Condition concept identifier
- condition_start_date: Start date of condition
- condition_end_date: End date of condition
- condition_type_concept_id: Type of condition occurrence
- condition_status_concept_id: Status of condition
- stop_reason: Reason for stopping condition
- provider_id: Provider identifier
- visit_occurrence_id: Visit occurrence identifier
- visit_detail_id: Visit detail identifier
- condition_source_value: Source value for condition
- condition_source_concept_id: Source concept identifier
- condition_status_source_value: Source value for condition status
- condition_end_date: End date of condition
```

### 4. Direct SQL Execution

```
You: "Show me the top 10 most common conditions"

Claude: I'll execute a SQL query to find the most common conditions.

[Uses select_query tool]

Here are the top 10 most common conditions:

1. Essential hypertension: 15,432 patients
2. Type 2 diabetes mellitus: 8,765 patients
3. Hyperlipidemia: 7,234 patients
4. Obesity: 6,543 patients
5. Chronic kidney disease: 4,321 patients
6. Atrial fibrillation: 3,876 patients
7. Myocardial infarction: 2,987 patients
8. Stroke: 2,654 patients
9. COPD: 2,345 patients
10. Depression: 2,123 patients

Query executed in 1.2 seconds, scanned 5.6GB of data.
```

### 5. Cohort SQL Generation

```
You: "Generate SQL for patients on metformin who developed kidney problems within 90 days"

Claude: I'll generate cohort SQL for this exposure-outcome relationship.

[Uses discover_concepts for both conditions, then generate_cohort_sql]

Generated cohort SQL:

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

This query identifies patients who:
- Were prescribed metformin (exposure)
- Developed acute kidney injury (outcome)
- Within 90 days of exposure
- Uses first exposure per patient logic
```

## Troubleshooting

### Common Issues

**"MCP server not found"**
- Verify the `cwd` path in your configuration is correct
- Ensure the omop-mcp directory exists and contains the server files
- Check that UV is installed: `uv --version`

**"OpenAI API key not found"**
- Verify `OPENAI_API_KEY` is set in your environment or config
- Check that the API key is valid and has sufficient credits

**"Database connection failed"**
- Verify database credentials are correct
- For BigQuery: ensure service account has access to the dataset
- For Snowflake: check account URL format and warehouse status
- For DuckDB: ensure database file exists and is readable

**"Query exceeds cost limit"**
- Increase `MAX_COST_USD` in your configuration
- Use more specific WHERE clauses to reduce data scanned
- Start with `execute=false` to check cost before running

**"Table not found"**
- Verify `BIGQUERY_DATASET_ID` or `SNOWFLAKE_SCHEMA` is correct
- Check that OMOP tables exist in your dataset
- Use `get_information_schema` to list available tables

### Debug Mode

Enable debug logging by setting:

```bash
LOG_LEVEL=DEBUG
```

This will show detailed logs in the MCP server output, helping diagnose issues.

### Log Locations

- **macOS**: `~/Library/Logs/Claude/`
- **Windows**: `%APPDATA%\Claude\logs\`
- **MCP Server**: Check terminal output where you started the server

## Security Considerations

### Production Settings

For production use, enable strict security:

```bash
# Enable strict table validation
STRICT_TABLE_VALIDATION=true

# Block PHI access
ALLOW_PATIENT_LIST=false
PHI_MODE=false

# Set conservative cost limits
MAX_COST_USD=0.50

# Enable OAuth authentication
OAUTH_ISSUER=https://your-auth-provider.com
OAUTH_AUDIENCE=omop-mcp-api
```

### Development Settings

For development, you can be more permissive:

```bash
# Allow patient lists for testing
ALLOW_PATIENT_LIST=true

# Higher cost limits for exploration
MAX_COST_USD=10.0

# Include non-OMOP tables
INCLUDE_NON_OMOP=true
```

## Advanced Configuration

### Custom Table Allowlist

```bash
# Define custom allowed tables
OMOP_ALLOWED_TABLES=person,condition_occurrence,drug_exposure,custom_table
```

### Custom Column Blocklist

```bash
# Block additional PHI columns
OMOP_BLOCKED_COLUMNS=person_source_value,provider_source_value,custom_phi_column
```

### Multiple Backends

You can configure multiple backends and switch between them:

```bash
# Primary backend
BACKEND_TYPE=bigquery

# Fallback backend
FALLBACK_BACKEND_TYPE=duckdb
FALLBACK_DUCKDB_DATABASE_PATH=./backup_data.duckdb
```

## Performance Tips

1. **Use DuckDB for development**: Faster iteration, no cloud costs
2. **Start with concept discovery**: Use `discover_concepts` before writing queries
3. **Validate before executing**: Use `execute=false` to check cost first
4. **Use LIMIT clauses**: Always limit result sets for exploration
5. **Cache results**: MCP resources are cached automatically

## Next Steps

- Explore the [API Reference](../api/tools.md) for detailed tool documentation
- Read the [SQL Validation Guide](../sql-validation.md) for security features
- Check out [Execution & Caching](../execution-caching.md) for performance optimization
- Try the [Generic MCP Client Guide](generic-mcp-client.md) for other clients
