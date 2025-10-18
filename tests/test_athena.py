"""Tests for ATHENA API client."""

from unittest.mock import Mock, patch

import pytest
from omop_mcp.models import OMOPConcept
from omop_mcp.tools import AthenaAPIClient, discover_concepts


class TestAthenaAPIClient:
    """Tests for AthenaAPIClient."""

    @pytest.fixture
    def mock_athena_concept(self):
        """Create a mock athena-client Concept object."""
        mock_concept = Mock()
        mock_concept.id = 201826
        mock_concept.name = "Type 2 diabetes mellitus"
        mock_concept.domain = "Condition"
        mock_concept.vocabulary = "SNOMED"
        mock_concept.className = "Clinical Finding"
        mock_concept.standardConcept = Mock(name="STANDARD")
        mock_concept.code = "44054006"
        mock_concept.invalidReason = None
        mock_concept.score = 95.5
        return mock_concept

    def test_client_initialization(self):
        """Test AthenaAPIClient initialization."""
        client = AthenaAPIClient()
        assert client is not None
        assert client.base_url is not None

    @patch("omop_mcp.tools.athena.AthenaClient")
    def test_search_concepts(self, mock_athena_client_class, mock_athena_concept):
        """Test search_concepts method."""
        # Setup mock
        mock_client_instance = Mock()
        mock_search_result = Mock()
        mock_search_result.__iter__ = Mock(return_value=iter([mock_athena_concept]))
        mock_client_instance.search.return_value = mock_search_result
        mock_athena_client_class.return_value = mock_client_instance

        # Test search
        client = AthenaAPIClient()
        results = client.search_concepts("diabetes", limit=10)

        assert len(results) > 0
        assert isinstance(results[0], OMOPConcept)
        mock_client_instance.search.assert_called_once()

    @patch("omop_mcp.tools.athena.AthenaClient")
    @patch("omop_mcp.tools.athena.ConceptType")
    def test_search_concepts_with_filters(
        self, mock_concept_type, mock_athena_client_class, mock_athena_concept
    ):
        """Test search_concepts with domain and vocabulary filters."""
        # Setup ConceptType enum mock
        mock_concept_type.STANDARD = "STANDARD"

        # Setup mock with matching filters
        mock_concept = Mock()
        mock_concept.id = 201826
        mock_concept.name = "Type 2 diabetes mellitus"
        mock_concept.domain = "Condition"  # Matches filter
        mock_concept.vocabulary = "SNOMED"  # Matches filter
        mock_concept.className = "Clinical Finding"
        mock_concept.standardConcept = "STANDARD"  # Matches standard_only=True
        mock_concept.code = "44054006"
        mock_concept.invalidReason = None
        mock_concept.score = 95.5

        mock_client_instance = Mock()
        mock_search_result = Mock()
        mock_search_result.__iter__ = Mock(return_value=iter([mock_concept]))
        mock_client_instance.search.return_value = mock_search_result
        mock_athena_client_class.return_value = mock_client_instance

        # Test search with filters
        client = AthenaAPIClient()
        results = client.search_concepts(
            "diabetes", domain="Condition", vocabulary="SNOMED", standard_only=True, limit=5
        )

        assert len(results) > 0
        # Verify concept matches filters
        concept = results[0]
        assert concept.domain_id == "Condition"
        assert concept.vocabulary_id == "SNOMED"
        assert concept.is_standard() is True

    @patch("omop_mcp.tools.athena.AthenaClient")
    def test_get_concept_by_id(self, mock_athena_client_class, mock_athena_concept):
        """Test get_concept_by_id method."""
        # Setup mock
        mock_client_instance = Mock()
        mock_client_instance.details.return_value = mock_athena_concept
        mock_athena_client_class.return_value = mock_client_instance

        # Test get by ID
        client = AthenaAPIClient()
        concept = client.get_concept_by_id(201826)

        assert concept is not None
        assert isinstance(concept, OMOPConcept)
        assert concept.concept_id == 201826
        mock_client_instance.details.assert_called_once_with(201826)

    @patch("omop_mcp.tools.athena.AthenaClient")
    def test_get_concept_relationships(self, mock_athena_client_class):
        """Test get_concept_relationships method."""
        # Setup mock relationship
        mock_rel = Mock()
        mock_rel.id = "123"
        mock_rel.name = "Maps to"
        mock_rel.targetId = 4046213

        mock_client_instance = Mock()
        mock_client_instance.relationships.return_value = [mock_rel]
        mock_athena_client_class.return_value = mock_client_instance

        # Test relationships
        client = AthenaAPIClient()
        relationships = client.get_concept_relationships(201826)

        assert len(relationships) > 0
        assert relationships[0].concept_id_1 == 201826
        assert relationships[0].concept_id_2 == 4046213
        assert relationships[0].relationship_name == "Maps to"


@patch("omop_mcp.tools.athena.AthenaClient")
@patch("omop_mcp.tools.athena.ConceptType")
def test_discover_concepts(mock_concept_type, mock_athena_client_class):
    """Test discover_concepts helper function."""
    # Setup ConceptType enum mock
    mock_concept_type.STANDARD = "STANDARD"

    # Setup mock
    mock_concept = Mock()
    mock_concept.id = 201826
    mock_concept.name = "Type 2 diabetes mellitus"
    mock_concept.domain = "Condition"
    mock_concept.vocabulary = "SNOMED"
    mock_concept.className = "Clinical Finding"
    mock_concept.standardConcept = "STANDARD"
    mock_concept.code = "44054006"
    mock_concept.invalidReason = None
    mock_concept.score = 95.5

    mock_client_instance = Mock()
    mock_search_result = Mock()
    mock_search_result.__iter__ = Mock(return_value=iter([mock_concept]))
    mock_client_instance.search.return_value = mock_search_result
    mock_athena_client_class.return_value = mock_client_instance

    # Test discover
    result = discover_concepts("diabetes", domain="Condition", limit=10)

    assert result.query == "diabetes"
    assert len(result.concepts) > 0
    assert len(result.standard_concepts) > 0
    assert 201826 in result.concept_ids
