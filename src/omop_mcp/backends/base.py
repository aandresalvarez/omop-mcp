"""Backend protocol and base classes for database abstraction."""

from dataclasses import dataclass
from typing import Any, Protocol

from omop_mcp.models import SQLValidationResult


@dataclass
class CohortQueryParts:
    """Components of a cohort SQL query."""

    exposure_cte: str
    outcome_cte: str
    cohort_cte: str
    final_select: str

    def to_sql(self) -> str:
        """Combine parts into complete SQL."""
        return f"{self.exposure_cte},\n{self.outcome_cte},\n{self.cohort_cte}\n{self.final_select}"


class Backend(Protocol):
    """Protocol for database backend implementations."""

    name: str
    dialect: str

    async def build_cohort_sql(
        self,
        exposure_ids: list[int],
        outcome_ids: list[int],
        pre_outcome_days: int,
        cdm: str = "5.4",
    ) -> CohortQueryParts:
        """Build cohort SQL query parts."""
        ...

    async def validate_sql(self, sql: str) -> SQLValidationResult:
        """Validate SQL and estimate cost (dry-run)."""
        ...

    async def execute_query(self, sql: str, limit: int = 1000) -> list[dict[str, Any]]:
        """Execute SQL safely and return results."""
        ...

    def qualified_table(self, table: str) -> str:
        """Generate dialect-specific qualified table name."""
        ...

    def age_calculation_sql(self, birth_col: str = "birth_datetime") -> str:
        """Generate dialect-specific age calculation SQL."""
        ...
