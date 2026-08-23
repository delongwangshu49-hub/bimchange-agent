"""Explicit v0.3 candidate backend for bounded placement-only geometry changes."""

from __future__ import annotations

import hashlib
import io
import json
import math
from collections import Counter
from contextlib import redirect_stdout
from importlib.resources import files
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.geom
import numpy as np
from ifcdiff import IfcDiff, __version__ as ifcdiff_version
from ifcopenshell.util.placement import get_local_placement
from ifcopenshell.util.shape import get_shape_matrix
from ifcopenshell.util.unit import calculate_unit_scale
from jsonschema import Draft202012Validator

from . import __version__
from .product_core import (
    DEFAULT_LIMITS,
    ProductBoundaryError,
    ProductLimits,
    _change_id,
    _location,
    _normalize_diff,
    _open_stable_ifc,
    _require_ifc_path,
    _write_json,
    load_json,
    sha256,
)


SCHEMA_VERSION = "0.3.0-preview.1-candidate"
SCHEMA_URI = "bimchange-agent://schemas/product-change-record-0.3.0-preview.1-candidate"
RAW_DIFF_FILE_NAME = "ifcdiff-geometry-candidate.json"
CHANGE_RECORD_FILE_NAME = "geometry-change-records.json"
MESH_QUANTIZATION_M = 1e-6
ROTATION_TOLERANCE = 1e-8
TRANSLATION_AGREEMENT_TOLERANCE_M = 1e-8
MINIMUM_TRANSLATION_THRESHOLD_M = 1e-4
SUPPORTED_CHANGE_TYPES = {
    "added",
    "deleted",
    "property_modified",
    "geometry_modified",
}
SUPPORTED_GEOMETRY_SUBTYPES = {"placement_translation"}


class GeometryClassificationError(ValueError):
    """A geometry flag that cannot be classified inside the candidate slice."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _schema() -> dict[str, Any]:
    resource = files("bimchange_agent.resources").joinpath(
        "product-change-record-0.3.0-preview.1-candidate.schema.json"
    )
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Candidate product schema is not a JSON object")
    return value


def _round(value: float, digits: int = 12) -> float:
    rounded = round(float(value), digits)
    return 0.0 if rounded == 0 else rounded


def _vector(values: Any, digits: int = 12) -> list[float]:
    return [_round(value, digits) for value in values]


def _matrix(values: np.ndarray, digits: int = 12) -> list[list[float]]:
    return [_vector(row, digits) for row in values.tolist()]


def _digest_value(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _context_precision(model: ifcopenshell.file) -> float:
    contexts = [
        context
        for context in model.by_type("IfcGeometricRepresentationContext")
        if context.ContextType == "Model"
    ]
    return float(contexts[0].Precision or 1e-4) if contexts else 1e-4


def _translation_threshold(model: ifcopenshell.file) -> float:
    return max(
        MINIMUM_TRANSLATION_THRESHOLD_M,
        10 * _context_precision(model) * calculate_unit_scale(model),
    )


def _settings() -> ifcopenshell.geom.settings:
    settings = ifcopenshell.geom.settings()
    settings.set("disable-boolean-result", True)
    settings.set("disable-opening-subtractions", True)
    return settings


def _canonical_mesh(shape: Any) -> dict[str, Any]:
    vertices = np.asarray(shape.geometry.verts, dtype=float).reshape((-1, 3))
    faces = np.asarray(shape.geometry.faces, dtype=int).reshape((-1, 3))
    quantized = np.rint(vertices / MESH_QUANTIZATION_M).astype(np.int64)
    triangles: list[list[list[int]]] = []
    for face in faces:
        triangles.append(sorted(quantized[index].tolist() for index in face))
    triangles.sort()
    payload = {
        "quantization_m": MESH_QUANTIZATION_M,
        "vertex_count": int(len(vertices)),
        "triangle_count": int(len(faces)),
        "triangles": triangles,
    }
    return {
        "sha256": _digest_value(payload),
        "vertex_count": payload["vertex_count"],
        "triangle_count": payload["triangle_count"],
    }


def _guid_matches(
    model: ifcopenshell.file, global_id: str
) -> list[ifcopenshell.entity_instance]:
    return [
        entity
        for entity in model.by_type("IfcRoot")
        if getattr(entity, "GlobalId", None) == global_id
    ]


def _element_facts(
    model: ifcopenshell.file, global_id: str, *, role: str
) -> dict[str, Any]:
    matches = _guid_matches(model, global_id)
    if len(matches) != 1 or not matches[0].is_a("IfcElement"):
        raise GeometryClassificationError(
            "global_id_resolution_failure",
            f"GlobalId does not resolve to one IfcElement in {role}",
        )
    element = matches[0]
    if element.ObjectPlacement is None:
        raise GeometryClassificationError("placement_unresolved", f"No placement in {role}")
    object_matrix = np.asarray(get_local_placement(element.ObjectPlacement), dtype=float)
    object_matrix_si = object_matrix.copy()
    object_matrix_si[0:3, 3] *= float(calculate_unit_scale(model))
    try:
        shape = ifcopenshell.geom.create_shape(_settings(), element)
    except Exception as error:
        raise GeometryClassificationError(
            "shape_unresolved", f"Could not construct shape in {role}"
        ) from error
    shape_matrix = np.asarray(get_shape_matrix(shape), dtype=float)
    return {
        "entity": element,
        "entity_type": element.is_a(),
        "object_matrix_si": _matrix(object_matrix_si),
        "object_origin_m": _vector(object_matrix_si[0:3, 3], 9),
        "object_rotation": _matrix(object_matrix_si[0:3, 0:3]),
        "shape_origin_m": _vector(shape_matrix[0:3, 3], 9),
        "shape_rotation": _matrix(shape_matrix[0:3, 0:3]),
        "local_mesh": _canonical_mesh(shape),
        "openings": sorted(
            item.RelatedOpeningElement.GlobalId
            for item in (getattr(element, "HasOpenings", None) or [])
        ),
        "projections": sorted(
            item.RelatedFeatureElement.GlobalId
            for item in (getattr(element, "HasProjections", None) or [])
        ),
    }


def _geometry_record(
    global_id: str,
    old_model: ifcopenshell.file,
    new_model: ifcopenshell.file,
    *,
    raw_diff_name: str,
) -> dict[str, Any]:
    old = _element_facts(old_model, global_id, role="source")
    new = _element_facts(new_model, global_id, role="revised")
    if old["entity_type"] != new["entity_type"]:
        raise GeometryClassificationError("entity_type_changed", "Entity type changed")
    if old["local_mesh"]["sha256"] != new["local_mesh"]["sha256"]:
        raise GeometryClassificationError("local_shape_changed", "Local canonical mesh changed")
    if old["openings"] != new["openings"] or old["projections"] != new["projections"]:
        raise GeometryClassificationError(
            "feature_relationship_changed", "Opening/projection set changed"
        )
    if (
        np.max(
            np.abs(
                np.asarray(old["object_rotation"], dtype=float)
                - np.asarray(new["object_rotation"], dtype=float)
            )
        )
        > ROTATION_TOLERANCE
        or np.max(
            np.abs(
                np.asarray(old["shape_rotation"], dtype=float)
                - np.asarray(new["shape_rotation"], dtype=float)
            )
        )
        > ROTATION_TOLERANCE
    ):
        raise GeometryClassificationError("rotation_changed", "Rotation changed")
    object_delta = np.asarray(new["object_origin_m"]) - np.asarray(old["object_origin_m"])
    shape_delta = np.asarray(new["shape_origin_m"]) - np.asarray(old["shape_origin_m"])
    if np.max(np.abs(object_delta - shape_delta)) > TRANSLATION_AGREEMENT_TOLERANCE_M:
        raise GeometryClassificationError(
            "translation_channel_disagreement",
            "ObjectPlacement and shape transformation translations disagree",
        )
    distance = float(np.linalg.norm(object_delta))
    threshold = _translation_threshold(old_model)
    if distance < threshold:
        raise GeometryClassificationError(
            "below_support_threshold",
            f"Translation {distance:.9g} m is below {threshold:.9g} m",
        )
    geometry_change = {
        "subtype": "placement_translation",
        "coordinate_frame": "project_world",
        "length_unit": "m",
        "old_origin": old["object_origin_m"],
        "new_origin": new["object_origin_m"],
        "delta": _vector(object_delta, 9),
        "distance": _round(distance, 9),
        "local_shape_unchanged": True,
    }
    selector = f"changed.{global_id}.geometry_changed"
    return {
        "change_id": _change_id(
            "geometry_modified", global_id, "placement_translation"
        ),
        "change_type": "geometry_modified",
        "entity_type": new["entity_type"],
        "global_id": global_id,
        "location": _location(new["entity"]),
        "field": None,
        "old_value": {"origin_m": old["object_origin_m"]},
        "new_value": {"origin_m": new["object_origin_m"]},
        "geometry_change": geometry_change,
        "evidence": {
            "reference_source": "ifcdiff+ifc_reconstruction",
            "detector": f"IfcDiff {ifcdiff_version}",
            "result_file": raw_diff_name,
            "selector": selector,
            "reconstruction": {
                "rule_id": "placement-translation-v1",
                "source_object_placement_sha256": _digest_value(old["object_matrix_si"]),
                "revised_object_placement_sha256": _digest_value(new["object_matrix_si"]),
                "source_local_shape_sha256": old["local_mesh"]["sha256"],
                "revised_local_shape_sha256": new["local_mesh"]["sha256"],
                "object_shape_translation_agreement": True,
                "translation_support_threshold_m": threshold,
            },
        },
    }


def validate_candidate_artifact(artifact: dict[str, Any]) -> None:
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(artifact)
    counts = Counter(record["change_type"] for record in artifact["changes"])
    expected_summary = {
        "total_supported": len(artifact["changes"]),
        "added": counts["added"],
        "deleted": counts["deleted"],
        "property_modified": counts["property_modified"],
        "geometry_modified": counts["geometry_modified"],
        "unsupported": len(artifact["unsupported_changes"]),
    }
    if artifact["summary"] != expected_summary:
        raise ValueError("Candidate summary does not match its records")
    change_ids = [record["change_id"] for record in artifact["changes"]]
    if len(change_ids) != len(set(change_ids)):
        raise ValueError("Candidate artifact contains duplicate change_id values")
    for model_key in ("source", "revised"):
        name = artifact[model_key]["file_name"]
        if Path(name).name != name or "/" in name or "\\" in name:
            raise ValueError("Candidate model file_name must be a basename")
    for record in artifact["changes"]:
        result_file = record["evidence"]["result_file"]
        if Path(result_file).name != result_file or "/" in result_file or "\\" in result_file:
            raise ValueError("Candidate evidence result_file must be a basename")


def diff_ifc_pair_geometry_candidate(
    source_path: Path,
    revised_path: Path,
    output_dir: Path,
    *,
    limits: ProductLimits = DEFAULT_LIMITS,
) -> dict[str, Any]:
    """Emit an explicit candidate artifact without changing the legacy product path."""
    source_path = _require_ifc_path(source_path, limits)
    revised_path = _require_ifc_path(revised_path, limits)
    source_model, source_summary, source_ids = _open_stable_ifc(source_path, limits)
    revised_model, revised_summary, revised_ids = _open_stable_ifc(revised_path, limits)
    denominator = min(len(source_ids), len(revised_ids))
    shared_count = len(source_ids & revised_ids)
    shared_ratio = shared_count / denominator if denominator else 0.0
    if shared_ratio < limits.min_shared_guid_ratio:
        raise ProductBoundaryError(
            f"Only {shared_ratio:.1%} of comparable element GUIDs are shared"
        )
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / RAW_DIFF_FILE_NAME
    records_path = output_dir / CHANGE_RECORD_FILE_NAME
    existing = [path.name for path in (raw_path, records_path) if path.exists()]
    if existing:
        raise ProductBoundaryError(
            "Output directory already contains candidate artifacts: "
            + ", ".join(existing)
        )
    detector = IfcDiff(
        source_model,
        revised_model,
        relationships=["property", "geometry"],
        is_shallow=False,
        filter_elements=None,
    )
    try:
        with redirect_stdout(io.StringIO()):
            detector.diff()
        raw = {
            "added": sorted(detector.added_elements),
            "deleted": sorted(detector.deleted_elements),
            "changed": detector.change_register,
        }
    except Exception as error:
        raise ProductBoundaryError("IfcDiff geometry candidate comparison failed") from error
    _write_json(raw_path, raw)
    records, unsupported = _normalize_diff(
        raw,
        source_model,
        revised_model,
        raw_diff_name=raw_path.name,
    )
    geometry_selectors = {
        f"changed.{global_id}.geometry_changed"
        for global_id, flags in raw.get("changed", {}).items()
        if isinstance(flags, dict) and "geometry_changed" in flags
    }
    unsupported = [
        item for item in unsupported if item["selector"] not in geometry_selectors
    ]
    for global_id in sorted(raw.get("changed", {})):
        flags = raw["changed"][global_id]
        if not isinstance(flags, dict) or flags.get("geometry_changed") is not True:
            continue
        selector = f"changed.{global_id}.geometry_changed"
        try:
            records.append(
                _geometry_record(
                    global_id,
                    source_model,
                    revised_model,
                    raw_diff_name=raw_path.name,
                )
            )
        except GeometryClassificationError as error:
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": (
                        "Geometry flag is not a supported placement translation "
                        f"({error.code}): {error}"
                    ),
                    "selector": selector,
                }
            )
    for record in records:
        record.setdefault("geometry_change", None)
    records.sort(key=lambda item: item["change_id"])
    unsupported.sort(key=lambda item: (item["global_id"], item["selector"]))
    counts = Counter(record["change_type"] for record in records)
    warnings = [
        "Candidate scope: exact IFC4 only; geometry support is limited to placement-only translation.",
        "IfcDiff 0.8.5 may not flag a revised-side Body removal; absence of a geometry record is not proof that geometry is unchanged.",
        "Geometry facts are coordination evidence, not engineering or safety conclusions.",
    ]
    if unsupported:
        warnings.append(
            "IfcDiff reported changes outside the candidate normalization boundary; see unsupported_changes."
        )
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "schema": SCHEMA_URI,
        "generator": {
            "name": "BIMChange-Agent",
            "version": __version__,
            "detector": f"IfcDiff {ifcdiff_version}",
            "relationships": ["property", "geometry"],
            "is_shallow": False,
        },
        "limits": {
            **vars(limits),
            "geometry_subtypes": ["placement_translation"],
        },
        "source": source_summary,
        "revised": revised_summary,
        "pair_diagnostics": {
            "shared_element_guid_count": shared_count,
            "shared_element_guid_ratio": round(shared_ratio, 6),
        },
        "summary": {
            "total_supported": len(records),
            "added": counts["added"],
            "deleted": counts["deleted"],
            "property_modified": counts["property_modified"],
            "geometry_modified": counts["geometry_modified"],
            "unsupported": len(unsupported),
        },
        "warnings": warnings,
        "changes": records,
        "unsupported_changes": unsupported,
        "model_calls_made": 0,
    }
    validate_candidate_artifact(artifact)
    _write_json(records_path, artifact)
    return {
        "status": "PASS_WITH_UNSUPPORTED_CHANGES" if unsupported else "PASS",
        "output_dir": str(output_dir),
        "raw_diff": str(raw_path),
        "change_records": str(records_path),
        "summary": artifact["summary"],
        "model_calls_made": 0,
    }

def _validate_candidate_filters(filters: dict[str, Any]) -> None:
    allowed = {
        "change_types",
        "entity_types",
        "global_ids",
        "building_storey_names",
        "property_set",
        "property_name",
        "geometry_subtypes",
    }
    unknown = sorted(set(filters) - allowed)
    if unknown:
        raise ValueError(f"Unsupported candidate query filters: {', '.join(unknown)}")
    for key in (
        "change_types",
        "entity_types",
        "global_ids",
        "building_storey_names",
        "geometry_subtypes",
    ):
        values = filters.get(key, [])
        if not isinstance(values, list) or any(
            not isinstance(value, str) or not value for value in values
        ):
            raise ValueError(f"{key} must be a list of non-empty strings")
    if set(filters.get("change_types", [])) - SUPPORTED_CHANGE_TYPES:
        raise ValueError("Unsupported candidate change type")
    if set(filters.get("geometry_subtypes", [])) - SUPPORTED_GEOMETRY_SUBTYPES:
        raise ValueError("Unsupported candidate geometry subtype")


def _record_matches(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    if filters.get("change_types") and record["change_type"] not in filters["change_types"]:
        return False
    if filters.get("entity_types") and record["entity_type"] not in filters["entity_types"]:
        return False
    if filters.get("global_ids") and record["global_id"] not in filters["global_ids"]:
        return False
    if filters.get("building_storey_names"):
        storey = record["location"]["building_storey"]
        if storey is None or storey["name"] not in filters["building_storey_names"]:
            return False
    field = record["field"]
    if filters.get("property_set") and (
        field is None or field["property_set"] != filters["property_set"]
    ):
        return False
    if filters.get("property_name") and (
        field is None or field["name"] != filters["property_name"]
    ):
        return False
    if filters.get("geometry_subtypes"):
        geometry = record["geometry_change"]
        if geometry is None or geometry["subtype"] not in filters["geometry_subtypes"]:
            return False
    return True


def query_geometry_candidate_artifact(
    artifact_path: Path, filters: dict[str, Any]
) -> dict[str, Any]:
    artifact_path = artifact_path.expanduser().resolve()
    _validate_candidate_filters(filters)
    artifact = load_json(artifact_path)
    validate_candidate_artifact(artifact)
    results = sorted(
        (record for record in artifact["changes"] if _record_matches(record, filters)),
        key=lambda item: item["change_id"],
    )
    return {
        "schema_version": artifact["schema_version"],
        "source": {"file_name": artifact_path.name, "sha256": sha256(artifact_path)},
        "filters": filters,
        "result_count": len(results),
        "results": results,
        "model_calls_made": 0,
    }
