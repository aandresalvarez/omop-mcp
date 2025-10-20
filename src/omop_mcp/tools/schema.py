"""
Schema introspection tools for OMOP CDM databases.

This module provides functionality to query database schema information,
including table structures, column definitions, and OMOP CDM metadata.
"""

from typing import Any

import structlog

from omop_mcp.backends.registry import get_backend
from omop_mcp.tools.sql_validator import get_omop_table_info

logger = structlog.get_logger(__name__)

# OMOP CDM table descriptions
OMOP_TABLE_DESCRIPTIONS = get_omop_table_info()

# Standard OMOP CDM column descriptions
OMOP_COLUMN_DESCRIPTIONS = {
    # Person table
    "person_id": "Unique identifier for each person",
    "gender_concept_id": "Gender concept identifier",
    "year_of_birth": "Year of birth",
    "month_of_birth": "Month of birth",
    "day_of_birth": "Day of birth",
    "birth_datetime": "Date and time of birth",
    "race_concept_id": "Race concept identifier",
    "ethnicity_concept_id": "Ethnicity concept identifier",
    "location_id": "Location identifier",
    "provider_id": "Provider identifier",
    "care_site_id": "Care site identifier",
    # Condition occurrence
    "condition_occurrence_id": "Unique identifier for condition occurrence",
    "condition_concept_id": "Condition concept identifier",
    "condition_start_date": "Start date of condition",
    "condition_start_datetime": "Start date and time of condition",
    "condition_end_date": "End date of condition",
    "condition_end_datetime": "End date and time of condition",
    "condition_type_concept_id": "Type of condition occurrence",
    "condition_status_concept_id": "Status of condition",
    "condition_stop_reason": "Reason for stopping condition",
    "condition_visit_occurrence_id": "Visit occurrence identifier",
    "condition_visit_detail_id": "Visit detail identifier",
    # Drug exposure
    "drug_exposure_id": "Unique identifier for drug exposure",
    "drug_concept_id": "Drug concept identifier",
    "drug_exposure_start_date": "Start date of drug exposure",
    "drug_exposure_start_datetime": "Start date and time of drug exposure",
    "drug_exposure_end_date": "End date of drug exposure",
    "drug_exposure_end_datetime": "End date and time of drug exposure",
    "verbatim_end_date": "Verbatim end date",
    "drug_type_concept_id": "Type of drug exposure",
    "drug_stop_reason": "Reason for stopping drug",
    "refills": "Number of refills",
    "drug_quantity": "Quantity of drug",
    "days_supply": "Days supply",
    "sig": "Prescription signature",
    "route_concept_id": "Route of administration concept",
    "lot_number": "Lot number",
    "drug_provider_id": "Provider identifier",
    "drug_visit_occurrence_id": "Visit occurrence identifier",
    "drug_visit_detail_id": "Visit detail identifier",
    # Procedure occurrence
    "procedure_occurrence_id": "Unique identifier for procedure occurrence",
    "procedure_concept_id": "Procedure concept identifier",
    "procedure_date": "Date of procedure",
    "procedure_datetime": "Date and time of procedure",
    "procedure_type_concept_id": "Type of procedure occurrence",
    "modifier_concept_id": "Modifier concept identifier",
    "procedure_quantity": "Quantity of procedure",
    "procedure_provider_id": "Provider identifier",
    "procedure_visit_occurrence_id": "Visit occurrence identifier",
    "procedure_visit_detail_id": "Visit detail identifier",
    # Measurement
    "measurement_id": "Unique identifier for measurement",
    "measurement_concept_id": "Measurement concept identifier",
    "measurement_date": "Date of measurement",
    "measurement_datetime": "Date and time of measurement",
    "measurement_type_concept_id": "Type of measurement",
    "operator_concept_id": "Operator concept identifier",
    "measurement_value_as_number": "Numeric value of measurement",
    "measurement_value_as_string": "String value of measurement",
    "measurement_unit_concept_id": "Unit concept identifier",
    "range_low": "Lower range value",
    "range_high": "Upper range value",
    "measurement_provider_id": "Provider identifier",
    "measurement_visit_occurrence_id": "Visit occurrence identifier",
    "measurement_visit_detail_id": "Visit detail identifier",
    # Observation
    "observation_id": "Unique identifier for observation",
    "observation_concept_id": "Observation concept identifier",
    "observation_date": "Date of observation",
    "observation_datetime": "Date and time of observation",
    "observation_type_concept_id": "Type of observation",
    "observation_value_as_string": "String value of observation",
    "observation_value_as_number": "Numeric value of observation",
    "qualifier_concept_id": "Qualifier concept identifier",
    "observation_unit_concept_id": "Unit concept identifier",
    "observation_provider_id": "Provider identifier",
    "observation_visit_occurrence_id": "Visit occurrence identifier",
    "observation_visit_detail_id": "Visit detail identifier",
    # Visit occurrence
    "visit_occurrence_id": "Unique identifier for visit occurrence",
    "visit_concept_id": "Visit concept identifier",
    "visit_start_date": "Start date of visit",
    "visit_start_datetime": "Start date and time of visit",
    "visit_end_date": "End date of visit",
    "visit_end_datetime": "End date and time of visit",
    "visit_type_concept_id": "Type of visit occurrence",
    "visit_provider_id": "Provider identifier",
    "visit_care_site_id": "Care site identifier",
    "visit_source_value": "Source value for visit",
    "admitted_from_concept_id": "Admitted from concept identifier",
    "discharged_to_concept_id": "Discharged to concept identifier",
    "preceding_visit_occurrence_id": "Preceding visit occurrence identifier",
    # Death
    "death_date": "Date of death",
    "death_datetime": "Date and time of death",
    "death_type_concept_id": "Type of death",
    "cause_concept_id": "Cause of death concept identifier",
    "cause_source_value": "Source value for cause of death",
    "cause_source_concept_id": "Source concept identifier for cause",
}


async def get_table_schema(table_name: str, backend_name: str = "bigquery") -> dict[str, Any]:
    """
    Get schema information for a specific OMOP table.

    Args:
        table_name: Name of the OMOP table
        backend_name: Database backend to query

    Returns:
        Dictionary containing table schema information
    """
    logger.info("getting_table_schema", table=table_name, backend=backend_name)

    try:
        backend = get_backend(backend_name)

        # Query INFORMATION_SCHEMA for table structure
        schema_query = f"""
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default,
            ordinal_position
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
        """

        # Execute schema query
        columns = await backend.execute_query(schema_query, limit=1000)

        # Enhance with OMOP CDM descriptions
        enhanced_columns = []
        for col in columns:
            column_name = col["column_name"]
            enhanced_col = {
                "name": column_name,
                "type": col["data_type"],
                "nullable": col["is_nullable"] == "YES",
                "default": col.get("column_default"),
                "position": col["ordinal_position"],
                "description": OMOP_COLUMN_DESCRIPTIONS.get(column_name, ""),
                "is_omop_standard": column_name in OMOP_COLUMN_DESCRIPTIONS,
            }
            enhanced_columns.append(enhanced_col)

        result = {
            "table_name": table_name,
            "description": OMOP_TABLE_DESCRIPTIONS.get(table_name, ""),
            "is_omop_standard": table_name in OMOP_TABLE_DESCRIPTIONS,
            "columns": enhanced_columns,
            "column_count": len(enhanced_columns),
            "backend": backend_name,
            "schema_source": "INFORMATION_SCHEMA",
        }

        logger.info("table_schema_retrieved", table=table_name, columns=len(enhanced_columns))
        return result

    except Exception as e:
        logger.error("table_schema_error", table=table_name, error=str(e))
        raise


async def get_all_tables_schema(
    backend_name: str = "bigquery", include_non_omop: bool = False
) -> dict[str, Any]:
    """
    Get schema information for all tables in the database.

    Args:
        backend_name: Database backend to query
        include_non_omop: Whether to include non-OMOP tables

    Returns:
        Dictionary containing all table schemas
    """
    logger.info(
        "getting_all_tables_schema", backend=backend_name, include_non_omop=include_non_omop
    )

    try:
        backend = get_backend(backend_name)

        # Query INFORMATION_SCHEMA for all tables
        tables_query = """
        SELECT
            table_name,
            table_type,
            table_schema
        FROM INFORMATION_SCHEMA.TABLES
        WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY table_name
        """

        tables = await backend.execute_query(tables_query, limit=1000)

        # Filter OMOP tables if requested
        if not include_non_omop:
            omop_tables = set(OMOP_TABLE_DESCRIPTIONS.keys())
            tables = [t for t in tables if t["table_name"] in omop_tables]

        # Get detailed schema for each table
        table_schemas = {}
        for table in tables:
            table_name = table["table_name"]
            try:
                schema_info = await get_table_schema(table_name, backend_name)
                table_schemas[table_name] = schema_info
            except Exception as e:
                logger.warning("failed_to_get_table_schema", table=table_name, error=str(e))
                # Add basic info even if detailed schema fails
                table_schemas[table_name] = {
                    "table_name": table_name,
                    "description": OMOP_TABLE_DESCRIPTIONS.get(table_name, ""),
                    "is_omop_standard": table_name in OMOP_TABLE_DESCRIPTIONS,
                    "columns": [],
                    "column_count": 0,
                    "backend": backend_name,
                    "error": str(e),
                }

        result = {
            "tables": table_schemas,
            "total_tables": len(table_schemas),
            "omop_tables": len([t for t in table_schemas.values() if t["is_omop_standard"]]),
            "backend": backend_name,
            "include_non_omop": include_non_omop,
        }

        logger.info("all_tables_schema_retrieved", total_tables=len(table_schemas))
        return result

    except Exception as e:
        logger.error("all_tables_schema_error", backend=backend_name, error=str(e))
        raise


async def search_columns(
    column_pattern: str, backend_name: str = "bigquery", table_pattern: str | None = None
) -> dict[str, Any]:
    """
    Search for columns matching a pattern across tables.

    Args:
        column_pattern: Pattern to match column names (SQL LIKE pattern)
        backend_name: Database backend to query
        table_pattern: Optional pattern to filter tables

    Returns:
        Dictionary containing matching columns
    """
    logger.info("searching_columns", pattern=column_pattern, backend=backend_name)

    try:
        backend = get_backend(backend_name)

        # Build query with optional table filter
        where_clause = f"column_name LIKE '{column_pattern}'"
        if table_pattern:
            where_clause += f" AND table_name LIKE '{table_pattern}'"

        search_query = f"""
        SELECT
            table_name,
            column_name,
            data_type,
            is_nullable,
            ordinal_position
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE {where_clause}
        ORDER BY table_name, ordinal_position
        """

        columns = await backend.execute_query(search_query, limit=1000)

        # Enhance with descriptions
        enhanced_columns = []
        for col in columns:
            column_name = col["column_name"]
            enhanced_col = {
                "table_name": col["table_name"],
                "column_name": column_name,
                "data_type": col["data_type"],
                "nullable": col["is_nullable"] == "YES",
                "position": col["ordinal_position"],
                "description": OMOP_COLUMN_DESCRIPTIONS.get(column_name, ""),
                "is_omop_standard": column_name in OMOP_COLUMN_DESCRIPTIONS,
            }
            enhanced_columns.append(enhanced_col)

        result = {
            "pattern": column_pattern,
            "table_pattern": table_pattern,
            "columns": enhanced_columns,
            "total_matches": len(enhanced_columns),
            "backend": backend_name,
        }

        logger.info("column_search_completed", matches=len(enhanced_columns))
        return result

    except Exception as e:
        logger.error("column_search_error", pattern=column_pattern, error=str(e))
        raise


def get_omop_cdm_info() -> dict[str, Any]:
    """
    Get general information about OMOP CDM structure.

    Returns:
        Dictionary containing OMOP CDM metadata
    """
    return {
        "version": "5.4",
        "description": "OMOP Common Data Model v5.4",
        "tables": {
            "core": [
                "person",
                "condition_occurrence",
                "drug_exposure",
                "procedure_occurrence",
                "measurement",
                "observation",
                "visit_occurrence",
                "death",
            ],
            "vocabulary": [
                "concept",
                "vocabulary",
                "concept_relationship",
                "concept_ancestor",
                "concept_synonym",
                "concept_class",
                "domain",
                "relationship",
            ],
            "reference": [
                "location",
                "care_site",
                "provider",
                "payer_plan_period",
                "cost",
                "cohort",
                "cohort_definition",
            ],
        },
        "domains": [
            "Condition",
            "Drug",
            "Procedure",
            "Measurement",
            "Observation",
            "Device",
            "Visit",
            "Death",
        ],
        "vocabularies": [
            "SNOMED",
            "RxNorm",
            "LOINC",
            "ICD10CM",
            "ICD10PCS",
            "CPT4",
            "HCPCS",
            "NDC",
            "UMLS",
            "ATC",
        ],
        "table_descriptions": OMOP_TABLE_DESCRIPTIONS,
        "column_descriptions": OMOP_COLUMN_DESCRIPTIONS,
    }
