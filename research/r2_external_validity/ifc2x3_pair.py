"""Prepare a path-free, preregistered IFC2X3 controlled revision pair."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import ifcopenshell
import ifcopenshell.api
from ifcopenshell.util.element import copy_deep, get_container, get_pset

from research.r1_traceability.traceability import sha256_file, write_json

from .preflight import _privacy_violations


PROTOCOL_ID = "r2-ifc2x3-controlled-pair-0.1.0"
PLAN_NAME = "ifc2x3-pair-plan.json"
LEDGER_NAME = "change-ledger.csv"
FIELD_MAP_NAME = "cross-schema-field-map.json"
REVISED_NAME = "revised.ifc"
BUILD_REPORT_NAME = "build-report.json"
IFC_GUID = __import__("re").compile(r"^[0-3][0-9A-Za-z_$]{21}$")
LEDGER_FIELDS = (
    "case_id",
    "operation",
    "entity_type",
    "source_global_id",
    "revised_global_id",
    "template_global_id",
    "property_set",
    "property_name",
    "old_value_json",
    "new_value_json",
    "expected_ifcdiff_section",
)


def _signature(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, getattr(stat, "st_ino", 0)


def _load_model(path: Path) -> tuple[ifcopenshell.file, str, tuple[int, int, int, int]]:
    path = path.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".ifc":
        raise ValueError("source must resolve to one IFC file")
    before = _signature(path)
    digest_before = sha256_file(path)
    model = ifcopenshell.open(path)
    after = _signature(path)
    if before != after or digest_before != sha256_file(path):
        raise ValueError("source changed while being inspected")
    if model.schema != "IFC2X3":
        raise ValueError("this research protocol requires exact IFC2X3")
    roots = model.by_type("IfcRoot")
    ids = [getattr(root, "GlobalId", None) for root in roots]
    if any(not isinstance(value, str) or not IFC_GUID.fullmatch(value) for value in ids):
        raise ValueError("IfcRoot GlobalIds must be complete and valid")
    if len(ids) != len(set(ids)):
        raise ValueError("IfcRoot GlobalIds must be unique")
    return model, digest_before, before


def _sorted_type(model: ifcopenshell.file, entity_type: str, excluded: set[str]) -> list[Any]:
    return sorted(
        (
            entity
            for entity in model.by_type(entity_type)
            if entity.is_a() == entity_type
            and isinstance(getattr(entity, "GlobalId", None), str)
            and entity.GlobalId not in excluded
        ),
        key=lambda entity: entity.GlobalId,
    )


def _take(model: ifcopenshell.file, entity_type: str, excluded: set[str]) -> Any:
    candidates = _sorted_type(model, entity_type, excluded)
    if not candidates:
        raise ValueError(f"no unused {entity_type} candidate is available")
    selected = candidates[0]
    excluded.add(selected.GlobalId)
    return selected


def _take_boolean_property(
    model: ifcopenshell.file,
    entity_type: str,
    pset_name: str,
    property_name: str,
    excluded: set[str],
) -> tuple[Any, bool]:
    for entity in _sorted_type(model, entity_type, excluded):
        value = get_pset(entity, pset_name, property_name, should_inherit=False)
        if isinstance(value, bool):
            excluded.add(entity.GlobalId)
            return entity, value
    raise ValueError(f"no boolean {entity_type}.{pset_name}.{property_name} candidate")


def _new_guid(source_digest: str, case_id: str) -> str:
    material = f"bimchange:r2-ifc2x3:{source_digest}:{case_id}"
    return ifcopenshell.guid.compress(uuid5(NAMESPACE_URL, material).hex)


def _json_cell(value: Any) -> str:
    return "" if value is None else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path.name}")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=LEDGER_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _field_map() -> dict[str, Any]:
    return {
        "protocol_id": PROTOCOL_ID,
        "status": "PREREGISTERED_BEFORE_DIFF",
        "mappings": [
            {"field": "global_id", "ifc4_source": "IfcRoot.GlobalId", "ifc2x3_source": "IfcRoot.GlobalId", "limit": "same-schema identity only"},
            {"field": "entity_type", "ifc4_source": "entity.is_a()", "ifc2x3_source": "entity.is_a()", "limit": "retain schema-specific subtype names"},
            {"field": "location", "ifc4_source": "IfcRelContainedInSpatialStructure", "ifc2x3_source": "IfcRelContainedInSpatialStructure", "limit": "null when explicit containment is absent; no inference"},
            {"field": "field", "ifc4_source": "structured IfcDiff property path", "ifc2x3_source": "preregistered structured IfcDiff property path", "limit": "must be observed after pair gate; value modifications only"},
            {"field": "old_value/new_value", "ifc4_source": "IfcDiff leaf plus both IFC roles", "ifc2x3_source": "IfcDiff leaf plus both IFC roles", "limit": "compare unwrapped JSON scalars, not IFC measure-type equivalence"},
            {"field": "predefined_type", "ifc4_source": "entity attribute when present", "ifc2x3_source": "entity attribute when present", "limit": "retain null when the IFC2X3 entity has no such attribute"},
            {"field": "change_id", "ifc4_source": "versioned product/research rule", "ifc2x3_source": "R2 research-only rule", "limit": "not interchangeable with product IDs"},
            {"field": "artifact_schema", "ifc4_source": "frozen product/R1 contracts", "ifc2x3_source": "independent R2 research artifact", "limit": "does not relax the product IFC4 guard"},
        ],
        "allowed_interpretation": "same-schema controlled-pair research only",
        "product_ifc2x3_support_claim": "NOT_PERMITTED",
        "model_calls_made": 0,
    }


def plan_pair(source: Path, output: Path) -> dict[str, Any]:
    """Freeze exact candidates and expectations without writing an IFC or running IfcDiff."""
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError("preregistration output directory already exists")
    output.mkdir(parents=True)
    model, source_digest, source_signature = _load_model(source)
    excluded: set[str] = set()
    add_beam = _take(model, "IfcBeam", excluded)
    add_column = _take(model, "IfcColumn", excluded)
    delete_wall = _take(model, "IfcWallStandardCase", excluded)
    delete_slab = _take(model, "IfcSlab", excluded)
    property_beam, beam_old = _take_boolean_property(
        model, "IfcBeam", "Pset_BeamCommon", "IsExternal", excluded
    )
    property_column, column_old = _take_boolean_property(
        model, "IfcColumn", "Pset_ColumnCommon", "IsExternal", excluded
    )
    negative = _take(model, "IfcDoor", excluded)
    rows = [
        {"case_id": "IFC2X3-A01", "operation": "added", "entity_type": "IfcBeam", "source_global_id": "", "revised_global_id": _new_guid(source_digest, "IFC2X3-A01"), "template_global_id": add_beam.GlobalId, "property_set": "", "property_name": "", "old_value_json": "", "new_value_json": "", "expected_ifcdiff_section": "added"},
        {"case_id": "IFC2X3-A02", "operation": "added", "entity_type": "IfcColumn", "source_global_id": "", "revised_global_id": _new_guid(source_digest, "IFC2X3-A02"), "template_global_id": add_column.GlobalId, "property_set": "", "property_name": "", "old_value_json": "", "new_value_json": "", "expected_ifcdiff_section": "added"},
        {"case_id": "IFC2X3-D01", "operation": "deleted", "entity_type": "IfcWallStandardCase", "source_global_id": delete_wall.GlobalId, "revised_global_id": "", "template_global_id": "", "property_set": "", "property_name": "", "old_value_json": "", "new_value_json": "", "expected_ifcdiff_section": "deleted"},
        {"case_id": "IFC2X3-D02", "operation": "deleted", "entity_type": "IfcSlab", "source_global_id": delete_slab.GlobalId, "revised_global_id": "", "template_global_id": "", "property_set": "", "property_name": "", "old_value_json": "", "new_value_json": "", "expected_ifcdiff_section": "deleted"},
        {"case_id": "IFC2X3-P01", "operation": "property_modified", "entity_type": "IfcBeam", "source_global_id": property_beam.GlobalId, "revised_global_id": property_beam.GlobalId, "template_global_id": "", "property_set": "Pset_BeamCommon", "property_name": "IsExternal", "old_value_json": _json_cell(beam_old), "new_value_json": _json_cell(not beam_old), "expected_ifcdiff_section": "changed"},
        {"case_id": "IFC2X3-P02", "operation": "property_modified", "entity_type": "IfcColumn", "source_global_id": property_column.GlobalId, "revised_global_id": property_column.GlobalId, "template_global_id": "", "property_set": "Pset_ColumnCommon", "property_name": "IsExternal", "old_value_json": _json_cell(column_old), "new_value_json": _json_cell(not column_old), "expected_ifcdiff_section": "changed"},
    ]
    _write_csv(output / LEDGER_NAME, rows)
    field_map = _field_map()
    write_json(output / FIELD_MAP_NAME, field_map)
    plan = {
        "protocol_id": PROTOCOL_ID,
        "status": "FROZEN_BEFORE_REVISION_AND_DIFF",
        "source": {
            "role": "ifc2x3_source.ifc",
            "sha256": source_digest,
            "file_size_bytes": source_signature[0],
            "ifc_schema": model.schema,
            "element_count": len(model.by_type("IfcElement")),
            "root_count": len(model.by_type("IfcRoot")),
        },
        "operation_counts": {"added": 2, "deleted": 2, "property_modified": 2},
        "operations": rows,
        "negative_control": {"global_id": negative.GlobalId, "entity_type": negative.is_a()},
        "artifacts": {
            LEDGER_NAME: sha256_file(output / LEDGER_NAME),
            FIELD_MAP_NAME: sha256_file(output / FIELD_MAP_NAME),
        },
        "ifcdiff_executed": False,
        "model_calls_made": 0,
    }
    if _privacy_violations(plan) or _privacy_violations(field_map):
        raise ValueError("preregistration artifact crossed the path or credential boundary")
    write_json(output / PLAN_NAME, plan)
    return plan


def _read_ledger(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
            raise ValueError("ledger columns differ from the frozen contract")
        rows = list(reader)
    if len(rows) != 6 or len({row["case_id"] for row in rows}) != 6:
        raise ValueError("ledger must contain six unique preregistered changes")
    return rows


def _property_set(model: ifcopenshell.file, entity: Any, name: str) -> Any:
    data = get_pset(entity, name, should_inherit=False)
    if not isinstance(data, dict) or not isinstance(data.get("id"), int):
        raise ValueError(f"property set is missing: {name}")
    return model.by_id(data["id"])


def build_revision(source: Path, preregistration: Path, output: Path) -> dict[str, Any]:
    """Build one new IFC2X3 revision without overwriting any existing path."""
    source = source.expanduser().resolve()
    preregistration = preregistration.expanduser().resolve()
    output = output.expanduser().resolve()
    if output.exists():
        raise FileExistsError("revision output directory already exists")
    output.mkdir(parents=True)
    revised_path = output / REVISED_NAME
    if revised_path.resolve() == source:
        raise ValueError("revised target must differ from the source")
    plan = json.loads((preregistration / PLAN_NAME).read_text(encoding="utf-8"))
    rows = _read_ledger(preregistration / LEDGER_NAME)
    if plan.get("protocol_id") != PROTOCOL_ID or plan.get("ifcdiff_executed") is not False:
        raise ValueError("plan is not the frozen pre-diff protocol")
    if plan["artifacts"].get(LEDGER_NAME) != sha256_file(preregistration / LEDGER_NAME):
        raise ValueError("ledger hash differs from the frozen plan")
    if plan["artifacts"].get(FIELD_MAP_NAME) != sha256_file(preregistration / FIELD_MAP_NAME):
        raise ValueError("field-map hash differs from the frozen plan")
    model, source_digest, source_signature = _load_model(source)
    if source_digest != plan["source"]["sha256"]:
        raise ValueError("source hash differs from the frozen plan")
    for row in rows:
        operation = row["operation"]
        if operation == "property_modified":
            entity = model.by_guid(row["source_global_id"])
            old_value = get_pset(entity, row["property_set"], row["property_name"], should_inherit=False)
            if _json_cell(old_value) != row["old_value_json"]:
                raise ValueError(f"property precondition drifted for {row['case_id']}")
            ifcopenshell.api.run(
                "pset.edit_pset",
                model,
                pset=_property_set(model, entity, row["property_set"]),
                properties={row["property_name"]: json.loads(row["new_value_json"])},
            )
        elif operation == "deleted":
            model.remove(model.by_guid(row["source_global_id"]))
        elif operation == "added":
            clone = copy_deep(model, model.by_guid(row["template_global_id"]))
            clone.GlobalId = row["revised_global_id"]
            if hasattr(clone, "Name"):
                clone.Name = f"R2 IFC2X3 controlled addition {row['case_id']}"
            if hasattr(clone, "Tag"):
                clone.Tag = row["case_id"]
        else:
            raise ValueError(f"unsupported operation in ledger: {operation}")
    temporary = revised_path.with_name(f".{revised_path.name}.{uuid4().hex}.tmp")
    try:
        model.write(str(temporary))
        temporary.replace(revised_path)
    finally:
        temporary.unlink(missing_ok=True)
    if _signature(source) != source_signature or sha256_file(source) != source_digest:
        raise ValueError("source changed during revision construction")
    report = verify_pair(source, revised_path, preregistration)
    write_json(output / BUILD_REPORT_NAME, report)
    return report


def _snapshot(entity: Any) -> dict[str, Any]:
    container = get_container(entity)
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": getattr(entity, "Name", None),
        "tag": getattr(entity, "Tag", None),
        "predefined_type": getattr(entity, "PredefinedType", None),
        "container_global_id": getattr(container, "GlobalId", None) if container else None,
    }


def _by_guid_or_none(model: ifcopenshell.file, global_id: str) -> Any | None:
    try:
        return model.by_guid(global_id)
    except RuntimeError:
        return None


def verify_pair(source: Path, revised: Path, preregistration: Path) -> dict[str, Any]:
    source_model, source_digest, _ = _load_model(source)
    revised_model, revised_digest, _ = _load_model(revised)
    preregistration = preregistration.expanduser().resolve()
    plan = json.loads((preregistration / PLAN_NAME).read_text(encoding="utf-8"))
    rows = _read_ledger(preregistration / LEDGER_NAME)
    checks: dict[str, bool] = {
        "source_hash_matches_plan": source_digest == plan["source"]["sha256"],
        "source_and_revised_are_distinct": source_digest != revised_digest,
        "ledger_hash_matches_plan": sha256_file(preregistration / LEDGER_NAME) == plan["artifacts"][LEDGER_NAME],
        "field_map_hash_matches_plan": sha256_file(preregistration / FIELD_MAP_NAME) == plan["artifacts"][FIELD_MAP_NAME],
    }
    for row in rows:
        case = row["case_id"]
        if row["operation"] == "added":
            checks[f"{case}_state"] = (
                _by_guid_or_none(source_model, row["revised_global_id"]) is None
                and _by_guid_or_none(revised_model, row["revised_global_id"]) is not None
                and revised_model.by_guid(row["revised_global_id"]).is_a() == row["entity_type"]
            )
        elif row["operation"] == "deleted":
            checks[f"{case}_state"] = (
                source_model.by_guid(row["source_global_id"]).is_a() == row["entity_type"]
                and _by_guid_or_none(revised_model, row["source_global_id"]) is None
            )
        else:
            old_entity = source_model.by_guid(row["source_global_id"])
            new_entity = revised_model.by_guid(row["revised_global_id"])
            checks[f"{case}_state"] = (
                _json_cell(get_pset(old_entity, row["property_set"], row["property_name"], should_inherit=False)) == row["old_value_json"]
                and _json_cell(get_pset(new_entity, row["property_set"], row["property_name"], should_inherit=False)) == row["new_value_json"]
            )
    control_id = plan["negative_control"]["global_id"]
    checks["negative_control_unchanged"] = _snapshot(source_model.by_guid(control_id)) == _snapshot(revised_model.by_guid(control_id))
    revised_ids = [root.GlobalId for root in revised_model.by_type("IfcRoot")]
    checks["revised_root_guids_complete_and_unique"] = (
        all(isinstance(value, str) and IFC_GUID.fullmatch(value) for value in revised_ids)
        and len(revised_ids) == len(set(revised_ids))
    )
    checks["element_count_balanced"] = len(source_model.by_type("IfcElement")) == len(revised_model.by_type("IfcElement"))
    report = {
        "protocol_id": PROTOCOL_ID,
        "status": "READY_FOR_PREREGISTERED_DIFF" if all(checks.values()) else "FAIL",
        "checks": checks,
        "source": {"role": "ifc2x3_source.ifc", "sha256": source_digest, "ifc_schema": source_model.schema, "element_count": len(source_model.by_type("IfcElement"))},
        "revised": {"role": "ifc2x3_revised.ifc", "sha256": revised_digest, "ifc_schema": revised_model.schema, "element_count": len(revised_model.by_type("IfcElement"))},
        "operation_counts": plan["operation_counts"],
        "ifcdiff_executed": False,
        "product_ifc2x3_support_claim": "NOT_PERMITTED",
        "privacy_violation_count": 0,
        "model_calls_made": 0,
    }
    report["privacy_violation_count"] = _privacy_violations(report)
    if report["privacy_violation_count"]:
        report["status"] = "FAIL"
    return report


def verify_reproducibility(
    source: Path, revised_a: Path, revised_b: Path, preregistration: Path
) -> dict[str, Any]:
    first = verify_pair(source, revised_a, preregistration)
    second = verify_pair(source, revised_b, preregistration)
    byte_identical = Path(revised_a).read_bytes() == Path(revised_b).read_bytes()
    return {
        "protocol_id": PROTOCOL_ID,
        "status": "READY_FOR_PREREGISTERED_DIFF"
        if first["status"] == second["status"] == "READY_FOR_PREREGISTERED_DIFF" and byte_identical
        else "FAIL",
        "clean_builds_passed": int(first["status"] == "READY_FOR_PREREGISTERED_DIFF") + int(second["status"] == "READY_FOR_PREREGISTERED_DIFF"),
        "clean_revisions_byte_identical": byte_identical,
        "revised_sha256": sha256_file(Path(revised_a)) if byte_identical else None,
        "ifcdiff_executed": False,
        "privacy_violation_count": 0,
        "model_calls_made": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--source", required=True, type=Path)
    plan.add_argument("--output", required=True, type=Path)
    build = subparsers.add_parser("build")
    build.add_argument("--source", required=True, type=Path)
    build.add_argument("--preregistration", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    verify = subparsers.add_parser("verify-reproducibility")
    verify.add_argument("--source", required=True, type=Path)
    verify.add_argument("--preregistration", required=True, type=Path)
    verify.add_argument("--revised-a", required=True, type=Path)
    verify.add_argument("--revised-b", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        result = plan_pair(args.source, args.output)
    elif args.command == "build":
        result = build_revision(args.source, args.preregistration, args.output)
    else:
        result = verify_reproducibility(args.source, args.revised_a, args.revised_b, args.preregistration)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
