# Option B: Partial Import - Component Analysis

## 📦 Folders to Copy

### 1. **cd (Concept Discovery)** - Stage 2

**What You're Getting:**
```
 /cd/
├── find_concepts.py          # Main orchestration
├── tools.py                  # ATHENA search/details/relationships
├── agents.py                 # Decomposer, Explorer, Acceptor agents
├── models.py                 # Pydantic models (ConceptPlan, ConceptSet, etc.)
├── run_discovery.sh          # Shell runner
├── README.md                 # Documentation
└── PHASE2_COMPLETE.md        # Performance optimizations doc
```

**Core Capabilities:**
- ✅ ATHENA API integration (search, concept details, relationships)
- ✅ Concept set decomposition (exposure/outcome → clinical terms)
- ✅ BFS graph exploration (Standard → Non-standard mappings)
- ✅ Quality filtering (3-stage acceptance: relevance, clinical utility, feasibility)
- ✅ Batch processing with time budgets
- ✅ LRU caching (within-run optimization)

**What It Needs to Work:**

1. **Environment Variables:**
```bash
# .env
OPENAI_API_KEY=sk-...
MAX_CONCEPT_SETS=5           # Optional (default: 5)
MAX_QUERIES_PER_SET=8        # Optional (default: 8)
SEARCH_TOP_K=10              # Optional (default: 10)
PER_SET_TIME_LIMIT_SEC=60    # Optional (default: 60)
MAX_ACCEPTED_PER_SET=50      # Optional (default: 50)
```

2. **Dependencies:**
```toml
# pyproject.toml
[project]
dependencies = [
    "pydantic>=2.0",
    "pydantic-ai>=0.0.13",
    "httpx>=0.27",
    "openai>=1.0",
]
```

3. **Shared Utilities:**
```python
# Will need to create minimal replacements for:
from projects.shared.secrets import get_openai_key  # → os.getenv("OPENAI_API_KEY")
```

**What You'll Adapt:**
- Input: Change from `complete_clarification_output.json` → your `Problem` model
- Output: Map `ConceptSet` → your `exposure_concepts`/`outcome_concepts`

---

### 2. **qb (BigQuery SQL Generation)** - Stage 3

**What You're Getting:**
 /qb/
├── create_bigquery_sql.py    # Main SQL builder
├── tools.py                  # BigQuery validation, dry-run, OMOP discovery
├── models.py                 # Pydantic models (CohortSQLInput, ValidationResult)
├── run_query_builder.sh      # Shell runner
└── README.md                 # Documentation
```

**Core Capabilities:**
- ✅ BigQuery SQL generation (cohort definition from concept sets)
- ✅ Dry-run validation (cost estimation, syntax check)
- ✅ OMOP table discovery (automatically detect available CDM tables)
- ✅ Temporal logic (exposure precedes outcome within window)
- ✅ Cost estimates ($5/TB pricing)

**What It Needs to Work:**

1. **Environment Variables:**
```bash
# .env
BIGQUERY_PROJECT_ID=my-gcp-project
OMOP_DATASET_ID=my_omop_dataset
BIGQUERY_LOCATION=US           # Optional (default: US)
```

2. **Authentication:**
```bash
# Application Default Credentials (ADC)
gcloud auth application-default login
```

3. **Dependencies:**
```toml
[project]
dependencies = [
    "google-cloud-bigquery>=3.0",
    "pydantic>=2.0",
    "pydantic-ai>=0.0.13",
]
```

4. **Input Format:**
```python
# Expected input structure (from Stage 2)
{
    "concept_sets": [
        {
            "name": "diabetes_exposure",
            "domain": "Condition",
            "accepted_concepts": [
                {"concept_id": 201826, "concept_name": "Type 2 diabetes", ...}
            ]
        }
    ],
    "demographics": {...},
    "index_info": {...}
}
```

**What You'll Adapt:**
- Input: Map your `Hypothesis` → `CohortSQLInput` (exposure/outcome concept IDs)
- Output: Extract SQL + validation results → `PlausibilityCounts`

---

### 3. **`projects/stats/` (Analytics)** - Stage 4

**What You're Getting:**
```
projects/stats/
├── run_stats.py              # Main analytics runner
├── build_analytics_queries.py # Query builders (demographics, age buckets, etc.)
├── analytics_dashboard.py    # Gradio charts (Plotly)
└── README.md
```

**Core Capabilities:**
- ✅ Demographic breakdowns (gender, race, ethnicity)
- ✅ Age distribution (10-year buckets)
- ✅ Index date derivation (first ESRD occurrence)
- ✅ Plotly visualizations

**What It Needs to Work:**

1. **Dependencies:**
```toml
[project]
dependencies = [
    "google-cloud-bigquery>=3.0",
    "plotly>=5.0",
    "pandas>=2.0",
]
```

2. **Input:**
```python
# Expects:
# 1. Generated SQL (cohort query)
# 2. ESRD concept IDs (for index date logic)
```

**What You'll Adapt:**
- Input: Your `cohort_sql` from Stage 3
- Output: Use analytics queries to compute `n_exposed`, `n_outcome`, `n_temporal`

---

## 🔧 What You'll Need to Build (Glue Code)

### Minimal Replacements for `projects/shared/`

```python
# shared/secrets.py (SIMPLIFIED VERSION)
import os
from typing import Optional

def get_openai_key() -> str:
    """Get OpenAI API key from environment."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY not set in environment")
    return key

def get_bigquery_project() -> str:
    """Get BigQuery project ID."""
    project = os.getenv("BIGQUERY_PROJECT_ID")
    if not project:
        raise ValueError("BIGQUERY_PROJECT_ID not set")
    return project

def get_omop_dataset() -> str:
    """Get OMOP dataset ID."""
    dataset = os.getenv("OMOP_DATASET_ID")
    if not dataset:
        raise ValueError("OMOP_DATASET_ID not set")
    return dataset
```

---

## 🔌 Integration Adapters (What You'll Write)

### 1. **Concept Mapper Wrapper**

```python
# hypothesis_engine/omop/concept_mapper.py
from typing import List
from projects.cd.find_concepts import run_concept_discovery
from projects.cd.models import ConceptSet

class ConceptMapper:
    """Adapter for cohortgen concept discovery."""

    def map_exposure(self, exposure_text: str) -> List[int]:
        """Map exposure text to OMOP concept IDs."""
        # Fake a Stage 1 output for Stage 2 input
        stage1_output = {
            "clinical_summary": {
                "index_events": [exposure_text],
                "inclusion_criteria": [],
                "exclusion_criteria": [],
                "demographics": {}
            }
        }

        # Run Stage 2 concept discovery
        result = run_concept_discovery(stage1_output)

        # Extract concept IDs from first concept set
        if result["concept_sets"]:
            first_set = result["concept_sets"][0]
            return [c["concept_id"] for c in first_set["accepted_concepts"]]

        return []

    def map_outcome(self, outcome_text: str) -> List[int]:
        """Map outcome text to OMOP concept IDs."""
        # Same pattern as exposure
        stage1_output = {
            "clinical_summary": {
                "index_events": [outcome_text],
                "inclusion_criteria": [],
                "exclusion_criteria": [],
                "demographics": {}
            }
        }

        result = run_concept_discovery(stage1_output)

        if result["concept_sets"]:
            return [c["concept_id"] for c in result["concept_sets"][0]["accepted_concepts"]]

        return []
```

### 2. **OMOP Plausibility Checker**

```python
# hypothesis_engine/omop/plausibility.py
from typing import List, Dict, Any
from google.cloud import bigquery
from pydantic import BaseModel

class PlausibilityCounts(BaseModel):
    n_exposed: int
    n_outcome: int
    n_temporal: int  # Exposure precedes outcome
    sql: str
    params: Dict[str, Any]

class OMOPPlausibilityChecker:
    """BigQuery-based OMOP plausibility checks."""

    def __init__(self, project_id: str, dataset: str):
        self.client = bigquery.Client(project=project_id)
        self.project_id = project_id
        self.dataset = dataset

    def compute_counts(
        self,
        exposure_concepts: List[int],
        outcome_concepts: List[int],
        pre_outcome_days: int = 90,
        min_n: int = 100
    ) -> PlausibilityCounts:
        """
        Compute temporal OMOP counts.

        Queries:
        1. n_exposed: COUNT DISTINCT person_id with exposure
        2. n_outcome: COUNT DISTINCT person_id with outcome
        3. n_temporal: COUNT where exposure precedes outcome by ≤ pre_outcome_days
        """

        # Build temporal SQL
        sql = f"""
        WITH exposure AS (
            SELECT DISTINCT person_id, condition_start_date AS exposure_date
            FROM `{self.project_id}.{self.dataset}.condition_occurrence`
            WHERE condition_concept_id IN UNNEST(@exposure_concepts)
        ),
        outcome AS (
            SELECT DISTINCT person_id, condition_start_date AS outcome_date
            FROM `{self.project_id}.{self.dataset}.condition_occurrence`
            WHERE condition_concept_id IN UNNEST(@outcome_concepts)
        ),
        temporal AS (
            SELECT DISTINCT e.person_id
            FROM exposure e
            JOIN outcome o ON e.person_id = o.person_id
            WHERE e.exposure_date <= o.outcome_date
              AND DATE_DIFF(o.outcome_date, e.exposure_date, DAY) <= @pre_outcome_days
        )
        SELECT
            (SELECT COUNT(DISTINCT person_id) FROM exposure) AS n_exposed,
            (SELECT COUNT(DISTINCT person_id) FROM outcome) AS n_outcome,
            (SELECT COUNT(DISTINCT person_id) FROM temporal) AS n_temporal
        """

        # Run query
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("exposure_concepts", "INT64", exposure_concepts),
                bigquery.ArrayQueryParameter("outcome_concepts", "INT64", outcome_concepts),
                bigquery.ScalarQueryParameter("pre_outcome_days", "INT64", pre_outcome_days)
            ]
        )

        result = self.client.query(sql, job_config=job_config).result()
        row = next(result)

        return PlausibilityCounts(
            n_exposed=row.n_exposed,
            n_outcome=row.n_outcome,
            n_temporal=row.n_temporal,
            sql=sql,
            params={
                "exposure_concepts": exposure_concepts,
                "outcome_concepts": outcome_concepts,
                "pre_outcome_days": pre_outcome_days,
                "min_n": min_n
            }
        )

    def score_plausibility(self, counts: PlausibilityCounts) -> float:
        """
        Convert counts to [0, 1] plausibility score.

        Logic:
        - If n_temporal < min_n → 0.0 (insufficient data)
        - Otherwise: sigmoid-like function based on temporal fraction
        """
        min_n = counts.params["min_n"]

        if counts.n_temporal < min_n:
            return 0.0

        # Compute temporal fraction (exposure → outcome rate)
        if counts.n_exposed == 0:
            return 0.0

        temporal_fraction = counts.n_temporal / counts.n_exposed

        # Map to [0, 1] with sigmoid
        # High temporal fraction → high plausibility
        import math
        return 1 / (1 + math.exp(-10 * (temporal_fraction - 0.5)))
```

---

## 📋 What's Left to Build (New Components)

### 1. **Literature Retrieval** (3 weeks)
- Vector index (FAISS/Pinecone)
- PubMed XML parser
- Embedding service
- RAG query builder

### 2. **Generator Agent** (2 weeks)
- Pydantic AI agent (similar to `projects/clar/hitl_clarification_working.py`)
- Hypothesis generation logic
- Diversity sampling

### 3. **Validator Agent** (2 weeks)
- Factuality scoring (claim → evidence)
- Novelty scoring (embedding distance)
- EIG proxy (peer pruning)
- Evidence Card builder

### 4. **FastAPI Gateway** (2 weeks)
- `/v1/run`, `/v1/generate`, `/v1/validate` endpoints
- Provenance store (Postgres)
- Background task queue

### 5. **React UI** (1 week)
- Problem form
- Hypothesis grid
- Evidence Card viewer

---

## 🎯 Summary: What You're Importing

| Folder | Lines of Code | What It Does | Adaptation Effort |
|--------|--------------|--------------|-------------------|
| **`projects/cd/`** | ~1,200 | ATHENA search + concept discovery | **Low** (1-2 days) |
| **`projects/qb/`** | ~800 | BigQuery SQL + validation | **Low** (1 day) |
| **`projects/stats/`** | ~600 | Analytics queries | **Low** (1 day) |
| **`projects/shared/`** | ~100 | Secrets management | **Minimal** (replace with env vars) |

**Total Imported:** ~2,700 lines of **production-ready OMOP code**

---

## ✅ Setup Checklist (Post-Import)

### Week 1: Integration
- [ ] Copy folders to new repo as git submodules:
  ```bash
  git submodule add https://github.com/you/cohortgen.git vendor/cohortgen
  ```
- [ ] Create `shared/secrets.py` replacement (env vars only)
- [ ] Update imports:
  ```python
  from vendor.cohortgen.projects.cd.find_concepts import run_concept_discovery
  from vendor.cohortgen.projects.qb.create_bigquery_sql import generate_sql
  ```
- [ ] Write `ConceptMapper` adapter
- [ ] Write `OMOPPlausibilityChecker` adapter
- [ ] Add tests for adapters

### Week 2: Validation
- [ ] Test concept mapping with real ATHENA
- [ ] Test BigQuery plausibility with real OMOP dataset
- [ ] Verify cost estimates ($5/TB)
- [ ] Document adapter usage

---

## 🚨 Key Dependencies

```toml
# pyproject.toml
[project]
dependencies = [
    # Existing cohortgen deps
    "pydantic>=2.0",
    "pydantic-ai>=0.0.13",
    "httpx>=0.27",
    "openai>=1.0",
    "google-cloud-bigquery>=3.0",
    "plotly>=5.0",
    "pandas>=2.0",

    # Your new components
    "fastapi>=0.100",
    "langchain>=0.1",  # For RAG
    "faiss-cpu>=1.7",  # For vector search
]
```

---

## 🎉 Final Tally

**What You Get:**
- ✅ OMOP concept mapping (Stage 2)
- ✅ BigQuery SQL generation + validation (Stage 3)
- ✅ Analytics queries (Stage 4)
- ✅ ~2,700 lines of tested code

**What You Build:**
- 🔨 Literature RAG (3 weeks)
- 🔨 Generator/Validator agents (4 weeks)
- 🔨 FastAPI API (2 weeks)
- 🔨 React UI (1 week)
- 🔨 Glue adapters (1 week)

**Total Timeline: 12-14 weeks to MVP** (vs 10-12 for full fork)

**Risk Assessment:** ✅ Lower (cleaner separation, but 2 weeks slower)
