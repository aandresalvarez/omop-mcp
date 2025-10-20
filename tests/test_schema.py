"""
Tests for schema introspection tools.
"""

from unittest.mock import AsyncMock, patch

import pytest
from omop_mcp.tools.schema import (
    OMOP_COLUMN_DESCRIPTIONS,
    OMOP_TABLE_DESCRIPTIONS,
    get_all_tables_schema,
    get_omop_cdm_info,
    get_table_schema,
    search_columns,
)


class TestGetTableSchema:
    """Test get_table_schema function."""

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.schema.get_backend")
    async def test_get_table_schema_success(self, mock_get_backend):
        """Test successful table schema retrieval."""
        # Setup mock backend
        mock_backend = AsyncMock()
        mock_backend.execute_query.return_value = [
            {
                "column_name": "person_id",
                "data_type": "INTEGER",
                "is_nullable": "NO",
                "column_default": None,
                "ordinal_position": 1,
            },
            {
                "column_name": "gender_concept_id",
                "data_type": "INTEGER",
                "is_nullable": "YES",
                "column_default": None,
                "ordinal_position": 2,
            },
        ]
        mock_get_backend.return_value = mock_backend

        result = await get_table_schema("person", "bigquery")

        assert result["table_name"] == "person"
        assert result["is_omop_standard"] is True
        assert result["column_count"] == 2
        assert result["backend"] == "bigquery"

        # Check columns
        columns = result["columns"]
        assert len(columns) == 2

        person_id_col = columns[0]
        assert person_id_col["name"] == "person_id"
        assert person_id_col["type"] == "INTEGER"
        assert person_id_col["nullable"] is False
        assert person_id_col["position"] == 1
        assert person_id_col["is_omop_standard"] is True
        assert "Unique identifier for each person" in person_id_col["description"]

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.schema.get_backend")
    async def test_get_table_schema_with_error(self, mock_get_backend):
        """Test table schema retrieval with backend error."""
        # Setup mock backend that raises error
        mock_backend = AsyncMock()
        mock_backend.execute_query.side_effect = Exception("Database error")
        mock_get_backend.return_value = mock_backend

        with pytest.raises(Exception, match="Database error"):
            await get_table_schema("person", "bigquery")

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.schema.get_backend")
    async def test_get_non_omop_table(self, mock_get_backend):
        """Test schema retrieval for non-OMOP table."""
        mock_backend = AsyncMock()
        mock_backend.execute_query.return_value = [
            {
                "column_name": "custom_id",
                "data_type": "VARCHAR",
                "is_nullable": "NO",
                "column_default": None,
                "ordinal_position": 1,
            }
        ]
        mock_get_backend.return_value = mock_backend

        result = await get_table_schema("custom_table", "bigquery")

        assert result["table_name"] == "custom_table"
        assert result["is_omop_standard"] is False
        assert result["description"] == ""  # No OMOP description

        # Check column
        column = result["columns"][0]
        assert column["name"] == "custom_id"
        assert column["is_omop_standard"] is False
        assert column["description"] == ""  # No OMOP description


class TestGetAllTablesSchema:
    """Test get_all_tables_schema function."""

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.schema.get_backend")
    @patch("omop_mcp.tools.schema.get_table_schema")
    async def test_get_all_tables_schema_success(self, mock_get_table_schema, mock_get_backend):
        """Test successful retrieval of all tables schema."""
        # Setup mock backend for table list
        mock_backend = AsyncMock()
        mock_backend.execute_query.return_value = [
            {"table_name": "person", "table_type": "BASE TABLE", "table_schema": "main"},
            {
                "table_name": "condition_occurrence",
                "table_type": "BASE TABLE",
                "table_schema": "main",
            },
        ]
        mock_get_backend.return_value = mock_backend

        # Setup mock for individual table schemas
        mock_get_table_schema.side_effect = [
            {
                "table_name": "person",
                "description": "Patient demographics",
                "is_omop_standard": True,
                "columns": [],
                "column_count": 15,
                "backend": "bigquery",
            },
            {
                "table_name": "condition_occurrence",
                "description": "Medical conditions",
                "is_omop_standard": True,
                "columns": [],
                "column_count": 15,
                "backend": "bigquery",
            },
        ]

        result = await get_all_tables_schema("bigquery", include_non_omop=False)

        assert result["total_tables"] == 2
        assert result["omop_tables"] == 2
        assert result["backend"] == "bigquery"
        assert result["include_non_omop"] is False

        tables = result["tables"]
        assert "person" in tables
        assert "condition_occurrence" in tables
        assert tables["person"]["is_omop_standard"] is True

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.schema.get_backend")
    @patch("omop_mcp.tools.schema.get_table_schema")
    async def test_get_all_tables_with_errors(self, mock_get_table_schema, mock_get_backend):
        """Test handling of errors in individual table schema retrieval."""
        # Setup mock backend
        mock_backend = AsyncMock()
        mock_backend.execute_query.return_value = [
            {"table_name": "person", "table_type": "BASE TABLE", "table_schema": "main"},
            {
                "table_name": "condition_occurrence",
                "table_type": "BASE TABLE",
                "table_schema": "main",
            },
        ]
        mock_get_backend.return_value = mock_backend

        # Setup mock for table schemas - one succeeds, one fails
        def mock_table_schema(table_name, backend):
            if table_name == "person":
                return {
                    "table_name": "person",
                    "description": "Patient demographics",
                    "is_omop_standard": True,
                    "columns": [],
                    "column_count": 15,
                    "backend": "bigquery",
                }
            else:
                raise Exception("Table access denied")

        mock_get_table_schema.side_effect = mock_table_schema

        result = await get_all_tables_schema("bigquery", include_non_omop=False)

        assert result["total_tables"] == 2
        assert "person" in result["tables"]
        assert "condition_occurrence" in result["tables"]

        # Check that error table has error info
        error_table = result["tables"]["condition_occurrence"]
        assert "error" in error_table
        assert error_table["column_count"] == 0


class TestSearchColumns:
    """Test search_columns function."""

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.schema.get_backend")
    async def test_search_columns_success(self, mock_get_backend):
        """Test successful column search."""
        mock_backend = AsyncMock()
        mock_backend.execute_query.return_value = [
            {
                "table_name": "person",
                "column_name": "person_id",
                "data_type": "INTEGER",
                "is_nullable": "NO",
                "ordinal_position": 1,
            },
            {
                "table_name": "condition_occurrence",
                "column_name": "person_id",
                "data_type": "INTEGER",
                "is_nullable": "NO",
                "ordinal_position": 2,
            },
        ]
        mock_get_backend.return_value = mock_backend

        result = await search_columns("person_id", "bigquery")

        assert result["pattern"] == "person_id"
        assert result["table_pattern"] is None
        assert result["total_matches"] == 2
        assert result["backend"] == "bigquery"

        columns = result["columns"]
        assert len(columns) == 2

        # Check first column
        col1 = columns[0]
        assert col1["table_name"] == "person"
        assert col1["column_name"] == "person_id"
        assert col1["data_type"] == "INTEGER"
        assert col1["is_omop_standard"] is True
        assert "Unique identifier for each person" in col1["description"]

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.schema.get_backend")
    async def test_search_columns_with_table_pattern(self, mock_get_backend):
        """Test column search with table pattern filter."""
        mock_backend = AsyncMock()
        mock_backend.execute_query.return_value = [
            {
                "table_name": "person",
                "column_name": "person_id",
                "data_type": "INTEGER",
                "is_nullable": "NO",
                "ordinal_position": 1,
            }
        ]
        mock_get_backend.return_value = mock_backend

        result = await search_columns("person_id", "bigquery", table_pattern="person")

        assert result["pattern"] == "person_id"
        assert result["table_pattern"] == "person"
        assert result["total_matches"] == 1

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.schema.get_backend")
    async def test_search_columns_no_matches(self, mock_get_backend):
        """Test column search with no matches."""
        mock_backend = AsyncMock()
        mock_backend.execute_query.return_value = []
        mock_get_backend.return_value = mock_backend

        result = await search_columns("nonexistent_column", "bigquery")

        assert result["total_matches"] == 0
        assert result["columns"] == []


class TestOMOPCDMInfo:
    """Test get_omop_cdm_info function."""

    def test_get_omop_cdm_info(self):
        """Test OMOP CDM info retrieval."""
        info = get_omop_cdm_info()

        assert info["version"] == "5.4"
        assert info["description"] == "OMOP Common Data Model v5.4"

        # Check table categories
        tables = info["tables"]
        assert "core" in tables
        assert "vocabulary" in tables
        assert "reference" in tables

        # Check core tables
        core_tables = tables["core"]
        assert "person" in core_tables
        assert "condition_occurrence" in core_tables
        assert "drug_exposure" in core_tables

        # Check domains
        domains = info["domains"]
        assert "Condition" in domains
        assert "Drug" in domains
        assert "Procedure" in domains

        # Check vocabularies
        vocabularies = info["vocabularies"]
        assert "SNOMED" in vocabularies
        assert "RxNorm" in vocabularies
        assert "LOINC" in vocabularies

        # Check descriptions
        assert "table_descriptions" in info
        assert "column_descriptions" in info


class TestOMOPDescriptions:
    """Test OMOP table and column descriptions."""

    def test_omop_table_descriptions(self):
        """Test OMOP table descriptions are available."""
        assert "person" in OMOP_TABLE_DESCRIPTIONS
        assert "condition_occurrence" in OMOP_TABLE_DESCRIPTIONS
        assert "drug_exposure" in OMOP_TABLE_DESCRIPTIONS

        # Check descriptions are meaningful
        person_desc = OMOP_TABLE_DESCRIPTIONS["person"]
        assert "demographics" in person_desc.lower()

        condition_desc = OMOP_TABLE_DESCRIPTIONS["condition_occurrence"]
        assert "condition" in condition_desc.lower()

    def test_omop_column_descriptions(self):
        """Test OMOP column descriptions are available."""
        assert "person_id" in OMOP_COLUMN_DESCRIPTIONS
        assert "condition_concept_id" in OMOP_COLUMN_DESCRIPTIONS
        assert "drug_concept_id" in OMOP_COLUMN_DESCRIPTIONS

        # Check descriptions are meaningful
        person_id_desc = OMOP_COLUMN_DESCRIPTIONS["person_id"]
        assert "identifier" in person_id_desc.lower()

        condition_concept_desc = OMOP_COLUMN_DESCRIPTIONS["condition_concept_id"]
        assert "concept" in condition_concept_desc.lower()


class TestSchemaIntegration:
    """Test schema tools integration."""

    @pytest.mark.asyncio
    @patch("omop_mcp.tools.schema.get_backend")
    async def test_end_to_end_schema_workflow(self, mock_get_backend):
        """Test complete schema exploration workflow."""
        # Setup mock backend
        mock_backend = AsyncMock()

        # Mock for table list
        mock_backend.execute_query.side_effect = [
            [{"table_name": "person", "table_type": "BASE TABLE", "table_schema": "main"}],
            [  # Mock for person table schema (first call)
                {
                    "column_name": "person_id",
                    "data_type": "INTEGER",
                    "is_nullable": "NO",
                    "column_default": None,
                    "ordinal_position": 1,
                },
                {
                    "column_name": "gender_concept_id",
                    "data_type": "INTEGER",
                    "is_nullable": "YES",
                    "column_default": None,
                    "ordinal_position": 2,
                },
            ],
            [  # Mock for person table schema (second call)
                {
                    "column_name": "person_id",
                    "data_type": "INTEGER",
                    "is_nullable": "NO",
                    "column_default": None,
                    "ordinal_position": 1,
                },
                {
                    "column_name": "gender_concept_id",
                    "data_type": "INTEGER",
                    "is_nullable": "YES",
                    "column_default": None,
                    "ordinal_position": 2,
                },
            ],
            [  # Mock for column search
                {
                    "table_name": "person",
                    "column_name": "person_id",
                    "data_type": "INTEGER",
                    "is_nullable": "NO",
                    "ordinal_position": 1,
                }
            ],
        ]
        mock_get_backend.return_value = mock_backend

        # 1. Get all tables
        all_tables = await get_all_tables_schema("bigquery")
        assert "person" in all_tables["tables"]

        # 2. Get specific table schema
        person_schema = await get_table_schema("person", "bigquery")
        assert person_schema["table_name"] == "person"
        assert person_schema["column_count"] == 2

        # 3. Search for specific columns
        person_id_columns = await search_columns("person_id", "bigquery")
        assert person_id_columns["total_matches"] == 1
        assert person_id_columns["columns"][0]["column_name"] == "person_id"

        # 4. Get OMOP CDM info
        cdm_info = get_omop_cdm_info()
        assert "person" in cdm_info["tables"]["core"]
        assert "person_id" in cdm_info["column_descriptions"]
