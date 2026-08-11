"""Query normalized product Change Records without a model call."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .product_core import load_json, sha256, validate_product_artifact


SUPPORTED_CHANGE_TYPES = {"added", "deleted", "property_modified"}


def validate_filters(filters: dict[str, Any]) -> None:
    """Reject malformed filters instead of silently returning an empty result."""
    allowed = {
        "change_types",
        "entity_types",
        "global_ids",
        "building_storey_names",
        "property_set",
        "property_name",
    }
    unknown = sorted(set(filters) - allowed)
    if unknown:
        raise ValueError(f"Unsupported query filters: {', '.join(unknown)}")
    for key in (
        "change_types",
        "entity_types",
        "global_ids",
        "building_storey_names",
    ):
        values = filters.get(key, [])
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value for value in values
        ):
            raise ValueError(f"{key} must be a list of non-empty strings")
    change_types = filters.get("change_types", [])
    invalid_changes = sorted(set(change_types) - SUPPORTED_CHANGE_TYPES)
    if invalid_changes:
        raise ValueError(f"Unsupported change types: {', '.join(invalid_changes)}")
    if any(not value.startswith("Ifc") for value in filters.get("entity_types", [])):
        raise ValueError("Every entity type must start with Ifc")
    if any(len(value) != 22 for value in filters.get("global_ids", [])):
        raise ValueError("Every GlobalId filter must contain exactly 22 characters")
    for key in ("property_set", "property_name"):
        if key in filters and not str(filters[key]).strip():
            raise ValueError(f"{key} must not be empty")


def record_matches(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Return whether a product Change Record satisfies all supplied filters."""
    if filters.get("change_types") and record["change_type"] not in filters[
        "change_types"
    ]:
        return False
    if filters.get("entity_types") and record["entity_type"] not in filters[
        "entity_types"
    ]:
        return False
    if filters.get("global_ids") and record["global_id"] not in filters[
        "global_ids"
    ]:
        return False
    if filters.get("building_storey_names"):
        storey = record["location"]["building_storey"]
        if storey is None or storey["name"] not in filters["building_storey_names"]:
            return False
    field = record["field"]
    if filters.get("property_set"):
        if field is None or field["property_set"] != filters["property_set"]:
            return False
    if filters.get("property_name"):
        if field is None or field["name"] != filters["property_name"]:
            return False
    return True


def query_product_artifact(
    artifact_path: Path, filters: dict[str, Any]
) -> dict[str, Any]:
    """Validate and query a v0.2 preview artifact."""
    artifact_path = artifact_path.expanduser().resolve()
    validate_filters(filters)
    artifact = load_json(artifact_path)
    validate_product_artifact(artifact)
    results = sorted(
        (
            record
            for record in artifact["changes"]
            if record_matches(record, filters)
        ),
        key=lambda item: item["change_id"],
    )
    return {
        "schema_version": artifact["schema_version"],
        "source": {
            "file_name": artifact_path.name,
            "sha256": sha256(artifact_path),
        },
        "filters": filters,
        "result_count": len(results),
        "results": results,
        "model_calls_made": 0,
    }
