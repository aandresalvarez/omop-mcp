Perfect—here’s a **fully revised, developer-ready plan** that folds in your new “multi-step analytical queries” requirement while keeping the system clean, secure, and extensible to future backends (Postgres, Snowflake, DuckDB, …). Hand this to your dev and they can execute.

# OMOP MCP Server — Plan v2 (with Multi-Step Analytics)

## 0) Objectives & Scope

### Objectives

* Ship an MCP server that supports:

  * **Tools**

    * `discover_concepts` — NL term → standard concepts (+relationships)
    * `get_concept_relationships` — relationships for a concept
    * `generate_cohort_sql` — cohort SQL (deferred-ready)
    * **`query_omop` (NEW)** — execute **analytical** queries (count/breakdown/list) using concept IDs
  * **Resources**

    * `omop://concept/{id}` — concept JSON (cacheable)
    * `athena://search` — cursor-paginated search
    * `backend://capabilities` — available engines & features
  * **Prompts**

    * `prompt://cohort/sql` — reusable SQL synthesis prompt
* Support **BigQuery** now; keep a pluggable backend interface for **Postgres** and others.
* Provide **Streamable HTTP** (for IDEs/Claude connector) and **stdio** (local dev).
* Add **strict execution guards** (cost/row limits, non-mutating, PHI safety).

### Out of Scope

* PHI processing beyond person_id listing in controlled dev modes.
* Query caching at DB level (may add later).

---

## 1) Repo Layout

```
omop-mcp/
├─ pyproject.toml
├─ .env.example
├─ Makefile
├─ src/omop_mcp/
│  ├─ __init__.py
│  ├─ server.py                  # FastMCP app (stdio + HTTP)
│  ├─ auth.py                    # OAuth2.1 token validation (middleware/hooks)
│  ├─ config.py                  # Pydantic settings
│  ├─ models.py                  # Domain models (OMOPConcept, SQLValidationResult, ...)
│  ├─ resources.py               # MCP resources
│  ├─ prompts.py                 # MCP prompts
│  ├─ backends/
│  │  ├─ base.py                 # Backend protocol + dataclasses
│  │  ├─ bigquery.py             # BigQuery implementation
│  │  ├─ postgres.py             # Postgres stub (implemented incrementally)
│  │  └─ registry.py             # get_backend(), capability listing
│  ├─ tools/
│  │  ├─ athena.py               # ATHENA search & relationships
│  │  ├─ sqlgen.py               # Cohort SQL synthesis (uses PydanticAI)
│  │  └─ query.py                # ★ NEW: analytical query runner (count/breakdown/list)
│  └─ agents/
│     ├─ concept_agent.py        # PydanticAI mapping NL→concepts (optional)
│     └─ sql_agent.py            # PydanticAI for SQL drafting (deferred-ready)
└─ tests/
   ├─ test_mcp_tools.py
   ├─ test_resources.py
   ├─ test_sql_backends.py
   ├─ test_query_tool.py         # ★ NEW
   ├─ test_query_security.py     # ★ NEW
   └─ test_multi_step_query.py   # ★ NEW (end-to-end “flu” scenario)
```

---

## 2) Dependencies (pinned)

```toml
[project]
name = "omop-mcp"
version = "0.2.0"
requires-python = ">=3.11"
dependencies = [
  "mcp[cli]>=1.2.0",
  "pydantic>=2.7",
  "pydantic-ai>=1.1.0",
  "pydantic-settings>=2.2",
  "athena-client==1.0.27",
  "openai>=1.50.0",
  "httpx>=0.27",
  "structlog>=24.1",
  "tenacity>=9.0",
  "starlette>=0.40",
  "uvicorn>=0.30",
  "google-cloud-bigquery>=3.25.0",
  "psycopg[binary,pool]>=3.2",      # future PG
  "asyncpg>=0.29"                    # optional PG driver
]

[project.optional-dependencies]
dev = ["pytest>=8","pytest-asyncio>=0.23","pytest-cov>=5","ruff>=0.6","mypy>=1.10","black>=24"]

[project.scripts]
omop-mcp = "omop_mcp.server:main"
```

**Makefile**

```
.PHONY: dev run http stdio test fmt lint type
dev:    uv pip install -e .[dev]
http:   uv run python -m omop_mcp.server --http --port 8000
stdio:  uv run python -m omop_mcp.server --stdio
test:   uv run pytest -q --maxfail=1
fmt:    uv run black src tests
lint:   ruff check src tests
type:   uv run mypy src
```

**.env.example**

```
OPENAI_API_KEY=sk-***
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0.0

ATHENA_BASE_URL=https://athena.ohdsi.org/api/v1
ATHENA_TIMEOUT=30

BIGQUERY_PROJECT_ID=your-project
BIGQUERY_DATASET_ID=omop_cdm54
BIGQUERY_LOCATION=US

POSTGRES_DSN=postgresql://user:pass@host:5432/dbname
POSTGRES_SCHEMA=public

# Auth
OAUTH_ISSUER=https://auth.example.com/
OAUTH_AUDIENCE=omop-mcp

# Execution guards
MAX_QUERY_COST_USD=1.0
ALLOW_PATIENT_LIST=false
QUERY_TIMEOUT_SEC=30
LOG_LEVEL=INFO
```

---

## 3) Config & Models (diffs only)

**config.py (add guards)**

```python
class OMOPConfig(BaseSettings):
    ...
    # BigQuery
    bigquery_project_id: str | None = None
    bigquery_dataset_id: str | None = None

    # Postgres
    postgres_dsn: str | None = None
    postgres_schema: str = "public"

    # Execution guards
    max_query_cost_usd: float = 1.0
    allow_patient_list: bool = False
    query_timeout_sec: int = 30
```

**models.py (already OK from v1)**

* `SQLValidationResult`, `CohortSQLResult` retained.
* Ensure `CohortSQLResult` includes `backend`, `dialect`.

---

## 4) Backends (Protocol + New execute_query)

**backends/base.py**

```python
class Backend(Protocol):
    name: str
    dialect: str

    async def build_cohort_sql(self, exposure_ids: list[int], outcome_ids: list[int], pre_outcome_days: int, cdm: str = "5.4") -> CohortQueryParts: ...
    async def validate_sql(self, sql: str) -> SQLValidationResult: ...

    # NEW: execute SQL safely (adds LIMIT if missing, blocks mutations)
    async def execute_query(self, sql: str, limit: int = 1000) -> list[dict]: ...

    # Helper methods for dialect-specific SQL generation
    def qualified_table(self, table: str) -> str:
        """Generate dialect-specific qualified table name (project.dataset.table or schema.table)."""
        ...

    def age_calculation_sql(self, birth_col: str = "birth_datetime") -> str:
        """Generate dialect-specific age calculation SQL."""
        ...
```

**backends/bigquery.py (extend with execute_query)**

```python
async def execute_query(self, sql: str, limit: int = 1000) -> list[dict]:
    from google.cloud import bigquery as bq
    up = sql.upper()
    if any(kw in up for kw in ("DELETE","UPDATE","DROP","TRUNCATE","ALTER","MERGE")):
        raise ValueError("Mutating queries not allowed")
    if "LIMIT" not in up:
        sql = f"{sql}\nLIMIT {limit}"
    client = bq.Client()
    job = client.query(sql, timeout=config.query_timeout_sec)
    rows = job.result()
    return [dict(r) for r in rows]

def qualified_table(self, table: str) -> str:
    """Return BigQuery-style fully qualified table name."""
    return f"`{config.bigquery_project_id}.{config.bigquery_dataset_id}.{table}`"

def age_calculation_sql(self, birth_col: str = "birth_datetime") -> str:
    """Return BigQuery-specific age calculation."""
    return f"EXTRACT(YEAR FROM CURRENT_DATE()) - EXTRACT(YEAR FROM {birth_col})"
```

**backends/postgres.py (stub now, implement next)**

```python
async def execute_query(self, sql: str, limit: int = 1000) -> list[dict]:
    import asyncpg
    up = sql.upper()
    if any(kw in up for kw in ("DELETE","UPDATE","DROP","TRUNCATE","ALTER","MERGE")):
        raise ValueError("Mutating queries not allowed")
    if "LIMIT" not in up:
        sql = f"{sql}\nLIMIT {limit}"

    conn = await asyncpg.connect(config.postgres_dsn)
    try:
        rows = await conn.fetch(sql)
        return [dict(r) for r in rows]
    finally:
        await conn.close()

def qualified_table(self, table: str) -> str:
    """Return Postgres-style schema.table name (no backticks)."""
    return f"{config.postgres_schema}.{table}"

def age_calculation_sql(self, birth_col: str = "birth_datetime") -> str:
    """Return Postgres-specific age calculation."""
    return f"extract(year from age(current_date, {birth_col}))"
```

**backends/registry.py**

* unchanged; keep `bigquery` live, `postgres` present but clearly “beta”.

---

## 5) Tools

### 5.1 `discover_concepts` & `get_concept_relationships`

* Keep your existing ATHENA wrapper.
* Return **only** standard concepts by default; include raw list in `search_metadata` if needed.

### 5.2 `generate_cohort_sql`

* Use PydanticAI to draft SQL; call backend for validation (dry-run on BQ).
* Mark MCP tool as `deferred=True` (even if v1 executes synchronously) to keep the door open for long validations/human approvals.

### 5.3 **NEW `query_omop`** (analytical queries)

**tools/query.py**

```python
from typing import List, Dict, Any
from omop_mcp.backends.registry import get_backend
from omop_mcp.config import config

TABLE_BY_DOMAIN = {
    "Condition": "condition_occurrence",
    "Drug": "drug_exposure",
    "Procedure": "procedure_occurrence",
    "Measurement": "measurement",
    "Observation": "observation",
}

def _concept_col(domain: str) -> str:
    d = domain.lower()
    if d == "condition":   return "condition_concept_id"
    if d == "drug":        return "drug_concept_id"
    if d == "procedure":   return "procedure_concept_id"
    if d == "measurement": return "measurement_concept_id"
    if d == "observation": return "observation_concept_id"
    return "condition_concept_id"

async def query_by_concepts(
    query_type: str,          # "count" | "breakdown" | "list_patients"
    concept_ids: List[int],
    domain: str,
    backend: str,
    execute: bool,
    limit: int = 1000
) -> Dict[str, Any]:
    if not concept_ids:
        raise ValueError("concept_ids cannot be empty")

    be = get_backend(backend)
    table = TABLE_BY_DOMAIN.get(domain, "condition_occurrence")
    col   = _concept_col(domain)

    # Use parameterized queries for security (concept_ids are validated ints, but best practice)
    # Note: For v1.0 we use string interpolation since concept_ids are Pydantic-validated ints
    # TODO v1.1: Refactor to use backend-specific parameterized queries
    concept_list = ','.join(map(str, concept_ids))

    # --- SQL builders using backend helper methods for dialect compatibility ---
    if query_type == "count":
        sql = f"""
SELECT COUNT(DISTINCT person_id) AS patient_count
FROM {be.qualified_table(table)}
WHERE {col} IN ({concept_list})
""".strip()

    elif query_type == "breakdown":
        sql = f"""
SELECT
  p.gender_concept_id,
  {be.age_calculation_sql("p.birth_datetime")} AS age_years,
  COUNT(DISTINCT p.person_id) AS patient_count
FROM {be.qualified_table(table)} t
JOIN {be.qualified_table("person")} p ON t.person_id = p.person_id
WHERE t.{col} IN ({concept_list})
GROUP BY 1, 2
ORDER BY patient_count DESC
LIMIT {limit}
""".strip()

    elif query_type == "list_patients":
        if not config.allow_patient_list:
            raise ValueError("list_patients not allowed (protected in this environment)")
        concept_list = ','.join(map(str, concept_ids))
        sql = f"""
SELECT DISTINCT person_id
FROM {be.qualified_table(table)}
WHERE {col} IN ({concept_list})
LIMIT {limit}
""".strip()

    else:
        raise ValueError("query_type must be one of: count | breakdown | list_patients")

    # --- Validate cost first ---
    validation = await be.validate_sql(sql)

    results = None
    row_count = None
    if execute:
        # cost guard
        if (validation.estimated_cost_usd or 0) > config.max_query_cost_usd:
            raise ValueError(f"Query too expensive (${validation.estimated_cost_usd:.4f}). Set execute=false to fetch SQL only.")
        results = await be.execute_query(sql, limit)
        row_count = len(results)

    return {
        "sql": sql,
        "results": results,
        "row_count": row_count,
        "estimated_cost_usd": validation.estimated_cost_usd,
        "estimated_bytes": validation.estimated_bytes,
        "backend": be.name,
        "dialect": be.dialect
    }
```

---

## 6) Server (FastMCP) & Transports

**server.py (delta): add `query_omop`)**

```python
from mcp.server.fastmcp import FastMCP, Context
from omop_mcp.tools import athena as t_athena, sqlgen as t_sql, query as t_query

mcp = FastMCP("omop-mcp", spec_version="2025-06-18")

@mcp.tool()
async def discover_concepts(ctx: Context, **kwargs):
    return await t_athena.discover_concepts(**kwargs)

@mcp.tool()
async def get_concept_relationships(ctx: Context, **kwargs):
    return await t_athena.get_concept_relationships(**kwargs)

@mcp.tool(deferred=True)
async def generate_cohort_sql(ctx: Context, **kwargs):
    return await t_sql.generate_sql(ctx.request_context, **kwargs)

# ★ NEW
@mcp.tool()
async def query_omop(
    ctx: Context,
    query_type: str,
    concept_ids: list[int],
    domain: str = "Condition",
    backend: str = "bigquery",
    execute: bool = True,
    limit: int = 1000
):
    return await t_query.query_by_concepts(query_type, concept_ids, domain, backend, execute, limit)
```

**Resources/Prompts**

* Keep as in v1; add `backend://capabilities` returning `name`, `dialect`, `features` (e.g., `["dry_run","cost_estimate","execute"]`).

**Transports**

* `stdio` for Inspector (dev).
* `http_app()` for Streamable HTTP + CORS (expose `Mcp-Session-Id`).

---

## 7) Security & Governance

* **Auth**: OAuth2.1 (verify iss/aud/exp; extract `sub`, `tenant`, `scopes`).
* **Guards**:

  * Always **dry-run** before execution; enforce `MAX_QUERY_COST_USD`.
  * **Block mutations** (`DELETE/UPDATE/DROP/TRUNCATE/ALTER/MERGE`) in `execute_query`.
  * **Row cap**: hard cap result sets (`limit<=1000`); inject `LIMIT` if missing.
  * **PHI safety**: `list_patients` disabled by default; require env flag + role.
  * **Timeouts**: `QUERY_TIMEOUT_SEC` (e.g., 30s) for execution.
* **Audit/Logs**: subject, tool, backend, dialect, args size, estimated bytes/cost, rows returned, p50/p95.

---

## 8) Testing (expanded)

* **Unit**

  * `test_athena_client.py`: map ATHENA → `OMOPConcept`; relationship filters.
  * `test_sql_backends.py`: `build_cohort_sql()` + `validate_sql()` + **`execute_query()`** (BQ with small public dataset or mocked client).
  * `test_query_tool.py`: `query_by_concepts()` for `count|breakdown|list_patients` (mock backend to assert SQL shape & guard behavior).
* **Security**

  * `test_query_security.py`: blocks mutations; enforces cost cap; applies row limit; rejects `list_patients` when flag off.
* **Integration / E2E**

  * `test_multi_step_query.py`: “flu”

    1. `discover_concepts("flu")` → concept_ids
    2. `query_omop(count, ids, domain="Condition", execute=false)` → SQL + estimate
    3. `query_omop(..., execute=true)` (only if estimate < cap) → results
* **Golden SQL**

  * Normalize whitespace & compare tokenized SQL (per backend) so future refactors don’t regress logic.

---

## 9) Rollout Plan (3 Weeks, updated)

**Week 1 — Foundations & Analytics**

* Scaffold; FastMCP server (stdio + HTTP); config; structlog; auth stub.
* ATHENA wrapper: search/get/relationships.
* Tools: `discover_concepts`, `get_concept_relationships`, **`query_omop`**.
* Backends: BigQuery `validate_sql()` + **`execute_query()`**.
* Resources: `omop://concept/{id}`, `athena://search` (cursor), `backend://capabilities`.
* Prompts: `prompt://cohort/sql`.
* Tests: query & security suites.

**Week 2 — Cohort SQL + Agents**

* `generate_cohort_sql` via PydanticAI; cost/bytes via BQ dry-run.
* Mark `generate_cohort_sql` as `deferred=True` (keep sync for v2.0 if needed).
* Golden SQL tests; metrics fields (latency histograms, bytes processed).

**Week 3 — Hardening & PG Stub**

* OAuth validation middleware + per-tool authZ.
* Rate limiting (gateway); structured audit logs.
* Postgres backend: minimal `execute_query` + age/date diff translation; enable in `capabilities`.
* CI: pytest, ruff, mypy; container image.

---

## 10) Acceptance Criteria (updated)

* MCP spec `"2025-06-18"`, **HTTP** + **stdio** transports.
* Tools return validated JSON; resources paginate with `next_page`.
* **`query_omop`**

  * Supports `count`, `breakdown`, `list_patients` (flag-gated).
  * Always dry-runs; rejects if estimated cost > `MAX_QUERY_COST_USD`.
  * Blocks mutating SQL; injects/enforces `LIMIT<=1000`.
  * Returns `{sql, results?, row_count?, estimated_cost_usd, estimated_bytes, backend, dialect}`.
* `generate_cohort_sql` returns valid SQL + validation (BQ).
* `backend://capabilities` lists `bigquery` (live) and `postgres` (beta).
* **E2E flu workflow** passes.
* Logs include subject, tool, backend/dialect, latency, estimated bytes/cost, and row_count.

---

## 11) Example Calls

**Step 1: discover concepts**

```json
{
  "tool": "discover_concepts",
  "arguments": { "clinical_text": "flu", "domain": "Condition" }
}
```

**Step 2a: estimate cost only**

```json
{
  "tool": "query_omop",
  "arguments": {
    "query_type": "count",
    "concept_ids": [4171852,4171853],
    "domain": "Condition",
    "execute": false
  }
}
```

**Step 2b: execute if cheap**

```json
{
  "tool": "query_omop",
  "arguments": {
    "query_type": "count",
    "concept_ids": [4171852,4171853],
    "domain": "Condition",
    "execute": true
  }
}
```

---

## 12) Notes on Dialects & SQL Safety

### Dialect Differences (now addressed via backend helpers)

* **Age calculation**:
  - BigQuery: `EXTRACT(YEAR FROM CURRENT_DATE()) - EXTRACT(YEAR FROM birth_datetime)`
  - Postgres: `extract(year from age(current_date, birth_date))`
  - **Solution**: Use `backend.age_calculation_sql()` method

* **Table qualification**:
  - BigQuery: `` `project.dataset.table` `` (backticks required)
  - Postgres: `schema.table` (no backticks)
  - **Solution**: Use `backend.qualified_table()` method

* **Arrays/UNNEST**:
  - BigQuery: `IN UNNEST(@array_param)`
  - Postgres: `= ANY(@array_param::int[])`
  - **TODO v1.1**: Implement parameterized queries per backend

* **Window functions**:
  - BigQuery: `QUALIFY` clause for window filtering
  - Postgres: Subquery with `WHERE rn = 1` pattern
  - **Solution**: Keep in backend-specific `build_cohort_sql()`

### SQL Injection Prevention

**v1.0 Approach** (current plan):
- Concept IDs are Pydantic-validated as `List[int]` before use
- String interpolation: `concept_ids` → `','.join(map(str, concept_ids))`
- Type coercion ensures only integers are inserted
- **Risk Level**: Low (validated ints only)

**v1.1 Improvement** (recommended):
```python
# BigQuery parameterized query example
from google.cloud import bigquery

job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ArrayQueryParameter("concept_ids", "INT64", concept_ids)
    ]
)
sql = "SELECT COUNT(*) FROM table WHERE concept_id IN UNNEST(@concept_ids)"
job = client.query(sql, job_config=job_config)
```

**Action Items**:
- ✅ v1.0: Use string interpolation with validated ints (acceptable risk)
- 📋 v1.1: Refactor to native parameter binding per backend
- 📋 v1.1: Add backend method `build_parameterized_query(sql, params)`

---

## 13) What's Next (v1.1+ Improvements)

### High Priority

* ✅ **SQL Parameterization**: Refactor `query_by_concepts` to use native parameter binding
  - BigQuery: `UNNEST(@concept_ids)` with `QueryJobConfig`
  - Postgres: `= ANY($1::int[])` with asyncpg parameters
  - Benefits: Defense-in-depth security, better query plan caching

* ✅ **Complete Postgres Implementation**:
  - Full `execute_query` with connection pooling
  - Implement `build_cohort_sql` for Postgres dialect
  - Add integration tests with Postgres test container

* ✅ **Backend Method Refactoring**:
  - Migrate all SQL generation to use `backend.qualified_table()`
  - Migrate all age calculations to use `backend.age_calculation_sql()`
  - Add `backend.parameterize_concepts()` for safe concept list binding

### Medium Priority

* **True DeferredToolRequests/Results** for long/approved runs
  - Implement async completion for queries >10s
  - Add human-in-the-loop approval for queries >$10

* **SQLGlot Integration**:
  - Add transpilation layer to reduce backend-specific SQL
  - Write SQL in canonical form, transpile to target dialect
  - Example: `sqlglot.transpile(sql, read="postgres", write="bigquery")`

* **Enhanced Query Types**:
  - `"cohort_overlap"`: Venn diagram of concept sets
  - `"time_series"`: Events over time buckets
  - `"prevalence"`: Concept prevalence by demographics

### Low Priority

* **Domain shortcuts** (predefined concept sets for common conditions)
* **Result formatters** (histograms for age buckets, sex/gender pivot, JSON-Schema for outputs)
* **Query caching**: Redis/Memcached for repeated queries
* **Cost alerts**: Slack/email notifications for expensive queries

---

## 14) Implementation Checklist

### Week 1
- [ ] Scaffold repo with pyproject.toml and .env.example
- [ ] Implement FastMCP server (stdio + HTTP transports)
- [ ] Create `backends/base.py` with Protocol (including helper methods)
- [ ] Implement `backends/bigquery.py` with all methods
- [ ] Stub `backends/postgres.py` with helper methods
- [ ] Create `tools/athena.py` (ATHENA client wrapper)
- [ ] Create `tools/query.py` with dialect-aware SQL generation
- [ ] Implement `discover_concepts`, `get_concept_relationships`, `query_omop` tools
- [ ] Add security guards (cost validation, mutation blocking, row limits)
- [ ] Write unit tests for query tool and security

### Week 2
- [ ] Implement `tools/sqlgen.py` for cohort SQL generation
- [ ] Add PydanticAI agents for concept discovery and SQL generation
- [ ] Implement `generate_cohort_sql` tool with deferred support
- [ ] Add golden SQL tests
- [ ] Add metrics/logging for all tool calls
- [ ] Write integration tests for multi-step workflows

### Week 3
- [ ] Implement OAuth2.1 token validation middleware
- [ ] Add rate limiting and audit logging
- [ ] Complete Postgres backend (execute_query + tests)
- [ ] Set up CI pipeline (pytest, ruff, mypy)
- [ ] Build container image
- [ ] Write end-to-end acceptance tests
- [ ] Update documentation and README

---

### TL;DR

This v2 plan adds the **`query_omop`** tool and **`execute_query`** backend method, enabling your two-step flow (discover → execute) for questions like *"How many patients with flu?"* while preserving clean extensibility and strict safety controls.

---

## 15) Summary of Changes from v1

### Architectural Improvements

1. **Backend Helper Methods** (NEW):
   - Added `qualified_table(table: str)` for dialect-specific table naming
   - Added `age_calculation_sql(birth_col: str)` for dialect-specific age calculation
   - Eliminates hardcoded dialect logic in tool layer

2. **Multi-Step Analytics Workflow** (NEW):
   - Added `query_omop` tool supporting `count`, `breakdown`, `list_patients`
   - Enables "discover concepts → execute query" pattern
   - Full integration with existing `discover_concepts` tool

3. **Enhanced Security** (IMPROVED):
   - SQL injection prevention via Pydantic type validation (v1.0)
   - Roadmap for native parameter binding (v1.1)
   - Cost validation before execution (hard $1 limit)
   - Mutation blocking (DELETE/UPDATE/DROP/etc.)
   - Row limits (max 1000)
   - PHI protection (list_patients flag-gated)
   - Query timeouts (30s default)

4. **Postgres Support** (EXPANDED):
   - Added complete `execute_query` implementation
   - Added dialect helper methods
   - Documented schema configuration
   - Ready for v1.0 beta testing

### Configuration Changes

- Added `POSTGRES_SCHEMA=public` to .env.example
- Added `postgres_schema` field to OMOPConfig
- Added execution guard configurations

### Testing Enhancements

- Added `test_query_tool.py` for analytical queries
- Added `test_query_security.py` for security guards
- Added `test_multi_step_query.py` for E2E workflows
- Enhanced golden SQL tests for both dialects

### Documentation Improvements

- Section 12: Comprehensive dialect differences guide
- Section 13: Clear v1.1 improvement roadmap
- Section 14: Detailed implementation checklist
- Section 15: This summary of changes

---

## 16) Developer Handoff Checklist

Before starting development, ensure you have:

### Access & Credentials
- [ ] OpenAI API key (for PydanticAI agents)
- [ ] Google Cloud project with BigQuery enabled
- [ ] OMOP CDM dataset in BigQuery (or public OMOP dataset for testing)
- [ ] OAuth2.1 provider details (issuer, audience) for auth

### Environment Setup
- [ ] Python 3.11+ installed
- [ ] `uv` package manager installed
- [ ] Clone repo and create `.env` from `.env.example`
- [ ] Test ATHENA API connectivity
- [ ] Test BigQuery connectivity with dry-run query

### Understanding the Architecture
- [ ] Review Section 1 (Repo Layout)
- [ ] Review Section 4 (Backend Protocol)
- [ ] Review Section 5.3 (query_omop implementation)
- [ ] Review Section 11 (Example workflow)
- [ ] Review Section 12 (Dialect differences)

### Development Workflow
- [ ] Start with Week 1 deliverables (Section 14)
- [ ] Use `make dev` to install dependencies
- [ ] Use `make test` to run tests after each component
- [ ] Use `make stdio` for local testing with MCP Inspector
- [ ] Commit after each completed checklist item

### Questions to Ask
- Should we implement SQLGlot in v1.0 or defer to v1.1?
- What's the preferred OAuth provider (Okta, Auth0, custom)?
- Do we need DuckDB support in addition to BigQuery/Postgres?
- What's the target deployment platform (Cloud Run, ECS, K8s)?

---

**STATUS**: ✅ Plan finalized and ready for development handoff.

**NEXT STEPS**:
1. Developer creates feature branch from `main`
2. Implements Week 1 checklist (Section 14)
3. Runs tests (`make test`) to validate
4. Opens PR with Week 1 deliverables for review
