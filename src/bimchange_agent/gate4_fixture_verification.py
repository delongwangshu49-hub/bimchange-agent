"""Independent offline verification for the Gate 4 held-out IFC fixture."""

from __future__ import annotations

import json
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import ifcopenshell
from ifcopenshell.util.element import get_container, get_pset
from jsonschema import Draft202012Validator

from bimchange_agent.gate4_fixture import generate_artifacts, sha256
from bimchange_agent.gate4_foundation import (
    REPOSITORY_ROOT,
    load_foundation_config,
    verify_gate4_foundation,
)


EXPECTED_DATASET_ID = "gate4-controlled-heldout-v0.1.0"
EXPECTED_STOREYS = {"Ground Floor", "Level 01", "Roof"}
EXPECTED_ENTITY_TYPES = {"IfcBeam", "IfcColumn", "IfcWall", "IfcSlab"}
EXPECTED_CHANGE_TYPES = {"added", "deleted", "property_modified"}
EXPECTED_MATRIX = {
    ("IfcBeam", "Ground Floor"): "added",
    ("IfcColumn", "Ground Floor"): "property_modified",
    ("IfcWall", "Ground Floor"): "deleted",
    ("IfcSlab", "Ground Floor"): "added",
    ("IfcBeam", "Level 01"): "deleted",
    ("IfcColumn", "Level 01"): "added",
    ("IfcWall", "Level 01"): "property_modified",
    ("IfcSlab", "Level 01"): "deleted",
    ("IfcBeam", "Roof"): "property_modified",
    ("IfcColumn", "Roof"): "deleted",
    ("IfcWall", "Roof"): "added",
    ("IfcSlab", "Roof"): "property_modified",
}
EXPECTED_PROPERTY_CHANGES = {
    ("IfcColumn", "Ground Floor"): (
        "Pset_ColumnCommon",
        "IsExternal",
        True,
        False,
    ),
    ("IfcWall", "Level 01"): (
        "Pset_WallCommon",
        "FireRating",
        "60",
        "90",
    ),
    ("IfcBeam", "Roof"): (
        "Pset_BeamCommon",
        "LoadBearing",
        False,
        True,
    ),
    ("IfcSlab", "Roof"): (
        "Pset_SlabCommon",
        "LoadBearing",
        False,
        True,
    ),
}
EXPECTED_PSETS = {
    "IfcBeam": ("Pset_BeamCommon", "LoadBearing"),
    "IfcColumn": ("Pset_ColumnCommon", "IsExternal"),
    "IfcWall": ("Pset_WallCommon", "FireRating"),
    "IfcSlab": ("Pset_SlabCommon", "LoadBearing"),
}
NEUTRALITY_PATTERN = re.compile(
    r"(?:added|deleted|modified|held[-_ ]?out|gate[34]-q\d+|answer)",
    re.IGNORECASE,
)
DIFF_RELATIVE_PATH = (
    "evals/results/held_out/gate4-controlled-heldout-v0.1.0/ifcdiff.json"
)


def _by_guid_or_none(
    model: ifcopenshell.file, global_id: str
) -> ifcopenshell.entity_instance | None:
    try:
        return model.by_guid(global_id)
    except RuntimeError:
        return None


def _reference(entity: ifcopenshell.entity_instance) -> dict[str, Any]:
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": entity.Name,
    }


def _location(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    direct_relations = list(element.ContainedInStructure)
    assert len(direct_relations) == 1
    container = direct_relations[0].RelatingStructure
    assert container.is_a("IfcBuildingStorey")
    assert get_container(element, should_get_direct=True) == container
    reference = _reference(container)
    return {"spatial_container": reference, "building_storey": reference.copy()}


def _snapshot(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    return {"name": element.Name, "tag": element.Tag}


def _element_signature(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    pset_name, property_name = EXPECTED_PSETS[element.is_a()]
    return {
        "entity_type": element.is_a(),
        "global_id": element.GlobalId,
        "name": element.Name,
        "tag": element.Tag,
        "location": _location(element),
        "property_set": pset_name,
        "property_name": property_name,
        "property_value": get_pset(element, pset_name, property_name),
    }


def _validate_spatial_model(model: ifcopenshell.file) -> None:
    assert model.schema == "IFC4"
    assert len(model.by_type("IfcProject")) == 1
    assert len(model.by_type("IfcSite")) == 1
    assert len(model.by_type("IfcBuilding")) == 1
    storeys = model.by_type("IfcBuildingStorey")
    assert {storey.Name for storey in storeys} == EXPECTED_STOREYS
    assert len(storeys) == 3

    roots = model.by_type("IfcRoot")
    global_ids = [root.GlobalId for root in roots]
    assert all(global_ids)
    assert len(global_ids) == len(set(global_ids))

    elements = model.by_type("IfcElement")
    assert len(elements) == 48
    assert {element.is_a() for element in elements} == EXPECTED_ENTITY_TYPES
    for element in elements:
        assert _location(element)["building_storey"]["name"] in EXPECTED_STOREYS
        assert element.Name and not NEUTRALITY_PATTERN.search(element.Name)
        assert element.Tag and not NEUTRALITY_PATTERN.search(element.Tag)
        pset_name, property_name = EXPECTED_PSETS[element.is_a()]
        assert get_pset(element, pset_name, property_name) is not None


def _validate_distribution(
    source_model: ifcopenshell.file,
    revised_model: ifcopenshell.file,
    records: list[dict[str, Any]],
) -> None:
    source_counts = Counter(
        (element.is_a(), _location(element)["building_storey"]["name"])
        for element in source_model.by_type("IfcElement")
    )
    revised_counts = Counter(
        (element.is_a(), _location(element)["building_storey"]["name"])
        for element in revised_model.by_type("IfcElement")
    )
    assert set(source_counts) == set(EXPECTED_MATRIX)
    assert all(count == 4 for count in source_counts.values())
    for key, change_type in EXPECTED_MATRIX.items():
        expected_revised = 5 if change_type == "added" else 3 if change_type == "deleted" else 4
        assert revised_counts[key] == expected_revised

    matrix = {
        (record["entity_type"], record["location"]["building_storey"]["name"]): record[
            "change_type"
        ]
        for record in records
    }
    assert matrix == EXPECTED_MATRIX


def _validate_contract(
    ledger: dict[str, Any], change_records: dict[str, Any]
) -> list[dict[str, Any]]:
    assert set(ledger) == {
        "schema_version",
        "dataset_id",
        "split",
        "ifc_schema",
        "source_ifc",
        "source_sha256",
        "revised_ifc",
        "revised_sha256",
        "operations",
    }
    assert ledger["schema_version"] == "0.1.0"
    assert ledger["dataset_id"] == EXPECTED_DATASET_ID
    assert ledger["split"] == "held_out"
    assert ledger["ifc_schema"] == "IFC4"

    schema_path = REPOSITORY_ROOT / change_records["schema"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(change_records)

    records = change_records["changes"]
    assert len(records) == 12
    assert len({record["change_id"] for record in records}) == 12
    assert len({record["global_id"] for record in records}) == 12
    assert Counter(record["change_type"] for record in records) == {
        change_type: 4 for change_type in EXPECTED_CHANGE_TYPES
    }
    assert Counter(record["entity_type"] for record in records) == {
        entity_type: 3 for entity_type in EXPECTED_ENTITY_TYPES
    }
    assert Counter(
        record["location"]["building_storey"]["name"] for record in records
    ) == {storey: 4 for storey in EXPECTED_STOREYS}

    ledger_core = ledger["operations"]
    record_core = [
        {key: value for key, value in record.items() if key != "evidence"}
        for record in records
    ]
    assert ledger_core == record_core
    for record in records:
        assert record["evidence"]["reference_source"] == (
            "controlled_revision_generator"
        )
        assert record["evidence"]["detector"] == "IfcDiff 0.8.5"
        assert record["evidence"]["result_file"] == DIFF_RELATIVE_PATH
    return records


def _validate_records_against_models(
    records: list[dict[str, Any]],
    source_model: ifcopenshell.file,
    revised_model: ifcopenshell.file,
) -> None:
    for record in records:
        source_entity = _by_guid_or_none(source_model, record["global_id"])
        revised_entity = _by_guid_or_none(revised_model, record["global_id"])
        key = (
            record["entity_type"],
            record["location"]["building_storey"]["name"],
        )
        if record["change_type"] == "added":
            assert source_entity is None and revised_entity is not None
            assert revised_entity.is_a() == record["entity_type"]
            assert _snapshot(revised_entity) == record["new_value"]
            assert record["old_value"] is None and record["field"] is None
            assert _location(revised_entity) == record["location"]
        elif record["change_type"] == "deleted":
            assert source_entity is not None and revised_entity is None
            assert source_entity.is_a() == record["entity_type"]
            assert _snapshot(source_entity) == record["old_value"]
            assert record["new_value"] is None and record["field"] is None
            assert _location(source_entity) == record["location"]
        else:
            assert source_entity is not None and revised_entity is not None
            assert source_entity.is_a() == revised_entity.is_a() == record["entity_type"]
            expected = EXPECTED_PROPERTY_CHANGES[key]
            assert record["field"] == {
                "kind": "property",
                "property_set": expected[0],
                "name": expected[1],
            }
            assert (record["old_value"], record["new_value"]) == expected[2:]
            assert get_pset(source_entity, expected[0], expected[1]) == expected[2]
            assert get_pset(revised_entity, expected[0], expected[1]) == expected[3]
            assert _location(source_entity) == _location(revised_entity) == record["location"]


def _validate_unchanged_elements(
    records: list[dict[str, Any]],
    source_model: ifcopenshell.file,
    revised_model: ifcopenshell.file,
) -> int:
    changed_ids = {record["global_id"] for record in records}
    source_ids = {element.GlobalId for element in source_model.by_type("IfcElement")}
    revised_ids = {element.GlobalId for element in revised_model.by_type("IfcElement")}
    unchanged_ids = (source_ids & revised_ids) - changed_ids
    assert len(unchanged_ids) == 40
    for global_id in unchanged_ids:
        assert _element_signature(source_model.by_guid(global_id)) == _element_signature(
            revised_model.by_guid(global_id)
        )
    return len(unchanged_ids)


def _validate_ifcdiff(diff: dict[str, Any], records: list[dict[str, Any]]) -> None:
    expected_added = {
        record["global_id"] for record in records if record["change_type"] == "added"
    }
    expected_deleted = {
        record["global_id"] for record in records if record["change_type"] == "deleted"
    }
    expected_changed = {
        record["global_id"]: record
        for record in records
        if record["change_type"] == "property_modified"
    }
    assert set(diff) == {"added", "deleted", "changed"}
    assert set(diff["added"]) == expected_added and len(diff["added"]) == 4
    assert set(diff["deleted"]) == expected_deleted and len(diff["deleted"]) == 4
    assert set(diff["changed"]) == set(expected_changed)
    for global_id, record in expected_changed.items():
        field = record["field"]
        property_path = f"root['{field['property_set']}']['{field['name']}']"
        assert diff["changed"][global_id] == {
            "properties_changed": {
                "values_changed": {
                    property_path: {
                        "new_value": record["new_value"],
                        "old_value": record["old_value"],
                    }
                }
            }
        }


def _validate_clean_regeneration(
    production_root: Path, logical_paths: dict[str, str]
) -> None:
    keys = ("source_ifc", "revised_ifc", "operation_ledger", "change_records")
    with tempfile.TemporaryDirectory(prefix="bimchange-g4-clean-a-") as first_dir:
        with tempfile.TemporaryDirectory(prefix="bimchange-g4-clean-b-") as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            generate_artifacts(first)
            generate_artifacts(second)
            for key in keys:
                production_bytes = (production_root / logical_paths[key]).read_bytes()
                first_bytes = (first / logical_paths[key]).read_bytes()
                second_bytes = (second / logical_paths[key]).read_bytes()
                assert production_bytes == first_bytes == second_bytes


def verify_production_artifacts() -> dict[str, Any]:
    """Guard, then verify every currently implemented held-out fixture artifact."""
    foundation = verify_gate4_foundation()
    config = load_foundation_config()
    logical_paths = dict(config["gate4_paths"])
    source_path = REPOSITORY_ROOT / logical_paths["source_ifc"]
    revised_path = REPOSITORY_ROOT / logical_paths["revised_ifc"]
    ledger_path = REPOSITORY_ROOT / logical_paths["operation_ledger"]
    records_path = REPOSITORY_ROOT / logical_paths["change_records"]
    diff_path = REPOSITORY_ROOT / DIFF_RELATIVE_PATH

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    change_records = json.loads(records_path.read_text(encoding="utf-8"))
    diff = json.loads(diff_path.read_text(encoding="utf-8"))
    assert sha256(source_path) == ledger["source_sha256"]
    assert sha256(revised_path) == ledger["revised_sha256"]
    assert change_records["source_sha256"] == ledger["source_sha256"]
    assert change_records["revised_sha256"] == ledger["revised_sha256"]
    assert change_records["source_ifc"] == ledger["source_ifc"]
    assert change_records["revised_ifc"] == ledger["revised_ifc"]

    source_model = ifcopenshell.open(source_path)
    revised_model = ifcopenshell.open(revised_path)
    assert source_model.header.file_name.time_stamp == "2026-08-08T00:00:00"
    assert revised_model.header.file_name.time_stamp == "2026-08-08T00:00:00"
    _validate_spatial_model(source_model)
    _validate_spatial_model(revised_model)
    records = _validate_contract(ledger, change_records)
    _validate_distribution(source_model, revised_model, records)
    _validate_records_against_models(records, source_model, revised_model)
    unchanged_count = _validate_unchanged_elements(
        records, source_model, revised_model
    )
    _validate_ifcdiff(diff, records)
    _validate_clean_regeneration(REPOSITORY_ROOT, logical_paths)

    return {
        "status": "PASS",
        "foundation_status": foundation["status"],
        "dataset_id": EXPECTED_DATASET_ID,
        "source_sha256": ledger["source_sha256"],
        "revised_sha256": ledger["revised_sha256"],
        "source_element_count": len(source_model.by_type("IfcElement")),
        "revised_element_count": len(revised_model.by_type("IfcElement")),
        "unchanged_element_count": unchanged_count,
        "change_count": len(records),
        "change_type_counts": dict(Counter(r["change_type"] for r in records)),
        "entity_type_counts": dict(Counter(r["entity_type"] for r in records)),
        "storey_counts": dict(
            Counter(r["location"]["building_storey"]["name"] for r in records)
        ),
        "ifcdiff_exact_change_count": (
            len(diff["added"]) + len(diff["deleted"]) + len(diff["changed"])
        ),
        "clean_regeneration_byte_identical": True,
        "held_out_artifacts_read": True,
        "model_calls_made": 0,
    }
