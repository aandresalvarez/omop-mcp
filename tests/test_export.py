"""Tests for export tools."""

import gzip
import json
from datetime import datetime
from pathlib import Path

import pytest
from omop_mcp.models import (
    CohortSQLResult,
    ConceptDiscoveryResult,
    OMOPConcept,
    SQLValidationResult,
)
from omop_mcp.tools.export import (
    ExportError,
    export_cohort_definition,
    export_concept_set,
    export_query_results,
    export_sql_query,
)


@pytest.fixture
def sample_concepts():
    """Sample OMOP concepts for testing."""
    return [
        OMOPConcept(
            id=1503297,
            name="Metformin",
            domain="Drug",
            vocabulary="RxNorm",
            className="Clinical Drug",
            standardConcept="S",
            code="6809",
            invalidReason=None,
        ),
        OMOPConcept(
            id=201826,
            name="Type 2 diabetes mellitus",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code="44054006",
            invalidReason=None,
        ),
        OMOPConcept(
            id=443530,
            name="Myocardial infarction",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code="22298006",
            invalidReason=None,
        ),
    ]


@pytest.fixture
def concept_discovery_result(sample_concepts):
    """Sample concept discovery result."""
    return ConceptDiscoveryResult(
        query="diabetes",
        concepts=sample_concepts[:2],
        relationships={},
        search_metadata={"source": "test"},
    )


@pytest.fixture
def cohort_sql_result():
    """Sample cohort SQL result."""
    return CohortSQLResult(
        sql="SELECT * FROM patient",
        backend="bigquery",
        dialect="bigquery",
        concept_counts={"exposure": 1, "outcome": 1},
        timestamp=datetime(2024, 1, 15, 10, 30),
        validation=SQLValidationResult(
            valid=True,
            estimated_bytes=1000000,
            estimated_cost_usd=0.005,
        ),
    )


class TestExportConceptSet:
    """Tests for export_concept_set function."""

    def test_export_concepts_json(self, sample_concepts, tmp_path):
        """Test exporting concepts to JSON format."""
        output_file = tmp_path / "concepts.json"
        result = export_concept_set(sample_concepts, output_file, format="json")

        assert result["path"] == str(output_file)
        assert result["format"] == "json"
        assert result["concept_count"] == 3
        assert result["compressed"] is False

        # Verify file contents
        with open(output_file) as f:
            data = json.load(f)
            assert "concepts" in data
            assert len(data["concepts"]) == 3
            assert "metadata" in data
            assert data["metadata"]["concept_count"] == 3
            assert data["metadata"]["standard_count"] == 3

    def test_export_concepts_csv(self, sample_concepts, tmp_path):
        """Test exporting concepts to CSV format."""
        output_file = tmp_path / "concepts.csv"
        result = export_concept_set(sample_concepts, output_file, format="csv")

        assert result["path"] == str(output_file)
        assert result["format"] == "csv"

        # Verify file contents
        content = output_file.read_text()
        assert "# Exported:" in content
        assert "# Concept count: 3" in content
        assert "concept_id,concept_name" in content
        assert "1503297,Metformin" in content

    def test_export_concepts_from_discovery_result(self, concept_discovery_result, tmp_path):
        """Test exporting ConceptDiscoveryResult."""
        output_file = tmp_path / "concepts.json"
        result = export_concept_set(concept_discovery_result, output_file)

        assert result["concept_count"] == 2

        with open(output_file) as f:
            data = json.load(f)
            assert data["metadata"]["query"]["query"] == "diabetes"

    def test_export_concepts_compressed(self, sample_concepts, tmp_path):
        """Test exporting concepts with gzip compression."""
        output_file = tmp_path / "concepts.json"
        result = export_concept_set(sample_concepts, output_file, compress=True)

        assert result["compressed"] is True
        assert result["path"].endswith(".gz")

        # Verify compressed file
        with gzip.open(result["path"], "rt") as f:
            data = json.load(f)
            assert len(data["concepts"]) == 3

    def test_export_concepts_no_metadata(self, sample_concepts, tmp_path):
        """Test exporting without metadata."""
        output_file = tmp_path / "concepts.json"
        export_concept_set(sample_concepts, output_file, include_metadata=False)

        with open(output_file) as f:
            data = json.load(f)
            assert "metadata" not in data

    def test_export_concepts_invalid_format(self, sample_concepts, tmp_path):
        """Test exporting with invalid format raises error."""
        with pytest.raises(ValueError, match="Invalid format"):
            export_concept_set(sample_concepts, tmp_path / "test", format="xml")

    def test_export_concepts_adds_extension(self, sample_concepts, tmp_path):
        """Test that missing file extension is added."""
        output_file = tmp_path / "concepts"
        result = export_concept_set(sample_concepts, output_file, format="json")

        assert result["path"].endswith(".json")
        assert Path(result["path"]).exists()


class TestExportSQLQuery:
    """Tests for export_sql_query function."""

    def test_export_sql_string(self, tmp_path):
        """Test exporting SQL string."""
        sql = "SELECT person_id, birth_datetime FROM person WHERE person_id < 1000"
        output_file = tmp_path / "query.sql"

        result = export_sql_query(sql, output_file)

        assert result["path"] == str(output_file)
        assert result["sql_length"] > 0  # SQL is formatted, length changes

        content = output_file.read_text()
        assert "OMOP CDM SQL Query" in content
        assert "SELECT person_id" in content
        assert "FROM person" in content

    def test_export_sql_result(self, cohort_sql_result, tmp_path):
        """Test exporting CohortSQLResult."""
        output_file = tmp_path / "cohort.sql"

        result = export_sql_query(cohort_sql_result, output_file)

        assert result["path"] == str(output_file)

        content = output_file.read_text()
        assert "Backend: bigquery" in content
        assert "Dialect: bigquery" in content
        assert "Valid: True" in content
        assert "SELECT *" in content
        assert "FROM patient" in content

    def test_export_sql_no_metadata(self, tmp_path):
        """Test exporting SQL without metadata."""
        sql = "SELECT COUNT(*) FROM person"
        output_file = tmp_path / "query.sql"

        export_sql_query(sql, output_file, include_metadata=False)

        content = output_file.read_text()
        assert "OMOP CDM SQL Query" not in content
        assert "SELECT COUNT(*)" in content
        assert "FROM person" in content

    def test_export_sql_adds_extension(self, tmp_path):
        """Test that .sql extension is added."""
        sql = "SELECT * FROM person"
        output_file = tmp_path / "query"

        result = export_sql_query(sql, output_file)

        assert result["path"].endswith(".sql")


class TestExportQueryResults:
    """Tests for export_query_results function."""

    def test_export_results_csv(self, tmp_path):
        """Test exporting query results to CSV."""
        results = [
            {"person_id": 1, "age": 45, "gender": "M"},
            {"person_id": 2, "age": 52, "gender": "F"},
            {"person_id": 3, "age": 38, "gender": "M"},
        ]
        output_file = tmp_path / "results.csv"

        result = export_query_results(results, output_file, format="csv")

        assert result["path"] == str(output_file)
        assert result["format"] == "csv"
        assert result["row_count"] == 3

        content = output_file.read_text()
        assert "person_id,age,gender" in content
        assert "1,45,M" in content

    def test_export_results_json(self, tmp_path):
        """Test exporting query results to JSON."""
        results = [
            {"person_id": 1, "count": 5},
            {"person_id": 2, "count": 3},
        ]
        output_file = tmp_path / "results.json"

        result = export_query_results(results, output_file, format="json")

        assert result["format"] == "json"

        with open(output_file) as f:
            data = json.load(f)
            assert "results" in data
            assert len(data["results"]) == 2
            assert "metadata" in data

    def test_export_results_jsonl(self, tmp_path):
        """Test exporting query results to JSONL."""
        results = [
            {"person_id": 1, "value": "a"},
            {"person_id": 2, "value": "b"},
        ]
        output_file = tmp_path / "results.jsonl"

        result = export_query_results(results, output_file, format="jsonl")

        assert result["format"] == "jsonl"

        lines = output_file.read_text().strip().split("\n")
        assert len(lines) == 3  # metadata + 2 results

        # First line is metadata
        metadata = json.loads(lines[0])
        assert "_metadata" in metadata

    def test_export_results_compressed(self, tmp_path):
        """Test exporting query results with compression."""
        results = [{"id": i} for i in range(10)]
        output_file = tmp_path / "results.json"

        result = export_query_results(results, output_file, format="json", compress=True)

        assert result["compressed"] is True
        assert result["path"].endswith(".gz")

        with gzip.open(result["path"], "rt") as f:
            data = json.load(f)
            assert len(data["results"]) == 10

    def test_export_results_empty_list(self, tmp_path):
        """Test exporting empty results raises error."""
        results = []
        output_file = tmp_path / "results.csv"

        with pytest.raises(ExportError, match="No results to export"):
            export_query_results(results, output_file, format="csv")

    def test_export_results_invalid_format(self, tmp_path):
        """Test invalid format raises error."""
        results = [{"id": 1}]

        with pytest.raises(ValueError, match="Invalid format"):
            export_query_results(results, tmp_path / "test", format="parquet")


class TestExportCohortDefinition:
    """Tests for export_cohort_definition function."""

    def test_export_cohort_from_result(self, cohort_sql_result, tmp_path):
        """Test exporting cohort definition from CohortSQLResult."""
        output_file = tmp_path / "cohort_def.json"

        result = export_cohort_definition(cohort_sql_result, output_file)

        assert result["path"] == str(output_file)

        with open(output_file) as f:
            data = json.load(f)
            assert "cohort_definition" in data
            assert "export_metadata" in data
            assert data["cohort_definition"]["backend"] == "bigquery"
            assert "sql" in data["cohort_definition"]
            assert "validation" in data["cohort_definition"]

    def test_export_cohort_without_sql(self, cohort_sql_result, tmp_path):
        """Test exporting cohort definition without SQL."""
        output_file = tmp_path / "cohort_def.json"

        export_cohort_definition(cohort_sql_result, output_file, include_sql=False)

        with open(output_file) as f:
            data = json.load(f)
            assert "sql" not in data["cohort_definition"]

    def test_export_cohort_from_dict(self, tmp_path):
        """Test exporting cohort definition from dictionary."""
        definition = {
            "name": "Test Cohort",
            "description": "A test cohort",
            "criteria": {"age": ">18"},
        }
        output_file = tmp_path / "cohort_def.json"

        export_cohort_definition(definition, output_file)

        with open(output_file) as f:
            data = json.load(f)
            assert data["cohort_definition"]["name"] == "Test Cohort"
            assert "export_metadata" in data

    def test_export_cohort_adds_extension(self, tmp_path):
        """Test that .json extension is added."""
        definition = {"test": "data"}
        output_file = tmp_path / "cohort"

        result = export_cohort_definition(definition, output_file)

        assert result["path"].endswith(".json")


class TestExportErrorHandling:
    """Tests for export error handling."""

    def test_export_to_nonexistent_directory(self, sample_concepts, tmp_path):
        """Test that parent directories are created automatically."""
        output_file = tmp_path / "subdir1" / "subdir2" / "concepts.json"

        result = export_concept_set(sample_concepts, output_file)

        assert Path(result["path"]).exists()
        assert Path(result["path"]).parent.exists()

    def test_export_with_permission_error(self, sample_concepts):
        """Test handling of permission errors (if possible)."""
        # This test would require specific OS setup to test permission errors
        # Skipping for now as it's OS-dependent
        pass
