"""Pydantic models for OMOP MCP server."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OMOPDomain(str, Enum):
    """OMOP domain types."""

    CONDITION = "Condition"
    DRUG = "Drug"
    PROCEDURE = "Procedure"
    OBSERVATION = "Observation"
    MEASUREMENT = "Measurement"
    DEVICE = "Device"


class OMOPConcept(BaseModel):
    """OMOP concept with metadata."""

    concept_id: int = Field(..., alias="id")
    concept_name: str = Field(..., alias="name")
    domain_id: str = Field(..., alias="domain")
    vocabulary_id: str = Field(..., alias="vocabulary")
    concept_class_id: str = Field(..., alias="className")
    standard_concept: str | None = Field(None, alias="standardConcept")
    concept_code: str = Field(..., alias="code")
    invalid_reason: str | None = Field(None, alias="invalidReason")
    score: float | None = None  # Search relevance score from ATHENA

    model_config = ConfigDict(populate_by_name=True)

    def is_standard(self) -> bool:
        """Check if concept is standard."""
        return self.standard_concept == "S"

    def is_valid(self) -> bool:
        """Check if concept is valid."""
        return self.invalid_reason is None


class ConceptRelationship(BaseModel):
    """Relationship between two OMOP concepts."""

    concept_id_1: int
    concept_id_2: int
    relationship_id: str
    relationship_name: str


class ConceptDiscoveryRequest(BaseModel):
    """Input for concept discovery."""

    clinical_text: str = Field(..., description="Clinical term to map (e.g., 'type 2 diabetes')")
    domain: OMOPDomain | None = Field(None, description="OMOP domain filter")
    vocabulary: str | None = Field(None, description="Vocabulary filter (e.g., 'SNOMED')")
    max_concepts: int = Field(50, ge=1, le=100, description="Maximum concepts to return")
    include_relationships: bool = Field(True, description="Include concept relationships")


class ConceptDiscoveryResult(BaseModel):
    """Output from concept discovery."""

    query: str
    concepts: list[OMOPConcept]
    relationships: dict[int, list[ConceptRelationship]] = Field(default_factory=dict)
    search_metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def concept_ids(self) -> list[int]:
        """Get list of all concept IDs."""
        return [c.concept_id for c in self.concepts]

    @property
    def standard_concepts(self) -> list[OMOPConcept]:
        """Get only standard concepts."""
        return [c for c in self.concepts if c.is_standard()]


class CohortSQLRequest(BaseModel):
    """Input for SQL generation."""

    exposure_concept_ids: list[int] = Field(..., min_length=1, description="Exposure concept IDs")
    outcome_concept_ids: list[int] = Field(..., min_length=1, description="Outcome concept IDs")
    pre_outcome_days: int = Field(90, ge=0, description="Days between exposure and outcome")
    validate_sql: bool = Field(True, description="Run BigQuery dry-run validation")
    project_id: str | None = Field(None, description="BigQuery project ID")
    dataset_id: str | None = Field(None, description="BigQuery dataset ID")


class SQLValidationResult(BaseModel):
    """BigQuery validation result."""

    valid: bool
    estimated_bytes: int | None = None
    estimated_cost_usd: float | None = None
    error_message: str | None = None
    execution_plan: dict[str, Any] | None = None


class CohortSQLResult(BaseModel):
    """Output from SQL generation."""

    sql: str
    validation: SQLValidationResult | None = None
    concept_counts: dict[str, int] = Field(default_factory=dict)
    backend: str = "bigquery"
    dialect: str = "bigquery"
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def is_valid(self) -> bool:
        """Check if SQL passed validation."""
        return self.validation is not None and self.validation.valid


class QueryOMOPRequest(BaseModel):
    """Input for analytical queries."""

    query_type: str = Field(..., description="count, breakdown, or list_patients")
    concept_ids: list[int] = Field(..., min_length=1, description="OMOP concept IDs")
    domain: str = Field("Condition", description="OMOP domain")
    backend: str = Field("bigquery", description="Backend to use")
    execute: bool = Field(True, description="Execute query or return SQL only")
    limit: int = Field(1000, ge=1, le=1000, description="Maximum rows")

    @field_validator("query_type")
    def validate_query_type(cls, v):
        if v not in ["count", "breakdown", "list_patients"]:
            raise ValueError("query_type must be: count, breakdown, or list_patients")
        return v


class QueryOMOPResult(BaseModel):
    """Output from analytical queries."""

    sql: str
    results: list[dict[str, Any]] | None = None
    row_count: int | None = None
    estimated_cost_usd: float | None = None
    estimated_bytes: int | None = None
    backend: str
    dialect: str
    timestamp: datetime = Field(default_factory=datetime.now)
