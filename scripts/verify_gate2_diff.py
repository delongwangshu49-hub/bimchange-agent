"""Verify the Gate 2 IfcDiff result and normalized change records."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import ifcopenshell
from ifcopenshell.util.element import get_container, get_pset
from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_PATH = (
    REPOSITORY_ROOT / "data" / "ground_truth" / "gate2-change-records.json"
)
DIFF_PATH = REPOSITORY_ROOT / "evals" / "results" / "gate2-ifcdiff.json"

ALLOWED_CHANGE_TYPES = {"added", "deleted", "property_modified"}


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def by_guid_or_none(
    model: ifcopenshell.file, global_id: str
) -> ifcopenshell.entity_instance | None:
    """Look up an IFC entity without treating absence as an exception."""
    try:
        return model.by_guid(global_id)
    except RuntimeError:
        return None


def entity_snapshot(entity: ifcopenshell.entity_instance) -> dict[str, Any]:
    """Return the snapshot fields used by the Gate 2 change contract."""
    return {"name": entity.Name, "tag": entity.Tag}


def entity_reference(
    entity: ifcopenshell.entity_instance | None,
) -> dict[str, Any] | None:
    """Return the normalized reference used by the Gate 2 change contract."""
    if entity is None:
        return None
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": entity.Name,
    }


def element_location(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    """Return the actual direct container and storey, when available."""
    container = get_container(element)
    storey = container if container and container.is_a("IfcBuildingStorey") else None
    return {
        "spatial_container": entity_reference(container),
        "building_storey": entity_reference(storey),
    }


def validate_change_contract(ground_truth: dict[str, Any]) -> None:
    """Validate the JSON Schema plus cross-record Gate 2 invariants."""
    schema_path = REPOSITORY_ROOT / ground_truth["schema"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["$id"] == "https://bimchange-agent.local/change-record.schema.json"
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(ground_truth)

    records = ground_truth["changes"]
    assert len(records) == 3
    assert len({record["change_id"] for record in records}) == len(records)
    for record in records:
        assert record["change_type"] in ALLOWED_CHANGE_TYPES
        assert record["evidence"]["reference_source"] == (
            "controlled_revision_generator"
        )
        assert record["evidence"]["detector"] == "IfcDiff 0.8.5"


def main() -> None:
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    diff = json.loads(DIFF_PATH.read_text(encoding="utf-8"))
    validate_change_contract(ground_truth)

    source_path = REPOSITORY_ROOT / ground_truth["source_ifc"]
    revised_path = REPOSITORY_ROOT / ground_truth["revised_ifc"]
    assert sha256(source_path) == ground_truth["source_sha256"]
    assert sha256(revised_path) == ground_truth["revised_sha256"]

    records = {record["change_type"]: record for record in ground_truth["changes"]}
    assert set(records) == ALLOWED_CHANGE_TYPES
    added = records["added"]
    deleted = records["deleted"]
    modified = records["property_modified"]

    assert diff["added"] == [added["global_id"]]
    assert diff["deleted"] == [deleted["global_id"]]
    assert set(diff["changed"]) == {modified["global_id"]}

    property_path = (
        f"root['{modified['field']['property_set']}']"
        f"['{modified['field']['name']}']"
    )
    actual_change = diff["changed"][modified["global_id"]][
        "properties_changed"
    ]["values_changed"][property_path]
    assert actual_change["old_value"] == modified["old_value"]
    assert actual_change["new_value"] == modified["new_value"]

    source_model = ifcopenshell.open(source_path)
    revised_model = ifcopenshell.open(revised_path)

    assert by_guid_or_none(source_model, added["global_id"]) is None
    added_entity = by_guid_or_none(revised_model, added["global_id"])
    assert added_entity is not None
    assert added_entity.is_a() == added["entity_type"]
    assert entity_snapshot(added_entity) == added["new_value"]
    assert element_location(added_entity) == added["location"]

    deleted_entity = by_guid_or_none(source_model, deleted["global_id"])
    assert deleted_entity is not None
    assert by_guid_or_none(revised_model, deleted["global_id"]) is None
    assert deleted_entity.is_a() == deleted["entity_type"]
    assert entity_snapshot(deleted_entity) == deleted["old_value"]
    assert element_location(deleted_entity) == deleted["location"]

    source_value = get_pset(
        source_model.by_guid(modified["global_id"]),
        modified["field"]["property_set"],
        modified["field"]["name"],
    )
    revised_value = get_pset(
        revised_model.by_guid(modified["global_id"]),
        modified["field"]["property_set"],
        modified["field"]["name"],
    )
    assert source_value == modified["old_value"]
    assert revised_value == modified["new_value"]
    assert element_location(
        revised_model.by_guid(modified["global_id"])
    ) == modified["location"]

    print(
        json.dumps(
            {
                "status": "PASS",
                "records_validated": len(ground_truth["changes"]),
                "added": diff["added"],
                "deleted": diff["deleted"],
                "property_modified": list(diff["changed"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
