"""Evaluate a preregistered IFC2X3 pair without changing the product boundary."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from uuid import uuid4

import ifcopenshell
from ifcdiff import IfcDiff, __version__ as ifcdiff_version
from ifcopenshell.util.element import get_container, get_pset

from research.r1_traceability.traceability import (
    canonical_json_bytes,
    digest_value,
    sha256_file,
    strict_load_json,
    write_json,
)

from .ifc2x3_pair import (
    FIELD_MAP_NAME,
    LEDGER_FIELDS,
    LEDGER_NAME,
    PLAN_NAME,
    PROTOCOL_ID,
    _load_model,
    verify_pair,
)
from .preflight import _privacy_violations


EVALUATION_ID = "r2-ifc2x3-controlled-diff-0.1.0"
RAW_NAME = "ifcdiff.json"
RECORDS_NAME = "ifc2x3-change-records.json"
RESULT_NAME = "ifc2x3-diff-evaluation.json"


def _read_ledger(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
            raise ValueError("ledger columns differ from the frozen contract")
        return list(reader)


def _parse_cell(value: str) -> Any:
    return None if value == "" else json.loads(value)


def _reference(entity: Any | None) -> dict[str, Any] | None:
    if entity is None:
        return None
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": getattr(entity, "Name", None),
    }


def _location(entity: Any) -> dict[str, Any]:
    container = get_container(entity)
    storey = container if container is not None and container.is_a("IfcBuildingStorey") else None
    return {
        "spatial_container": _reference(container),
        "building_storey": _reference(storey),
    }


def _snapshot(entity: Any) -> dict[str, Any]:
    return {
        "name": getattr(entity, "Name", None),
        "tag": getattr(entity, "Tag", None),
        "predefined_type": getattr(entity, "PredefinedType", None),
    }


def _property_path(row: dict[str, str]) -> str:
    pset = row["property_set"].replace("'", "\\'")
    name = row["property_name"].replace("'", "\\'")
    return f"root['{pset}']['{name}']"


def _run_ifcdiff(source_model: Any, revised_model: Any, output: Path) -> dict[str, Any]:
    detector = IfcDiff(
        source_model,
        revised_model,
        relationships=["property"],
        is_shallow=False,
    )
    temporary = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
    try:
        with redirect_stdout(io.StringIO()):
            detector.diff()
            detector.export(str(temporary))
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return strict_load_json(output)


def _raw_deviations(raw: dict[str, Any], rows: list[dict[str, str]]) -> list[str]:
    expected_added = {
        row["revised_global_id"] for row in rows if row["operation"] == "added"
    }
    expected_deleted = {
        row["source_global_id"] for row in rows if row["operation"] == "deleted"
    }
    expected_properties = {
        row["source_global_id"]: {
            "path": _property_path(row),
            "old_value": _parse_cell(row["old_value_json"]),
            "new_value": _parse_cell(row["new_value_json"]),
        }
        for row in rows
        if row["operation"] == "property_modified"
    }
    deviations: list[str] = []
    added = raw.get("added")
    deleted = raw.get("deleted")
    changed = raw.get("changed")
    if not isinstance(added, list) or len(added) != len(set(added)) or set(added) != expected_added:
        deviations.append("added_set_differs_from_preregistration")
    if not isinstance(deleted, list) or len(deleted) != len(set(deleted)) or set(deleted) != expected_deleted:
        deviations.append("deleted_set_differs_from_preregistration")
    if not isinstance(changed, dict) or set(changed) != set(expected_properties):
        deviations.append("changed_set_differs_from_preregistration")
        return deviations
    for global_id, expected in expected_properties.items():
        flags = changed[global_id]
        if not isinstance(flags, dict) or set(flags) != {"properties_changed"}:
            deviations.append(f"{global_id}:unexpected_change_flags")
            continue
        property_diff = flags["properties_changed"]
        if not isinstance(property_diff, dict) or set(property_diff) != {"values_changed"}:
            deviations.append(f"{global_id}:unexpected_property_categories")
            continue
        values_changed = property_diff["values_changed"]
        if not isinstance(values_changed, dict) or set(values_changed) != {expected["path"]}:
            deviations.append(f"{global_id}:property_path_differs")
            continue
        leaf = values_changed[expected["path"]]
        if leaf != {"old_value": expected["old_value"], "new_value": expected["new_value"]}:
            deviations.append(f"{global_id}:property_values_differ")
    return deviations


def _record(row: dict[str, str], source_model: Any, revised_model: Any) -> dict[str, Any]:
    operation = row["operation"]
    if operation == "added":
        entity = revised_model.by_guid(row["revised_global_id"])
        location = _location(entity)
        field = None
        old_value = None
        new_value = _snapshot(entity)
        global_id = row["revised_global_id"]
        locator = {"section": "added", "global_id": global_id, "property_path": None}
    elif operation == "deleted":
        entity = source_model.by_guid(row["source_global_id"])
        location = _location(entity)
        field = None
        old_value = _snapshot(entity)
        new_value = None
        global_id = row["source_global_id"]
        locator = {"section": "deleted", "global_id": global_id, "property_path": None}
    else:
        old_entity = source_model.by_guid(row["source_global_id"])
        entity = revised_model.by_guid(row["revised_global_id"])
        old_value = get_pset(
            old_entity,
            row["property_set"],
            row["property_name"],
            should_inherit=False,
        )
        new_value = get_pset(
            entity,
            row["property_set"],
            row["property_name"],
            should_inherit=False,
        )
        location = _location(entity)
        field = {
            "kind": "property",
            "property_set": row["property_set"],
            "name": row["property_name"],
        }
        global_id = row["source_global_id"]
        locator = {
            "section": "changed",
            "global_id": global_id,
            "property_path": _property_path(row),
        }
    facts = {
        "change_type": operation,
        "entity_type": entity.is_a(),
        "global_id": global_id,
        "location": location,
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
    }
    return {
        "case_id": row["case_id"],
        **facts,
        "evidence": {
            "detector": f"IfcDiff {ifcdiff_version}",
            "result_role": RAW_NAME,
            "locator": locator,
        },
        "derived_facts_sha256": digest_value(facts),
    }


def evaluate_pair(
    source: Path,
    revised: Path,
    preregistration: Path,
    output: Path,
) -> dict[str, Any]:
    """Run the frozen detector only after the preregistered pair gate passes."""
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError("evaluation output directory already exists")
    output.mkdir(parents=True)
    pair_report = verify_pair(source, revised, preregistration)
    if pair_report["status"] != "READY_FOR_PREREGISTERED_DIFF":
        raise ValueError("the preregistered pair gate has not passed")
    preregistration = preregistration.expanduser().resolve()
    plan = strict_load_json(preregistration / PLAN_NAME)
    rows = _read_ledger(preregistration / LEDGER_NAME)
    if plan["artifacts"][FIELD_MAP_NAME] != sha256_file(preregistration / FIELD_MAP_NAME):
        raise ValueError("cross-schema field map drifted after preregistration")
    source_model, source_digest, _ = _load_model(source)
    revised_model, revised_digest, _ = _load_model(revised)
    raw = _run_ifcdiff(source_model, revised_model, output / RAW_NAME)
    deviations = _raw_deviations(raw, rows)
    records = [_record(row, source_model, revised_model) for row in rows]
    counts = Counter(record["change_type"] for record in records)
    artifact = {
        "protocol_id": EVALUATION_ID,
        "status": "PASS_CONTROLLED_IFC2X3_DIFF_ONLY" if not deviations else "FAIL",
        "scope": "one_authorised_preregistered_same_schema_ifc2x3_pair",
        "source": {"role": "ifc2x3_source.ifc", "sha256": source_digest, "ifc_schema": "IFC2X3"},
        "revised": {"role": "ifc2x3_revised.ifc", "sha256": revised_digest, "ifc_schema": "IFC2X3"},
        "detector": {"name": "IfcDiff", "version": ifcdiff_version, "relationships": ["property"], "is_shallow": False},
        "preregistration": {
            "plan_sha256": sha256_file(preregistration / PLAN_NAME),
            "ledger_sha256": sha256_file(preregistration / LEDGER_NAME),
            "field_map_sha256": sha256_file(preregistration / FIELD_MAP_NAME),
        },
        "summary": {
            "total": len(records),
            "added": counts["added"],
            "deleted": counts["deleted"],
            "property_modified": counts["property_modified"],
            "deviation_count": len(deviations),
        },
        "changes": records,
        "deviations": deviations,
        "product_ifc2x3_support_claim": "NOT_PERMITTED",
        "r1_ifc2x3_traceability_status": "NOT_RUN_REQUIRES_INDEPENDENT_ADAPTATION",
        "privacy_violation_count": 0,
        "model_calls_made": 0,
    }
    artifact["privacy_violation_count"] = _privacy_violations(artifact)
    if artifact["privacy_violation_count"]:
        artifact["status"] = "FAIL"
    write_json(output / RECORDS_NAME, artifact)
    result = {
        "protocol_id": EVALUATION_ID,
        "status": artifact["status"],
        "checks": {
            "pair_gate_passed": True,
            "detector_version_frozen": ifcdiff_version == "0.8.5",
            "raw_result_matches_preregistration": not deviations,
            "ledger_rows_normalized": len(records) == len(rows) == 6,
            "change_type_counts_match": counts == {"added": 2, "deleted": 2, "property_modified": 2},
            "source_hash_unchanged": sha256_file(Path(source)) == plan["source"]["sha256"],
        },
        "raw_result_sha256": sha256_file(output / RAW_NAME),
        "raw_result_canonical_sha256": hashlib.sha256(canonical_json_bytes(raw)).hexdigest(),
        "change_records_sha256": sha256_file(output / RECORDS_NAME),
        "change_records_canonical_sha256": hashlib.sha256(canonical_json_bytes(artifact)).hexdigest(),
        "summary": artifact["summary"],
        "deviations": deviations,
        "product_ifc2x3_support_claim": "NOT_PERMITTED",
        "r1_ifc2x3_traceability_status": "NOT_RUN_REQUIRES_INDEPENDENT_ADAPTATION",
        "privacy_violation_count": artifact["privacy_violation_count"],
        "model_calls_made": 0,
    }
    if not all(result["checks"].values()):
        result["status"] = "FAIL"
    write_json(output / RESULT_NAME, result)
    return result


def compare_evaluations(first: Path, second: Path) -> dict[str, Any]:
    first = Path(first)
    second = Path(second)
    raw_a = strict_load_json(first / RAW_NAME)
    raw_b = strict_load_json(second / RAW_NAME)
    result_a = strict_load_json(first / RESULT_NAME)
    result_b = strict_load_json(second / RESULT_NAME)
    result_a_without_raw_bytes = dict(result_a)
    result_b_without_raw_bytes = dict(result_b)
    result_a_without_raw_bytes.pop("raw_result_sha256", None)
    result_b_without_raw_bytes.pop("raw_result_sha256", None)
    matches = {
        "raw_bytes": (first / RAW_NAME).read_bytes() == (second / RAW_NAME).read_bytes(),
        "raw_canonical_semantics": digest_value(raw_a) == digest_value(raw_b),
        "change_records_bytes": (first / RECORDS_NAME).read_bytes()
        == (second / RECORDS_NAME).read_bytes(),
        "evaluation_semantics_excluding_raw_byte_digest": result_a_without_raw_bytes
        == result_b_without_raw_bytes,
    }
    passed = (
        matches["raw_canonical_semantics"]
        and matches["change_records_bytes"]
        and matches["evaluation_semantics_excluding_raw_byte_digest"]
    )
    return {
        "protocol_id": EVALUATION_ID,
        "status": "PASS_CONTROLLED_IFC2X3_DIFF_ONLY" if passed else "FAIL",
        "clean_evaluations": 2,
        "byte_identical": matches,
        "recorded_limitation": (
            None
            if matches["raw_bytes"]
            else "IfcDiff object-key order varied while canonical semantics stayed identical"
        ),
        "product_ifc2x3_support_claim": "NOT_PERMITTED",
        "r1_ifc2x3_traceability_status": "NOT_RUN_REQUIRES_INDEPENDENT_ADAPTATION",
        "model_calls_made": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--source", required=True, type=Path)
    evaluate.add_argument("--revised", required=True, type=Path)
    evaluate.add_argument("--preregistration", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--first", required=True, type=Path)
    compare.add_argument("--second", required=True, type=Path)
    compare.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = (
        evaluate_pair(args.source, args.revised, args.preregistration, args.output)
        if args.command == "evaluate"
        else compare_evaluations(args.first, args.second)
    )
    if args.command == "compare" and args.output is not None:
        if args.output.exists():
            raise FileExistsError("comparison output already exists")
        write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
