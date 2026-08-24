"""Stable product implementation for all bounded R3 semantics."""

from __future__ import annotations

import io
import json
from collections import Counter
from contextlib import redirect_stdout
from importlib.resources import files
from pathlib import Path
from typing import Any

from ifcdiff import IfcDiff, __version__ as ifcdiff_version
from jsonschema import Draft202012Validator

from .geometry_product_candidate import (
    CHANGE_RECORD_FILE_NAME as BASE_RECORD_FILE_NAME,
    RAW_DIFF_FILE_NAME,
    GeometryClassificationError,
    diff_ifc_pair_geometry_candidate,
)
from .product_core import (
    DEFAULT_LIMITS, ProductLimits, _change_id, _location, _open_stable_ifc,
    _require_ifc_path, _write_json, load_json, sha256,
)
from .r3_semantics import extrusion_dimension_change, relationship_change, tessellated_shape_change


SCHEMA_VERSION = "0.4.0"
SCHEMA_URI = "bimchange-agent://schemas/product-change-record-0.4.0"
CHANGE_RECORD_FILE_NAME = "r3-change-records.json"
RELATIONSHIP_RAW_FILE_NAME = "ifcdiff-relationships.json"
GEOMETRY_SUBTYPES = {
    "placement_translation", "extrusion_dimension_change", "tessellated_vertex_geometry_change",
}
RELATIONSHIP_SUBTYPES = {
    "spatial_containment_change", "aggregation_change", "type_assignment_change", "material_assignment_change",
}
CHANGE_TYPES = {"added", "deleted", "property_modified", "geometry_modified", "relationship_modified"}


def _schema() -> dict[str, Any]:
    resource = files("bimchange_agent.resources").joinpath(
        "product-change-record-0.4.0.schema.json"
    )
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("R3 schema must be an object")
    return value


def validate_r3_artifact(artifact: dict[str, Any]) -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(artifact)
    counts = Counter(item["change_type"] for item in artifact["changes"])
    expected = {
        "total_supported": len(artifact["changes"]),
        "added": counts["added"], "deleted": counts["deleted"],
        "property_modified": counts["property_modified"],
        "geometry_modified": counts["geometry_modified"],
        "relationship_modified": counts["relationship_modified"],
        "unsupported": len(artifact["unsupported_changes"]),
    }
    if artifact["summary"] != expected:
        raise ValueError("R3 summary mismatch")
    ids = [item["change_id"] for item in artifact["changes"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate R3 change_id")
    for model_key in ("source", "revised"):
        name = artifact[model_key]["file_name"]
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError("R3 model file_name must be a basename")
    relationship_fields = {
        "spatial_containment_change": "container",
        "aggregation_change": "aggregate",
        "type_assignment_change": "type",
        "material_assignment_change": "material",
    }
    for record in artifact["changes"]:
        result_file = record["evidence"]["result_file"]
        if Path(result_file).name != result_file or "/" in result_file or "\\" in result_file:
            raise ValueError("R3 evidence result_file must be a basename")
        change_type = record["change_type"]
        if change_type == "property_modified":
            field = record["field"]
            expected_id = _change_id(change_type, record["global_id"], field["property_set"], field["name"])
        elif change_type in {"geometry_modified", "relationship_modified"}:
            detail_key = "geometry_change" if change_type == "geometry_modified" else "relationship_change"
            expected_id = _change_id(change_type, record["global_id"], record[detail_key]["subtype"])
        else:
            expected_id = _change_id(change_type, record["global_id"], record["evidence"]["selector"])
        if record["change_id"] != expected_id:
            raise ValueError("R3 change_id does not match its semantic identity")
        geometry = record.get("geometry_change")
        if geometry and geometry["subtype"] == "extrusion_dimension_change":
            fields = [item["field"] for item in geometry["changed_dimensions"]]
            if len(fields) != len(set(fields)):
                raise ValueError("R3 repeats a changed dimension")
            for item in geometry["changed_dimensions"]:
                if abs((item["new_m"] - item["old_m"]) - item["delta_m"]) > 1e-9:
                    raise ValueError("R3 dimension delta is inconsistent")
        relationship = record.get("relationship_change")
        if relationship and relationship_fields[relationship["subtype"]] != relationship["relationship"]:
            raise ValueError("R3 relationship subtype is inconsistent")


def _geometry_record(global_id: str, data: dict[str, Any], source, revised, raw_name: str) -> dict[str, Any]:
    element = revised.by_guid(global_id)
    subtype = data["subtype"]
    if subtype == "extrusion_dimension_change":
        old_value = {item["field"]: item["old_m"] for item in data["changed_dimensions"]}
        new_value = {item["field"]: item["new_m"] for item in data["changed_dimensions"]}
        selector = f"ifc.{global_id}.Representation.Body.IfcExtrudedAreaSolid"
        rule = "rectangular-extrusion-parameters-v1"
    else:
        old_value = {"local_shape_sha256": data["old_local_shape_sha256"]}
        new_value = {"local_shape_sha256": data["new_local_shape_sha256"]}
        selector = f"changed.{global_id}.geometry_changed"
        rule = "ifc-triangulated-face-set-vertex-deformation-v1"
    return {
        "change_id": _change_id("geometry_modified", global_id, subtype),
        "change_type": "geometry_modified", "entity_type": element.is_a(), "global_id": global_id,
        "location": _location(element), "field": None, "old_value": old_value, "new_value": new_value,
        "geometry_change": data, "relationship_change": None,
        "evidence": {
            "reference_source": (
                "direct_ifc_reconstruction" if subtype == "extrusion_dimension_change"
                else "ifcdiff+ifc_reconstruction"
            ),
            "detector": f"Direct IFC chain + IfcDiff {ifcdiff_version}",
            "result_file": raw_name, "selector": selector,
            "reconstruction": {"rule_id": rule},
        },
    }


def _relationship_record(global_id: str, data: dict[str, Any], revised, raw_name: str) -> dict[str, Any]:
    element = revised.by_guid(global_id)
    subtype = data["subtype"]
    return {
        "change_id": _change_id("relationship_modified", global_id, subtype),
        "change_type": "relationship_modified", "entity_type": element.is_a(), "global_id": global_id,
        "location": _location(element), "field": None,
        "old_value": data["old_relation"], "new_value": data["new_relation"],
        "geometry_change": None, "relationship_change": data,
        "evidence": {
            "reference_source": "direct_ifc_reconstruction",
            "detector": f"Direct IFC chain + IfcDiff {ifcdiff_version}",
            "result_file": raw_name,
            "selector": f"ifc.{global_id}.{data['relationship']}",
            "reconstruction": {"rule_id": f"r3b-{data['relationship']}-v1"},
        },
    }


def diff_ifc_pair_r3(
    source_path: Path, revised_path: Path, output_dir: Path, *, limits: ProductLimits = DEFAULT_LIMITS
) -> dict[str, Any]:
    source_path, revised_path = _require_ifc_path(source_path, limits), _require_ifc_path(revised_path, limits)
    output_dir = output_dir.expanduser().resolve()
    base_result = diff_ifc_pair_geometry_candidate(source_path, revised_path, output_dir, limits=limits)
    source, _, source_ids = _open_stable_ifc(source_path, limits)
    revised, _, revised_ids = _open_stable_ifc(revised_path, limits)
    artifact = load_json(output_dir / BASE_RECORD_FILE_NAME)
    raw = load_json(output_dir / RAW_DIFF_FILE_NAME)
    relation_detector = IfcDiff(source, revised, relationships=["container", "aggregate", "type"], is_shallow=False, filter_elements=None)
    with redirect_stdout(io.StringIO()):
        relation_detector.diff()
    relationship_raw = {
        "added": sorted(relation_detector.added_elements),
        "deleted": sorted(relation_detector.deleted_elements),
        "changed": relation_detector.change_register,
        "known_limits": [
            "IfcDiff 0.8.5 relationship entity-instance comparison may emit unrelated flags or miss the requested flag.",
            "IfcDiff 0.8.5 has no material relationship mode.",
        ],
    }
    _write_json(output_dir / RELATIONSHIP_RAW_FILE_NAME, relationship_raw)
    records = artifact["changes"]
    for record in records:
        record["relationship_change"] = None
    handled_geometry = {
        item["global_id"] for item in records if item["change_type"] == "geometry_modified"
    }
    shared = sorted(source_ids & revised_ids)
    for global_id in shared:
        flags = raw.get("changed", {}).get(global_id, {})
        ifcdiff_flag = isinstance(flags, dict) and flags.get("geometry_changed") is True
        if global_id not in handled_geometry:
            try:
                data = extrusion_dimension_change(source, revised, global_id, ifcdiff_flag=ifcdiff_flag)
                records.append(_geometry_record(global_id, data, source, revised, RAW_DIFF_FILE_NAME))
                handled_geometry.add(global_id)
            except GeometryClassificationError:
                pass
        if ifcdiff_flag and global_id not in handled_geometry:
            try:
                data = tessellated_shape_change(source, revised, global_id)
                records.append(_geometry_record(global_id, data, source, revised, RAW_DIFF_FILE_NAME))
                handled_geometry.add(global_id)
            except GeometryClassificationError:
                pass
        try:
            data = relationship_change(source, revised, global_id)
            records.append(_relationship_record(global_id, data, revised, RELATIONSHIP_RAW_FILE_NAME))
        except GeometryClassificationError as error:
            if error.code == "relationship_scope_ambiguous":
                artifact["unsupported_changes"].append({
                    "global_id": global_id, "reason": f"Relationship change is ambiguous ({error.code}): {error}",
                    "selector": f"direct_relationships.{global_id}",
                })
    artifact["unsupported_changes"] = [
        item for item in artifact["unsupported_changes"]
        if not (item["selector"].endswith(".geometry_changed") and item["global_id"] in handled_geometry)
    ]
    records.sort(key=lambda item: item["change_id"])
    artifact["unsupported_changes"].sort(key=lambda item: (item["global_id"], item["selector"]))
    counts = Counter(item["change_type"] for item in records)
    artifact.update({
        "schema_version": SCHEMA_VERSION, "schema": SCHEMA_URI,
        "summary": {
            "total_supported": len(records), "added": counts["added"], "deleted": counts["deleted"],
            "property_modified": counts["property_modified"], "geometry_modified": counts["geometry_modified"],
            "relationship_modified": counts["relationship_modified"], "unsupported": len(artifact["unsupported_changes"]),
        },
    })
    artifact["generator"]["detectors"] = ["direct_ifc_chain_comparison", f"IfcDiff {ifcdiff_version}"]
    artifact["limits"]["geometry_subtypes"] = sorted(GEOMETRY_SUBTYPES)
    artifact["limits"]["relationship_subtypes"] = sorted(RELATIONSHIP_SUBTYPES)
    artifact["warnings"] = [
        "R3 scope is exact IFC4 and limited to the declared representation and relationship chains.",
        "Direct IFC-chain comparison is primary; IfcDiff 0.8.5 raw output is supplemental because controlled audits found geometry and relationship blind spots.",
        "Unsupported representation, topology, mixed semantic, and ambiguous relationship results fail closed.",
        "Change Records are coordination evidence, not engineering or safety conclusions.",
    ] + (["See unsupported_changes for detections outside the supported boundary."] if artifact["unsupported_changes"] else [])
    validate_r3_artifact(artifact)
    output_path = output_dir / CHANGE_RECORD_FILE_NAME
    _write_json(output_path, artifact)
    return {
        "status": "PASS_WITH_UNSUPPORTED_CHANGES" if artifact["unsupported_changes"] else "PASS",
        "output_dir": str(output_dir), "raw_diff": base_result["raw_diff"],
        "relationship_raw_diff": str(output_dir / RELATIONSHIP_RAW_FILE_NAME),
        "change_records": str(output_path), "summary": artifact["summary"], "model_calls_made": 0,
    }


def _validate_filters(filters: dict[str, Any]) -> None:
    allowed = {"change_types", "entity_types", "global_ids", "building_storey_names", "property_set", "property_name", "geometry_subtypes", "relationship_subtypes"}
    if set(filters) - allowed:
        raise ValueError("Unsupported R3 query filter")
    if set(filters.get("change_types", [])) - CHANGE_TYPES:
        raise ValueError("Unsupported R3 change type")
    if set(filters.get("geometry_subtypes", [])) - GEOMETRY_SUBTYPES:
        raise ValueError("Unsupported R3 geometry subtype")
    if set(filters.get("relationship_subtypes", [])) - RELATIONSHIP_SUBTYPES:
        raise ValueError("Unsupported R3 relationship subtype")


def query_r3_artifact(path: Path, filters: dict[str, Any]) -> dict[str, Any]:
    _validate_filters(filters)
    artifact = load_json(path)
    validate_r3_artifact(artifact)
    def matches(record: dict[str, Any]) -> bool:
        if filters.get("change_types") and record["change_type"] not in filters["change_types"]: return False
        if filters.get("entity_types") and record["entity_type"] not in filters["entity_types"]: return False
        if filters.get("global_ids") and record["global_id"] not in filters["global_ids"]: return False
        storey = record["location"]["building_storey"]
        if filters.get("building_storey_names") and (storey is None or storey["name"] not in filters["building_storey_names"]): return False
        field = record["field"]
        if filters.get("property_set") and (field is None or field["property_set"] != filters["property_set"]): return False
        if filters.get("property_name") and (field is None or field["name"] != filters["property_name"]): return False
        geometry = record.get("geometry_change")
        if filters.get("geometry_subtypes") and (geometry is None or geometry["subtype"] not in filters["geometry_subtypes"]): return False
        relationship = record.get("relationship_change")
        if filters.get("relationship_subtypes") and (relationship is None or relationship["subtype"] not in filters["relationship_subtypes"]): return False
        return True
    results = sorted((record for record in artifact["changes"] if matches(record)), key=lambda item: item["change_id"])
    return {
        "schema_version": artifact["schema_version"], "source": {"file_name": path.name, "sha256": sha256(path)},
        "filters": filters, "result_count": len(results), "results": results, "model_calls_made": 0,
    }
