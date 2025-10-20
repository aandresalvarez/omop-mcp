"""Configuration management using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class OMOPConfig(BaseSettings):
    """OMOP MCP server configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OpenAI (for PydanticAI agents)
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.0

    # ATHENA API
    athena_base_url: str = "https://athena.ohdsi.org/api/v1"
    athena_timeout: int = 30

    # BigQuery
    bigquery_project_id: str | None = None
    bigquery_dataset_id: str | None = None
    bigquery_location: str = "US"
    bigquery_credentials_path: str | None = None

    # Snowflake
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_database: str | None = None
    snowflake_schema: str | None = None
    snowflake_warehouse: str | None = None

    # DuckDB
    duckdb_database_path: str = ":memory:"  # Default to in-memory
    duckdb_schema: str = "main"

    # Postgres
    postgres_dsn: str | None = None
    postgres_schema: str = "public"

    # Auth (OAuth2.1)
    oauth_issuer: str | None = None
    oauth_audience: str | None = None

    # Execution guards
    max_query_cost_usd: float = 1.0
    allow_patient_list: bool = False
    query_timeout_sec: int = 30

    # SQL validation settings
    strict_table_validation: bool = False
    omop_allowed_tables: list[str] = Field(
        default=[
            "person",
            "condition_occurrence",
            "drug_exposure",
            "procedure_occurrence",
            "measurement",
            "observation",
            "visit_occurrence",
            "death",
            "location",
            "care_site",
            "provider",
            "concept",
            "vocabulary",
            "concept_relationship",
            "concept_ancestor",
        ]
    )
    omop_blocked_columns: list[str] = Field(
        default=[
            "person_source_value",
            "provider_source_value",
            "location_source_value",
            "care_site_source_value",
        ]
    )
    phi_mode: bool = False

    # Agent settings
    max_concepts_per_query: int = 50
    concept_search_top_k: int = 10
    per_query_time_limit_sec: int = 60
    max_retries: int = 3

    # Logging
    log_level: str = "INFO"


# Global config instance
config = OMOPConfig()  # type: ignore[call-arg]
