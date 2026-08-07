"""Deterministic Change Record query tool used by Gate 3 workflows."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHANGE_RECORD_PATH = (
    REPOSITORY_ROOT / "data" / "ground_truth" / "gate2-change-records.json"
)
CHANGE_RECORD_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "change-record.schema.json"
)
REQUEST_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "change-query-request.schema.json"
)
RESPONSE_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "change-query-response.schema.json"
)


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return data


def validate(instance: Any, schema_path: Path) -> None:
    """Validate an instance, registering the shared Change Record schema."""
    schema = load_json(schema_path)
    change_schema = load_json(CHANGE_RECORD_SCHEMA_PATH)
    request_schema = load_json(REQUEST_SCHEMA_PATH)
    registry = (
        Registry()
        .with_resource(
            change_schema["$id"], Resource.from_contents(change_schema)
        )
        .with_resource(
            request_schema["$id"], Resource.from_contents(request_schema)
        )
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, registry=registry).validate(instance)


def record_matches(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Return whether a Change Record satisfies every supplied filter."""
    if "change_types" in filters and record["change_type"] not in filters[
        "change_types"
    ]:
        return False
    if "entity_types" in filters and record["entity_type"] not in filters[
        "entity_types"
    ]:
        return False
    if "global_ids" in filters and record["global_id"] not in filters[
        "global_ids"
    ]:
        return False

    storey = record["location"]["building_storey"]
    if "building_storey_names" in filters:
        if storey is None or storey["name"] not in filters[
            "building_storey_names"
        ]:
            return False

    field = record["field"]
    if "property_set" in filters:
        if field is None or field["property_set"] != filters["property_set"]:
            return False
    if "property_name" in filters:
        if field is None or field["name"] != filters["property_name"]:
            return False
    return True


def query_change_records(
    request: dict[str, Any],
    *,
    change_record_path: Path = DEFAULT_CHANGE_RECORD_PATH,
) -> dict[str, Any]:
    """Validate a query and return exact matching Change Records."""
    validate(request, REQUEST_SCHEMA_PATH)
    change_record_path = change_record_path.resolve()
    artifact = load_json(change_record_path)
    validate(artifact, CHANGE_RECORD_SCHEMA_PATH)

    filters = request["filters"]
    results = sorted(
        (
            record
            for record in artifact["changes"]
            if record_matches(record, filters)
        ),
        key=lambda record: record["change_id"],
    )
    try:
        source_path = change_record_path.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        source_path = str(change_record_path)

    response = {
        "schema_version": "0.1.0",
        "source": {
            "path": source_path,
            "sha256": sha256(change_record_path),
        },
        "filters": filters,
        "result_count": len(results),
        "results": results,
    }
    validate(response, RESPONSE_SCHEMA_PATH)
    return response
