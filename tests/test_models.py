"""Tests for OMOP MCP Pydantic models."""

from datetime import datetime

import pytest
from omop_mcp.models import (
    CohortSQLRequest,
    ConceptDiscoveryResult,
    ConceptRelationship,
    OMOPConcept,
    OMOPDomain,
    QueryOMOPRequest,
)


class TestOMOPConcept:
    """Tests for OMOPConcept model."""

    def test_concept_creation(self):
        """Test creating an OMOP concept."""
        concept = OMOPConcept(
            id=12345,
            name="Type 2 diabetes mellitus",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code="44054006",
            invalidReason=None,
        )

        assert concept.concept_id == 12345
        assert concept.concept_name == "Type 2 diabetes mellitus"
        assert concept.domain_id == "Condition"
        assert concept.vocabulary_id == "SNOMED"
        assert concept.concept_class_id == "Clinical Finding"
        assert concept.standard_concept == "S"

    def test_concept_is_standard(self):
        """Test is_standard() method."""
        standard_concept = OMOPConcept(
            id=1,
            name="Test",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code="123",
            invalidReason=None,
        )

        non_standard_concept = OMOPConcept(
            id=2,
            name="Test",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept=None,
            code="456",
            invalidReason=None,
        )

        assert standard_concept.is_standard() is True
        assert non_standard_concept.is_standard() is False

    def test_concept_is_valid(self):
        """Test is_valid() method."""
        valid_concept = OMOPConcept(
            id=1,
            name="Test",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code="123",
            invalidReason=None,
        )

        invalid_concept = OMOPConcept(
            id=2,
            name="Test",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code="456",
            invalidReason="D",  # Deleted
        )

        assert valid_concept.is_valid() is True
        assert invalid_concept.is_valid() is False

    def test_concept_with_aliases(self):
        """Test that field aliases work for initialization (athena-client compatibility)."""
        # Test with camelCase (athena-client format) - should work for initialization
        concept = OMOPConcept(
            id=12345,
            name="Diabetes",
            domain="Condition",
            vocabulary="SNOMED",
            className="Clinical Finding",
            standardConcept="S",
            code="44054006",
        )

        # Should be accessible via canonical snake_case names
        assert concept.concept_id == 12345
        assert concept.concept_name == "Diabetes"
        assert concept.domain_id == "Condition"


class TestConceptRelationship:
    """Tests for ConceptRelationship model."""

    def test_relationship_creation(self):
        """Test creating a concept relationship."""
        rel = ConceptRelationship(
            concept_id_1=12345,
            concept_id_2=67890,
            relationship_id="123",
            relationship_name="Maps to",
        )

        assert rel.concept_id_1 == 12345
        assert rel.concept_id_2 == 67890
        assert rel.relationship_id == "123"
        assert rel.relationship_name == "Maps to"


class TestConceptDiscoveryResult:
    """Tests for ConceptDiscoveryResult model."""

    def test_discovery_result_creation(self):
        """Test creating a discovery result."""
        concepts = [
            OMOPConcept(
                id=1,
                name="Test 1",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept="S",
                code="123",
            ),
            OMOPConcept(
                id=2,
                name="Test 2",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept=None,
                code="456",
            ),
        ]

        result = ConceptDiscoveryResult(
            query="diabetes",
            concepts=concepts,
        )

        assert result.query == "diabetes"
        assert len(result.concepts) == 2
        assert isinstance(result.timestamp, datetime)

    def test_discovery_result_concept_ids_property(self):
        """Test concept_ids property."""
        concepts = [
            OMOPConcept(
                id=12345,
                name="Test 1",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept="S",
                code="123",
            ),
            OMOPConcept(
                id=67890,
                name="Test 2",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept="S",
                code="456",
            ),
        ]

        result = ConceptDiscoveryResult(
            query="test",
            concepts=concepts,
        )

        assert result.concept_ids == [12345, 67890]

    def test_discovery_result_standard_concepts_property(self):
        """Test standard_concepts property."""
        concepts = [
            OMOPConcept(
                id=1,
                name="Standard",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept="S",
                code="123",
            ),
            OMOPConcept(
                id=2,
                name="Non-standard",
                domain="Condition",
                vocabulary="SNOMED",
                className="Clinical Finding",
                standardConcept=None,
                code="456",
            ),
        ]

        result = ConceptDiscoveryResult(
            query="test",
            concepts=concepts,
        )

        standard = result.standard_concepts
        assert len(standard) == 1
        assert standard[0].concept_id == 1


class TestCohortSQLRequest:
    """Tests for CohortSQLRequest model."""

    def test_cohort_sql_request_creation(self):
        """Test creating a cohort SQL request."""
        request = CohortSQLRequest(
            exposure_concept_ids=[201826, 4046213],
            outcome_concept_ids=[320128],
            pre_outcome_days=90,
            validate_sql=True,
        )

        assert len(request.exposure_concept_ids) == 2
        assert len(request.outcome_concept_ids) == 1
        assert request.pre_outcome_days == 90
        assert request.validate_sql is True

    def test_cohort_sql_request_with_project(self):
        """Test cohort SQL request with project and dataset."""
        request = CohortSQLRequest(
            exposure_concept_ids=[201826],
            outcome_concept_ids=[320128],
            project_id="my-project",
            dataset_id="omop_cdm",
        )

        assert request.project_id == "my-project"
        assert request.dataset_id == "omop_cdm"


class TestQueryOMOPRequest:
    """Tests for QueryOMOPRequest model."""

    def test_query_omop_request_creation(self):
        """Test creating a query OMOP request."""
        request = QueryOMOPRequest(
            concept_ids=[201826, 4046213],
            query_type="count",
            backend="bigquery",
        )

        assert len(request.concept_ids) == 2
        assert request.query_type == "count"
        assert request.backend == "bigquery"

    def test_query_omop_request_invalid_type(self):
        """Test that invalid query type raises error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="query_type must be"):
            QueryOMOPRequest(
                concept_ids=[201826],
                query_type="invalid_type",
                backend="bigquery",
            )


class TestOMOPDomain:
    """Tests for OMOPDomain enum."""

    def test_domain_values(self):
        """Test OMOP domain enum values."""
        assert OMOPDomain.CONDITION == "Condition"
        assert OMOPDomain.DRUG == "Drug"
        assert OMOPDomain.PROCEDURE == "Procedure"
        assert OMOPDomain.MEASUREMENT == "Measurement"
        assert OMOPDomain.OBSERVATION == "Observation"
        assert OMOPDomain.DEVICE == "Device"
