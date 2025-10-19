"""Export tools for OMOP MCP data.

This module provides functions to export OMOP data in various formats:
- Concept sets (JSON, CSV)
- Query results (CSV, JSON, Parquet)
- SQL queries (SQL files)
- Cohort definitions (JSON)

All exports include metadata for reproducibility and documentation.
"""

import csv
import gzip
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from omop_mcp.models import CohortSQLResult, ConceptDiscoveryResult, OMOPConcept

logger = logging.getLogger(__name__)


class ExportError(Exception):
    """Exception raised when export operations fail."""

    pass


def export_concept_set(
    concepts: list[OMOPConcept] | ConceptDiscoveryResult,
    output_path: str | Path,
    format: str = "json",
    include_metadata: bool = True,
    compress: bool = False,
) -> dict[str, Any]:
    """
    Export OMOP concept set to file.

    Args:
        concepts: List of concepts or ConceptDiscoveryResult
        output_path: Output file path (extension added if missing)
        format: Export format ("json" or "csv")
        include_metadata: Include export metadata in file
        compress: Compress output with gzip

    Returns:
        Dictionary with export metadata (path, count, timestamp)

    Raises:
        ExportError: If export fails
        ValueError: If format is invalid

    Example:
        >>> concepts = await discover_concepts("diabetes")
        >>> result = export_concept_set(
        ...     concepts,
        ...     "diabetes_concepts.json",
        ...     format="json"
        ... )
        >>> print(f"Exported {result['concept_count']} concepts to {result['path']}")
    """
    if format not in ["json", "csv"]:
        raise ValueError(f"Invalid format: {format}. Must be 'json' or 'csv'")

    # Extract concepts if ConceptDiscoveryResult
    if isinstance(concepts, ConceptDiscoveryResult):
        concept_list = concepts.concepts
        query_info: dict[str, Any] | None = {"query": concepts.query}
    else:
        concept_list = concepts
        query_info = None

    # Prepare output path
    output_path = Path(output_path)
    if not output_path.suffix:
        output_path = output_path.with_suffix(f".{format}")
    if compress:
        output_path = Path(str(output_path) + ".gz")

    # Create parent directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"Exporting concept set to {output_path} (format={format}, count={len(concept_list)}, compress={compress})"
    )

    try:
        if format == "json":
            _export_concepts_json(concept_list, output_path, include_metadata, query_info, compress)
        elif format == "csv":
            _export_concepts_csv(concept_list, output_path, include_metadata, query_info, compress)

        result = {
            "path": str(output_path),
            "format": format,
            "concept_count": len(concept_list),
            "compressed": compress,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"Concept set exported: {result}")
        return result

    except Exception as e:
        logger.error(f"Concept set export failed for {output_path}: {e}", exc_info=True)
        raise ExportError(f"Failed to export concept set: {e}") from e


def _export_concepts_json(
    concepts: list[OMOPConcept],
    output_path: Path,
    include_metadata: bool,
    query_info: dict[str, Any] | None,
    compress: bool,
) -> None:
    """Export concepts to JSON format."""
    data: dict[str, Any] = {
        "concepts": [c.model_dump() for c in concepts],
    }

    if include_metadata:
        metadata: dict[str, Any] = {
            "export_timestamp": datetime.now().isoformat(),
            "concept_count": len(concepts),
            "standard_count": sum(1 for c in concepts if c.is_standard()),
        }
        if query_info:
            metadata["query"] = query_info
        data["metadata"] = metadata

    open_func = gzip.open if compress else open  # type: ignore[assignment]
    mode = "wt" if compress else "w"

    with open_func(output_path, mode) as f:  # type: ignore[operator,arg-type]
        json.dump(data, f, indent=2)  # type: ignore[operator,arg-type]


def _export_concepts_csv(
    concepts: list[OMOPConcept],
    output_path: Path,
    include_metadata: bool,
    query_info: dict[str, Any] | None,
    compress: bool,
) -> None:
    """Export concepts to CSV format."""
    open_func = gzip.open if compress else open  # type: ignore[assignment]
    mode = "wt" if compress else "w"

    with open_func(output_path, mode, newline="") as f:  # type: ignore[operator,call-overload,arg-type]
        # Write metadata as comments
        if include_metadata:
            f.write(f"# Exported: {datetime.now().isoformat()}\n")  # type: ignore[arg-type]
            f.write(f"# Concept count: {len(concepts)}\n")  # type: ignore[arg-type]
            if query_info:
                f.write(f"# Query: {query_info.get('query')}\n")  # type: ignore[arg-type]
            f.write("#\n")  # type: ignore[arg-type]

        # Write CSV
        if concepts:
            fieldnames = [
                "concept_id",
                "concept_name",
                "domain_id",
                "vocabulary_id",
                "concept_class_id",
                "standard_concept",
                "concept_code",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)  # type: ignore[arg-type]
            writer.writeheader()

            for concept in concepts:
                writer.writerow(
                    {
                        "concept_id": concept.concept_id,
                        "concept_name": concept.concept_name,
                        "domain_id": concept.domain_id,
                        "vocabulary_id": concept.vocabulary_id,
                        "concept_class_id": concept.concept_class_id,
                        "standard_concept": concept.standard_concept or "",
                        "concept_code": concept.concept_code,
                    }
                )


def export_sql_query(
    sql: str | CohortSQLResult,
    output_path: str | Path,
    include_metadata: bool = True,
    format_sql: bool = True,
) -> dict[str, Any]:
    """
    Export SQL query to file.

    Args:
        sql: SQL string or CohortSQLResult
        output_path: Output file path (extension added if missing)
        include_metadata: Include metadata as SQL comments
        format_sql: Format SQL for readability

    Returns:
        Dictionary with export metadata

    Raises:
        ExportError: If export fails

    Example:
        >>> result = await generate_cohort_sql(...)
        >>> export_info = export_sql_query(
        ...     result,
        ...     "cohort_query.sql",
        ...     include_metadata=True
        ... )
    """
    # Extract SQL and metadata
    if isinstance(sql, CohortSQLResult):
        sql_text = sql.sql
        metadata = {
            "backend": sql.backend,
            "dialect": sql.dialect,
            "is_valid": sql.is_valid,
            "timestamp": sql.timestamp.isoformat(),
            "concept_counts": sql.concept_counts,
        }
    else:
        sql_text = sql
        metadata = None

    # Prepare output path
    output_path = Path(output_path)
    if not output_path.suffix:
        output_path = output_path.with_suffix(".sql")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Exporting SQL query to {output_path} (length={len(sql_text)})")

    try:
        with open(output_path, "w") as f:
            # Write metadata as SQL comments
            if include_metadata:
                f.write("-- =====================================================\n")
                f.write("-- OMOP CDM SQL Query\n")
                f.write(f"-- Generated: {datetime.now().isoformat()}\n")
                if metadata:
                    f.write(f"-- Backend: {metadata['backend']}\n")
                    f.write(f"-- Dialect: {metadata['dialect']}\n")
                    f.write(f"-- Valid: {metadata['is_valid']}\n")
                    if metadata.get("concept_counts"):
                        f.write(f"-- Concept counts: {metadata['concept_counts']}\n")
                f.write("-- =====================================================\n\n")

            # Format SQL if requested
            if format_sql:
                from omop_mcp.tools.sqlgen import format_sql as fmt_sql

                sql_text = fmt_sql(sql_text)

            f.write(sql_text)
            f.write("\n")

        result = {
            "path": str(output_path),
            "sql_length": len(sql_text),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"SQL query exported: {result}")
        return result

    except Exception as e:
        logger.error(f"SQL query export failed for {output_path}: {e}", exc_info=True)
        raise ExportError(f"Failed to export SQL query: {e}") from e


def export_query_results(
    results: list[dict[str, Any]],
    output_path: str | Path,
    format: str = "csv",
    include_metadata: bool = True,
    compress: bool = False,
    chunk_size: int | None = None,
) -> dict[str, Any]:
    """
    Export query results to file.

    Args:
        results: List of result dictionaries
        output_path: Output file path
        format: Export format ("csv", "json", or "jsonl")
        include_metadata: Include metadata in export
        compress: Compress output with gzip
        chunk_size: For large exports, write in chunks (None = all at once)

    Returns:
        Dictionary with export metadata

    Raises:
        ExportError: If export fails
        ValueError: If format is invalid

    Example:
        >>> results = [
        ...     {"person_id": 1, "age": 45, "gender": "M"},
        ...     {"person_id": 2, "age": 52, "gender": "F"},
        ... ]
        >>> export_info = export_query_results(
        ...     results,
        ...     "cohort_results.csv"
        ... )
    """
    if format not in ["csv", "json", "jsonl"]:
        raise ValueError(f"Invalid format: {format}. Must be 'csv', 'json', or 'jsonl'")

    output_path = Path(output_path)
    if not output_path.suffix:
        output_path = output_path.with_suffix(f".{format}")
    if compress:
        output_path = Path(str(output_path) + ".gz")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"Exporting query results to {output_path} (format={format}, rows={len(results)}, compress={compress})"
    )

    try:
        if format == "csv":
            _export_results_csv(results, output_path, include_metadata, compress)
        elif format == "json":
            _export_results_json(results, output_path, include_metadata, compress)
        elif format == "jsonl":
            _export_results_jsonl(results, output_path, include_metadata, compress, chunk_size)

        result = {
            "path": str(output_path),
            "format": format,
            "row_count": len(results),
            "compressed": compress,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"Query results exported: {result}")
        return result

    except Exception as e:
        logger.error(f"Query results export failed for {output_path}: {e}", exc_info=True)
        raise ExportError(f"Failed to export query results: {e}") from e


def _export_results_csv(
    results: list[dict[str, Any]],
    output_path: Path,
    include_metadata: bool,
    compress: bool,
) -> None:
    """Export results to CSV format."""
    if not results:
        raise ExportError("No results to export")

    open_func = gzip.open if compress else open  # type: ignore[assignment]
    mode = "wt" if compress else "w"

    with open_func(output_path, mode, newline="") as f:  # type: ignore[operator,call-overload,arg-type]
        if include_metadata:
            f.write(f"# Exported: {datetime.now().isoformat()}\n")  # type: ignore[arg-type]
            f.write(f"# Row count: {len(results)}\n")  # type: ignore[arg-type]
            f.write("#\n")  # type: ignore[arg-type]

        fieldnames = list(results[0].keys())
        writer = csv.DictWriter(f, fieldnames=fieldnames)  # type: ignore[arg-type]
        writer.writeheader()
        writer.writerows(results)


def _export_results_json(
    results: list[dict[str, Any]],
    output_path: Path,
    include_metadata: bool,
    compress: bool,
) -> None:
    """Export results to JSON format."""
    data: dict[str, Any] = {"results": results}

    if include_metadata:
        metadata: dict[str, Any] = {
            "export_timestamp": datetime.now().isoformat(),
            "row_count": len(results),
        }
        data["metadata"] = metadata

    open_func = gzip.open if compress else open  # type: ignore[assignment]
    mode = "wt" if compress else "w"

    with open_func(output_path, mode) as f:  # type: ignore[operator,arg-type]
        json.dump(data, f, indent=2, default=str)  # type: ignore[operator,arg-type]


def _export_results_jsonl(
    results: list[dict[str, Any]],
    output_path: Path,
    include_metadata: bool,
    compress: bool,
    chunk_size: int | None,
) -> None:
    """Export results to JSONL format (one JSON per line)."""
    open_func = gzip.open if compress else open  # type: ignore[assignment]
    mode = "wt" if compress else "w"

    with open_func(output_path, mode) as f:  # type: ignore[operator,arg-type]
        if include_metadata:
            # Write metadata as first line (comment not standard in JSONL)
            metadata = {
                "_metadata": {
                    "export_timestamp": datetime.now().isoformat(),
                    "row_count": len(results),
                }
            }
            f.write(json.dumps(metadata, default=str) + "\n")  # type: ignore[arg-type]

        # Write each result as a line
        for result in results:
            f.write(json.dumps(result, default=str) + "\n")  # type: ignore[arg-type]


def export_cohort_definition(
    definition: dict[str, Any] | CohortSQLResult,
    output_path: str | Path,
    include_sql: bool = True,
) -> dict[str, Any]:
    """
    Export cohort definition to JSON.

    Args:
        definition: Cohort definition dict or CohortSQLResult
        output_path: Output file path
        include_sql: Include generated SQL in export

    Returns:
        Dictionary with export metadata

    Raises:
        ExportError: If export fails

    Example:
        >>> result = await generate_cohort_sql(
        ...     exposure_concept_ids=[1503297],
        ...     outcome_concept_ids=[443530],
        ...     time_window_days=90
        ... )
        >>> export_info = export_cohort_definition(
        ...     result,
        ...     "cohort_definition.json"
        ... )
    """
    output_path = Path(output_path)
    if not output_path.suffix:
        output_path = output_path.with_suffix(".json")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Exporting cohort definition to {output_path}")

    try:
        # Prepare cohort definition
        if isinstance(definition, CohortSQLResult):
            cohort_def = {
                "concept_counts": definition.concept_counts,
                "backend": definition.backend,
                "dialect": definition.dialect,
                "is_valid": definition.is_valid,
                "timestamp": definition.timestamp.isoformat(),
            }
            if include_sql:
                cohort_def["sql"] = definition.sql
            if definition.validation:
                cohort_def["validation"] = definition.validation.model_dump()
        else:
            cohort_def = definition

        # Add export metadata
        export_data = {
            "cohort_definition": cohort_def,
            "export_metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "format_version": "1.0",
            },
        }

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        result = {
            "path": str(output_path),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"Cohort definition exported: {result}")
        return result

    except Exception as e:
        logger.error(f"Cohort definition export failed for {output_path}: {e}", exc_info=True)
        raise ExportError(f"Failed to export cohort definition: {e}") from e
