# LibreChat + Ollama Integration Guide

This guide shows how to integrate the OMOP MCP server with LibreChat and Ollama for local healthcare data analysis.

## Prerequisites

- **LibreChat** installed and running
- **Ollama** installed with a suitable model (e.g., `llama3.1`, `codellama`)
- **Python 3.11+** installed
- **OMOP CDM database** (DuckDB recommended for local development)

## Architecture Overview

```
LibreChat ↔ Ollama ↔ MCP Client ↔ OMOP MCP Server (HTTP) ↔ OMOP Database
```

The OMOP MCP server runs in HTTP mode and communicates with LibreChat through Server-Sent Events (SSE).

## Quick Setup (10 minutes)

### 1. Install OMOP MCP Server

```bash
# Clone and install
git clone https://github.com/aandresalvarez/omop-mcp.git
cd omop-mcp
uv pip install -e ".[duckdb]"  # Minimal install for local development
```

### 2. Configure for Local Development

Create `.env` file for local DuckDB setup:

```bash
# OpenAI API key (required for AI agents)
OPENAI_API_KEY=sk-your-openai-api-key-here

# Local DuckDB setup (no credentials needed!)
BACKEND_TYPE=duckdb
DUCKDB_DATABASE_PATH=./synthetic_data/synthea.duckdb
DUCKDB_SCHEMA=main

# Security settings for local development
MAX_COST_USD=10.0
ALLOW_PATIENT_LIST=true
QUERY_TIMEOUT_SEC=60

# HTTP server settings
HTTP_HOST=0.0.0.0
HTTP_PORT=8000
```

### 3. Start OMOP MCP Server

```bash
# Start in HTTP mode
uv run python -m omop_mcp.server --http --port 8000

# Server will be available at http://localhost:8000
# SSE endpoint: http://localhost:8000/sse
```

### 4. Configure LibreChat

Add MCP server configuration to LibreChat:

**File**: `librechat/config/endpoints.js`

```javascript
module.exports = {
  // ... existing endpoints ...

  mcp: {
    'omop-mcp': {
      serverUrl: 'http://localhost:8000/sse',
      tools: [
        'discover_concepts',
        'get_concept_relationships',
        'query_omop',
        'generate_cohort_sql',
        'get_information_schema',
        'select_query'
      ],
      resources: [
        'omop://concept/{concept_id}',
        'athena://search',
        'backend://capabilities'
      ]
    }
  }
};
```

**File**: `librechat/config/models.js`

```javascript
module.exports = {
  // ... existing models ...

  ollama: {
    'llama3.1:8b': {
      contextLength: 8192,
      mcpServers: ['omop-mcp']
    },
    'codellama:7b': {
      contextLength: 16384,
      mcpServers: ['omop-mcp']
    }
  }
};
```

### 5. Restart LibreChat

```bash
# Restart LibreChat to load MCP configuration
npm run restart
# or
docker-compose restart librechat
```

## Configuration Examples

### DuckDB with Synthetic Data

```bash
# Download Synthea synthetic data
wget https://github.com/synthetichealth/synthea/releases/download/v3.0.0/synthea_sample_data_csv_apr2020.zip
unzip synthea_sample_data_csv_apr2020.zip

# Convert to DuckDB (example script)
python scripts/convert_synthea_to_duckdb.py synthea_sample_data_csv_apr2020/ synthea.duckdb

# Configure for DuckDB
BACKEND_TYPE=duckdb
DUCKDB_DATABASE_PATH=./synthea.duckdb
DUCKDB_SCHEMA=main
```

### BigQuery Integration

```bash
# For cloud data access
BACKEND_TYPE=bigquery
BIGQUERY_PROJECT_ID=your-project
BIGQUERY_DATASET_ID=omop_cdm
BIGQUERY_CREDENTIALS_PATH=/path/to/service-account.json
MAX_COST_USD=5.0
```

### Snowflake Integration

```bash
# For enterprise data warehouse
BACKEND_TYPE=snowflake
SNOWFLAKE_ACCOUNT=your-account.snowflakecomputing.com
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_DATABASE=omop_db
SNOWFLAKE_SCHEMA=cdm
SNOWFLAKE_WAREHOUSE=compute_wh
```

## Usage Examples

### 1. Concept Discovery

```
User: "Find all diabetes-related concepts in the OMOP vocabulary"

LibreChat: I'll search for diabetes concepts using the OMOP MCP server.

[Uses discover_concepts tool]

Found 12 diabetes-related concepts:

**Standard Concepts:**
- Type 2 diabetes mellitus (concept_id: 201826) - SNOMED
- Type 1 diabetes mellitus (concept_id: 201254) - SNOMED
- Diabetes mellitus (concept_id: 201820) - SNOMED
- Diabetic nephropathy (concept_id: 201530) - SNOMED

**Non-Standard Concepts:**
- Diabetes mellitus, type 2 (concept_id: 4193704) - ICD10CM
- Diabetes mellitus, type 1 (concept_id: 4193705) - ICD10CM

Would you like me to generate a query to count patients with these conditions?
```

### 2. Patient Demographics

```
User: "Show me the age and gender distribution of diabetic patients"

LibreChat: I'll analyze the demographics of patients with diabetes.

[Uses discover_concepts then query_omop with breakdown]

**Demographics of Diabetic Patients:**

**By Gender:**
- Female: 1,234 patients (52.3%)
- Male: 1,126 patients (47.7%)

**By Age Group:**
- 18-30: 45 patients (1.9%)
- 31-45: 234 patients (9.9%)
- 46-60: 567 patients (24.0%)
- 61-75: 890 patients (37.7%)
- 76+: 624 patients (26.4%)

**Total:** 2,360 patients with diabetes

The analysis shows diabetes is more common in older age groups, with peak prevalence in the 61-75 age range.
```

### 3. Schema Exploration

```
User: "What tables and columns are available in this OMOP database?"

LibreChat: I'll explore the database schema to show you available tables and columns.

[Uses get_information_schema tool]

**OMOP CDM Database Schema:**

**Core Tables:**
- **person** (15 columns): Patient demographics and basic information
- **condition_occurrence** (15 columns): Medical conditions and diagnoses
- **drug_exposure** (25 columns): Medication records and prescriptions
- **procedure_occurrence** (12 columns): Medical procedures and interventions
- **measurement** (20 columns): Lab values, vital signs, and measurements
- **observation** (15 columns): Clinical observations and assessments
- **visit_occurrence** (18 columns): Healthcare encounters and visits
- **death** (8 columns): Mortality data and cause of death

**Vocabulary Tables:**
- **concept** (12 columns): OMOP concept definitions and metadata
- **vocabulary** (6 columns): Vocabulary system metadata
- **concept_relationship** (8 columns): Concept mappings and relationships
- **concept_ancestor** (4 columns): Concept hierarchy and ancestry

**Reference Tables:**
- **location** (10 columns): Geographic locations and addresses
- **care_site** (12 columns): Healthcare facilities and organizations
- **provider** (15 columns): Healthcare providers and clinicians

Would you like me to show the detailed column structure for any specific table?
```

### 4. Direct SQL Queries

```
User: "Show me the top 10 most prescribed medications"

LibreChat: I'll execute a SQL query to find the most commonly prescribed medications.

[Uses select_query tool]

**Top 10 Most Prescribed Medications:**

1. **Metformin** (concept_id: 1503297): 2,456 prescriptions
2. **Lisinopril** (concept_id: 1308216): 1,987 prescriptions
3. **Atorvastatin** (concept_id: 1539411): 1,765 prescriptions
4. **Amlodipine** (concept_id: 1332419): 1,543 prescriptions
5. **Omeprazole** (concept_id: 1115009): 1,432 prescriptions
6. **Simvastatin** (concept_id: 1551860): 1,321 prescriptions
7. **Hydrochlorothiazide** (concept_id: 974166): 1,234 prescriptions
8. **Losartan** (concept_id: 1341927): 1,123 prescriptions
9. **Gabapentin** (concept_id: 1503327): 1,012 prescriptions
10. **Furosemide** (concept_id: 974166): 987 prescriptions

Query executed in 0.8 seconds, scanned 1.2GB of data.
```

### 5. Cohort Analysis

```
User: "Generate SQL for patients who had a heart attack after taking statins"

LibreChat: I'll create a cohort analysis for statin users who developed myocardial infarction.

[Uses discover_concepts for both conditions, then generate_cohort_sql]

**Cohort Definition:**
- **Exposure:** Statin medications (atorvastatin, simvastatin, etc.)
- **Outcome:** Myocardial infarction
- **Time Window:** Any time after statin initiation
- **Logic:** First statin exposure per patient

**Generated SQL:**

```sql
WITH exposure AS (
  SELECT DISTINCT person_id, drug_exposure_start_date AS exposure_date
  FROM drug_exposure
  WHERE drug_concept_id IN (
    1539411,  -- Atorvastatin
    1551860,  -- Simvastatin
    1551861,  -- Pravastatin
    1551862   -- Lovastatin
  )
),
outcome AS (
  SELECT DISTINCT person_id, condition_start_date AS outcome_date
  FROM condition_occurrence
  WHERE condition_concept_id IN (312327)  -- Myocardial infarction
),
cohort AS (
  SELECT e.person_id, e.exposure_date, o.outcome_date,
    DATE_DIFF(o.outcome_date, e.exposure_date, DAY) AS days_to_outcome
  FROM exposure e
  INNER JOIN outcome o ON e.person_id = o.person_id
  WHERE e.exposure_date <= o.outcome_date
)
SELECT * FROM cohort
QUALIFY ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY exposure_date) = 1;
```

**Cohort Results:**
- **Total patients:** 1,234 patients
- **With outcome:** 89 patients (7.2%)
- **Median time to outcome:** 45 days
- **Range:** 1-365 days

This analysis shows the temporal relationship between statin use and myocardial infarction events.
```

## Network Configuration

### CORS Setup

If accessing LibreChat from a different domain, configure CORS:

```bash
# Add to .env
CORS_ORIGINS=http://localhost:3080,http://localhost:3000,https://your-librechat-domain.com
```

### Firewall Configuration

```bash
# Allow HTTP traffic on port 8000
sudo ufw allow 8000/tcp

# For Docker deployments
docker run -p 8000:8000 omop-mcp-server
```

### SSL/TLS Setup

For production deployments with HTTPS:

```bash
# Generate SSL certificate
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Configure HTTPS
HTTPS_ENABLED=true
SSL_CERT_PATH=./cert.pem
SSL_KEY_PATH=./key.pem
```

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install UV
RUN pip install uv

# Copy project files
COPY . .

# Install dependencies
RUN uv pip install -e ".[duckdb]"

# Expose port
EXPOSE 8000

# Start server
CMD ["uv", "run", "python", "-m", "omop_mcp.server", "--http", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  omop-mcp:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - BACKEND_TYPE=duckdb
      - DUCKDB_DATABASE_PATH=/data/synthea.duckdb
    volumes:
      - ./data:/data
    restart: unless-stopped

  librechat:
    image: ghcr.io/danny-avila/librechat:latest
    ports:
      - "3080:3080"
    environment:
      - MCP_SERVERS={"omop-mcp":{"serverUrl":"http://omop-mcp:8000/sse"}}
    depends_on:
      - omop-mcp
    restart: unless-stopped
```

## Troubleshooting

### Common Issues

**"Connection refused to MCP server"**
- Verify OMOP MCP server is running: `curl http://localhost:8000/health`
- Check firewall settings and port accessibility
- Ensure LibreChat can reach the MCP server URL

**"SSE connection failed"**
- Verify SSE endpoint is accessible: `curl http://localhost:8000/sse`
- Check CORS configuration if accessing from different domains
- Ensure LibreChat MCP configuration is correct

**"Ollama model not responding"**
- Verify Ollama is running: `ollama list`
- Check model availability: `ollama pull llama3.1:8b`
- Ensure sufficient system resources (RAM, CPU)

**"Database connection failed"**
- For DuckDB: verify database file exists and is readable
- For BigQuery: check service account permissions
- For Snowflake: verify account URL and credentials

### Debug Mode

Enable detailed logging:

```bash
# MCP Server debug
LOG_LEVEL=DEBUG

# LibreChat debug
DEBUG=true
VERBOSE_DEBUG=true
```

### Performance Optimization

**For Local Development:**
```bash
# Use DuckDB for fastest local performance
BACKEND_TYPE=duckdb
DUCKDB_DATABASE_PATH=:memory:  # In-memory for speed

# Increase timeouts for complex queries
QUERY_TIMEOUT_SEC=120
```

**For Production:**
```bash
# Use connection pooling
DATABASE_POOL_SIZE=10
DATABASE_POOL_TIMEOUT=30

# Enable query caching
ENABLE_QUERY_CACHE=true
QUERY_CACHE_TTL=3600
```

## Security Considerations

### Local Development
```bash
# More permissive for development
ALLOW_PATIENT_LIST=true
MAX_COST_USD=50.0
STRICT_TABLE_VALIDATION=false
```

### Production Deployment
```bash
# Strict security for production
ALLOW_PATIENT_LIST=false
MAX_COST_USD=1.0
STRICT_TABLE_VALIDATION=true
PHI_MODE=false

# Enable authentication
OAUTH_ISSUER=https://your-auth-provider.com
OAUTH_AUDIENCE=omop-mcp-api
```

## Next Steps

- Explore the [Claude Desktop Integration](claude-desktop.md) for desktop usage
- Read the [Generic MCP Client Guide](generic-mcp-client.md) for other clients
- Check out the [API Reference](../api/tools.md) for detailed tool documentation
- Review the [SQL Validation Guide](../sql-validation.md) for security features
