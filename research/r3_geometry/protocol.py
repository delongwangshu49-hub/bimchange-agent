"""Generate and verify the isolated R3-A placement-translation evidence bundle."""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import shutil
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from uuid import uuid4

import ifcopenshell
import ifcopenshell.geom
import numpy as np
from ifcdiff import IfcDiff, __version__ as ifcdiff_version
from ifcopenshell.api.geometry import edit_object_placement
from ifcopenshell.util.element import get_container
from ifcopenshell.util.placement import get_local_placement
from ifcopenshell.util.shape import get_shape_matrix
from ifcopenshell.util.unit import calculate_unit_scale
from jsonschema import Draft202012Validator


PROTOCOL_ID = "r3a-placement-translation-0.1.0-candidate"
RECORD_SCHEMA_VERSION = "0.1.0-candidate"
MANIFEST_SCHEMA_VERSION = "0.1.0-candidate"
TARGET_GLOBAL_ID = "2ddLgAnQf4mBfh5IpUp54U"
PRIMARY_DELTA_M = (0.25, 0.0, 0.0)
VECTOR_DELTA_M = (0.125, -0.25, 0.375)
MESH_QUANTIZATION_M = 1e-6
ROTATION_TOLERANCE = 1e-8
TRANSLATION_AGREEMENT_TOLERANCE_M = 1e-8
MINIMUM_TRANSLATION_THRESHOLD_M = 1e-4
FIXED_HISTORY_TIMESTAMP = 1731578952
EXPECTED_DETECTOR = {
    "name": "IfcDiff",
    "version": "0.8.5",
    "configuration": {
        "relationships": ["geometry"],
        "is_shallow": False,
        "filter_elements": None,
    },
    "verification": "reexecute_and_compare_normalized_semantics",
}
ROLE_NAMES = {
    "source": "source.ifc",
    "revised": "revised.ifc",
    "ledger": "operation-ledger.json",
    "raw": "ifcdiff.json",
    "records": "geometry-records.json",
    "manifest": "trace-manifest.json",
}
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
UNC_ABSOLUTE = re.compile(r"^\\\\")
CREDENTIAL_TEXT = re.compile(
    r"(?i)(?:api[_ -]?key|access[_ -]?token|secret)\s*[:=]|sk-[A-Za-z0-9_-]{12,}"
)


class R3GeometryError(ValueError):
    """One fail-closed R3-A diagnostic."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class DuplicateJsonKeyError(ValueError):
    """Raised when strict JSON parsing encounters a duplicate object key."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def strict_load_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON number: {value}")

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_strict_object,
        parse_constant=reject_constant,
    )
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _schema(name: str) -> dict[str, Any]:
    return strict_load_json(Path(__file__).with_name(name))


def _round(value: float, digits: int = 12) -> float:
    rounded = round(float(value), digits)
    return 0.0 if rounded == 0 else rounded


def _vector(values: Any, digits: int = 12) -> list[float]:
    return [_round(value, digits) for value in values]


def _matrix(values: np.ndarray, digits: int = 12) -> list[list[float]]:
    return [_vector(row, digits) for row in values.tolist()]


def _context_precision(model: ifcopenshell.file) -> float:
    contexts = [
        context
        for context in model.by_type("IfcGeometricRepresentationContext")
        if context.ContextType == "Model"
    ]
    if not contexts:
        return 1e-4
    return float(contexts[0].Precision or 1e-4)


def _translation_threshold(model: ifcopenshell.file) -> float:
    return max(
        MINIMUM_TRANSLATION_THRESHOLD_M,
        10 * _context_precision(model) * calculate_unit_scale(model),
    )


def _geometry_settings() -> ifcopenshell.geom.settings:
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
        triangle = sorted(quantized[index].tolist() for index in face)
        triangles.append(triangle)
    triangles.sort()
    payload = {
        "quantization_m": MESH_QUANTIZATION_M,
        "vertex_count": int(len(vertices)),
        "triangle_count": int(len(faces)),
        "triangles": triangles,
    }
    return {
        "sha256": digest_value(payload),
        "vertex_count": payload["vertex_count"],
        "triangle_count": payload["triangle_count"],
        "bbox_min_m": _vector(vertices.min(axis=0), 9),
        "bbox_max_m": _vector(vertices.max(axis=0), 9),
        "quantization_m": MESH_QUANTIZATION_M,
    }


def _guid_matches(
    model: ifcopenshell.file, global_id: str
) -> list[ifcopenshell.entity_instance]:
    return [
        entity
        for entity in model.by_type("IfcRoot")
        if getattr(entity, "GlobalId", None) == global_id
    ]


def _require_element(
    model: ifcopenshell.file, global_id: str, *, role: str
) -> ifcopenshell.entity_instance:
    matches = _guid_matches(model, global_id)
    if len(matches) != 1 or not matches[0].is_a("IfcElement"):
        raise R3GeometryError(
            "global_id_resolution_failure",
            f"{global_id} does not resolve to exactly one IfcElement in {role}",
        )
    return matches[0]


def _reference(entity: ifcopenshell.entity_instance | None) -> dict[str, Any] | None:
    if entity is None:
        return None
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": getattr(entity, "Name", None),
    }


def _location(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    container = get_container(element)
    storey = (
        container
        if container is not None and container.is_a("IfcBuildingStorey")
        else None
    )
    return {
        "spatial_container": _reference(container),
        "building_storey": _reference(storey),
    }


def reconstruct_element_geometry(
    model: ifcopenshell.file, global_id: str, *, role: str
) -> dict[str, Any]:
    """Reconstruct placement and mesh facts without using IfcDiff summaries."""
    element = _require_element(model, global_id, role=role)
    if element.ObjectPlacement is None:
        raise R3GeometryError("placement_unresolved", f"No ObjectPlacement in {role}")
    unit_scale = float(calculate_unit_scale(model))
    object_matrix = np.asarray(get_local_placement(element.ObjectPlacement), dtype=float)
    object_matrix_si = object_matrix.copy()
    object_matrix_si[0:3, 3] *= unit_scale
    try:
        shape = ifcopenshell.geom.create_shape(_geometry_settings(), element)
    except Exception as error:
        raise R3GeometryError(
            "shape_unresolved", f"Could not construct shape in {role}"
        ) from error
    shape_matrix = np.asarray(get_shape_matrix(shape), dtype=float)
    mesh = _canonical_mesh(shape)
    return {
        "entity_type": element.is_a(),
        "global_id": element.GlobalId,
        "location": _location(element),
        "unit_scale_to_m": unit_scale,
        "context_precision": _context_precision(model),
        "object_matrix_si": _matrix(object_matrix_si),
        "object_origin_m": _vector(object_matrix_si[0:3, 3], 9),
        "object_rotation": _matrix(object_matrix_si[0:3, 0:3]),
        "shape_matrix_si": _matrix(shape_matrix),
        "shape_origin_m": _vector(shape_matrix[0:3, 3], 9),
        "shape_rotation": _matrix(shape_matrix[0:3, 0:3]),
        "local_mesh": mesh,
        "openings": sorted(
            opening.RelatedOpeningElement.GlobalId
            for opening in (getattr(element, "HasOpenings", None) or [])
        ),
        "projections": sorted(
            projection.RelatedFeatureElement.GlobalId
            for projection in (getattr(element, "HasProjections", None) or [])
        ),
    }


def normalized_ifcdiff_semantics(raw: dict[str, Any]) -> dict[str, Any]:
    added = raw.get("added")
    deleted = raw.get("deleted")
    changed = raw.get("changed")
    if not isinstance(added, list) or not isinstance(deleted, list):
        raise R3GeometryError("raw_shape_invalid", "Raw added/deleted must be arrays")
    if len(added) != len(set(added)) or len(deleted) != len(set(deleted)):
        raise R3GeometryError("raw_guid_duplicate", "Raw added/deleted contains duplicates")
    if not isinstance(changed, dict):
        raise R3GeometryError("raw_shape_invalid", "Raw changed must be an object")
    return {"added": sorted(added), "deleted": sorted(deleted), "changed": changed}


def run_geometry_diff(
    source_model: ifcopenshell.file, revised_model: ifcopenshell.file
) -> dict[str, Any]:
    detector = IfcDiff(
        source_model,
        revised_model,
        relationships=["geometry"],
        is_shallow=False,
        filter_elements=None,
    )
    with redirect_stdout(io.StringIO()):
        detector.diff()
    raw = {
        "added": sorted(detector.added_elements),
        "deleted": sorted(detector.deleted_elements),
        "changed": detector.change_register,
    }
    return normalized_ifcdiff_semantics(raw)


def _normalise_generated_serialization(model: ifcopenshell.file) -> None:
    for history in model.by_type("IfcOwnerHistory"):
        history.CreationDate = FIXED_HISTORY_TIMESTAMP
        if history.LastModifiedDate is not None:
            history.LastModifiedDate = FIXED_HISTORY_TIMESTAMP
    for relation in model.by_type("IfcRelContainedInSpatialStructure"):
        relation.RelatedElements = sorted(
            relation.RelatedElements,
            key=lambda entity: (entity.GlobalId, entity.is_a()),
        )
    for relation in model.by_type("IfcRelAssociatesMaterial"):
        relation.RelatedObjects = sorted(
            relation.RelatedObjects,
            key=lambda entity: (getattr(entity, "GlobalId", "") or "", entity.is_a()),
        )


def generate_revision(
    source_path: Path,
    revised_path: Path,
    *,
    variant: str,
    delta_m: tuple[float, float, float] = PRIMARY_DELTA_M,
) -> dict[str, Any]:
    model = ifcopenshell.open(source_path)
    element = _require_element(model, TARGET_GLOBAL_ID, role="source")
    source_facts = reconstruct_element_geometry(model, TARGET_GLOBAL_ID, role="source")
    world_matrix_si = np.asarray(source_facts["object_matrix_si"], dtype=float)
    operation: dict[str, Any]
    if variant == "translation":
        world_matrix_si[0:3, 3] += np.asarray(delta_m, dtype=float)
        edit_object_placement(
            model,
            product=element,
            matrix=world_matrix_si,
            is_si=True,
            should_transform_children=False,
        )
        operation = {"kind": "placement_translation", "delta_m": list(delta_m)}
    elif variant == "rotation":
        angle = math.radians(5.0)
        rotation = np.asarray(
            [
                [math.cos(angle), -math.sin(angle), 0.0],
                [math.sin(angle), math.cos(angle), 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        world_matrix_si[0:3, 0:3] = rotation @ world_matrix_si[0:3, 0:3]
        edit_object_placement(
            model,
            product=element,
            matrix=world_matrix_si,
            is_si=True,
            should_transform_children=False,
        )
        operation = {"kind": "rotation_only", "angle_degrees": 5.0}
    elif variant == "local_shape":
        representation = element.Representation
        if representation is None:
            raise R3GeometryError("shape_unresolved", "Target has no representation")
        item = representation.Representations[0].Items[0]
        if not item.is_a("IfcTriangulatedFaceSet"):
            raise R3GeometryError("shape_unresolved", "Target is not a triangulated fixture")
        coordinates = item.Coordinates
        rows = [list(row) for row in coordinates.CoordList]
        rows[0][0] += 100.0
        coordinates.CoordList = rows
        operation = {"kind": "local_shape_change", "first_point_x_delta_project_units": 100.0}
    elif variant == "missing_body":
        element.Representation = None
        operation = {"kind": "missing_body"}
    elif variant == "noop":
        operation = {"kind": "noop_rewrite"}
    else:
        raise ValueError(f"Unknown R3-A variant: {variant}")
    _normalise_generated_serialization(model)
    revised_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(revised_path)
    return {
        "protocol_id": PROTOCOL_ID,
        "operation_id": f"r3a-{variant}",
        "target_global_id": TARGET_GLOBAL_ID,
        "source_sha256": sha256_file(source_path),
        "revised_sha256": sha256_file(revised_path),
        "operation": operation,
        "expected": {
            "preserve_global_id": True,
            "preserve_entity_type": True,
            "supported_subtype": "placement_translation" if variant == "translation" else None,
        },
        "model_calls_made": 0,
    }


def _raw_selected_geometry(raw: dict[str, Any], global_id: str) -> tuple[bool, int]:
    raw = normalized_ifcdiff_semantics(raw)
    flags = raw["changed"].get(global_id)
    if not isinstance(flags, dict) or "geometry_changed" not in flags:
        raise R3GeometryError("evidence_locator_missing", "geometry_changed flag is absent")
    if set(flags) != {"geometry_changed"} or flags["geometry_changed"] is not True:
        raise R3GeometryError("evidence_flag_invalid", "Geometry flag is not exactly true")
    return True, 1


def reconstruct_translation_record(
    source_model: ifcopenshell.file,
    revised_model: ifcopenshell.file,
    raw: dict[str, Any],
    ledger: dict[str, Any],
) -> dict[str, Any]:
    raw = normalized_ifcdiff_semantics(raw)
    if raw["added"] or raw["deleted"] or set(raw["changed"]) != {TARGET_GLOBAL_ID}:
        raise R3GeometryError(
            "unexpected_detector_scope", "Translation slice must contain one changed GlobalId"
        )
    selected, match_count = _raw_selected_geometry(raw, TARGET_GLOBAL_ID)
    old = reconstruct_element_geometry(source_model, TARGET_GLOBAL_ID, role="source")
    new = reconstruct_element_geometry(revised_model, TARGET_GLOBAL_ID, role="revised")
    if old["entity_type"] != new["entity_type"]:
        raise R3GeometryError("entity_type_changed", "Entity type changed")
    if old["local_mesh"]["sha256"] != new["local_mesh"]["sha256"]:
        raise R3GeometryError("local_shape_changed", "Local canonical mesh changed")
    if old["openings"] != new["openings"] or old["projections"] != new["projections"]:
        raise R3GeometryError("feature_relationship_changed", "Opening/projection set changed")
    old_object_rotation = np.asarray(old["object_rotation"], dtype=float)
    new_object_rotation = np.asarray(new["object_rotation"], dtype=float)
    old_shape_rotation = np.asarray(old["shape_rotation"], dtype=float)
    new_shape_rotation = np.asarray(new["shape_rotation"], dtype=float)
    if (
        np.max(np.abs(old_object_rotation - new_object_rotation)) > ROTATION_TOLERANCE
        or np.max(np.abs(old_shape_rotation - new_shape_rotation)) > ROTATION_TOLERANCE
    ):
        raise R3GeometryError("rotation_changed", "Rotation changed outside the slice")
    object_delta = np.asarray(new["object_origin_m"]) - np.asarray(old["object_origin_m"])
    shape_delta = np.asarray(new["shape_origin_m"]) - np.asarray(old["shape_origin_m"])
    if np.max(np.abs(object_delta - shape_delta)) > TRANSLATION_AGREEMENT_TOLERANCE_M:
        raise R3GeometryError(
            "translation_channel_disagreement", "Object and shape translations disagree"
        )
    declared_delta = np.asarray(ledger["operation"].get("delta_m", []), dtype=float)
    if declared_delta.shape != (3,) or np.max(np.abs(object_delta - declared_delta)) > TRANSLATION_AGREEMENT_TOLERANCE_M:
        raise R3GeometryError("ledger_fact_mismatch", "Ledger delta differs from IFC facts")
    distance = float(np.linalg.norm(object_delta))
    threshold = _translation_threshold(source_model)
    if distance < threshold:
        raise R3GeometryError("below_support_threshold", "Translation is below support threshold")
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
    evidence = {
        "detector": {
            "result_role": ROLE_NAMES["raw"],
            "locator": {
                "section": "changed",
                "global_id": TARGET_GLOBAL_ID,
                "flag": "geometry_changed",
            },
            "selected_value_sha256": digest_value(selected),
        },
        "reconstruction": {
            "source_object_placement_sha256": digest_value(old["object_matrix_si"]),
            "revised_object_placement_sha256": digest_value(new["object_matrix_si"]),
            "source_local_shape_sha256": old["local_mesh"]["sha256"],
            "revised_local_shape_sha256": new["local_mesh"]["sha256"],
            "object_shape_translation_agreement": True,
        },
        "resolution": {"status": "resolved_unique", "match_count": match_count},
    }
    record_body = {
        "change_type": "geometry_modified",
        "entity_type": new["entity_type"],
        "global_id": TARGET_GLOBAL_ID,
        "location": new["location"],
        "field": None,
        "geometry_change": geometry_change,
        "evidence": evidence,
    }
    return {
        "change_id": f"chg-{digest_value(record_body)[:16]}",
        **record_body,
    }


def _artifact(role_name: str, path: Path, *, json_artifact: bool = False) -> dict[str, str]:
    result = {"role_name": role_name, "sha256": sha256_file(path)}
    if json_artifact:
        result["canonical_json_sha256"] = digest_value(strict_load_json(path))
    return result


def _records_artifact(
    source_path: Path,
    revised_path: Path,
    ledger: dict[str, Any],
    raw: dict[str, Any],
) -> dict[str, Any]:
    source_model = ifcopenshell.open(source_path)
    revised_model = ifcopenshell.open(revised_path)
    record = reconstruct_translation_record(source_model, revised_model, raw, ledger)
    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "schema": "bimchange-agent://research/r3a-geometry-records-0.1.0-candidate",
        "protocol_id": PROTOCOL_ID,
        "source": {
            "role_name": ROLE_NAMES["source"],
            "sha256": sha256_file(source_path),
            "ifc_schema": source_model.schema,
        },
        "revised": {
            "role_name": ROLE_NAMES["revised"],
            "sha256": sha256_file(revised_path),
            "ifc_schema": revised_model.schema,
        },
        "detector": EXPECTED_DETECTOR,
        "tolerances": {
            "mesh_quantization_m": MESH_QUANTIZATION_M,
            "rotation_tolerance": ROTATION_TOLERANCE,
            "translation_agreement_tolerance_m": TRANSLATION_AGREEMENT_TOLERANCE_M,
            "translation_support_threshold_m": _translation_threshold(source_model),
        },
        "ledger_sha256": digest_value(ledger),
        "changes": [record],
        "model_calls_made": 0,
    }


def _manifest(bundle: Path) -> dict[str, Any]:
    records = strict_load_json(bundle / ROLE_NAMES["records"])
    raw = strict_load_json(bundle / ROLE_NAMES["raw"])
    record = records["changes"][0]
    entry_body = {
        "change_id": record["change_id"],
        "change_record_sha256": digest_value(record),
        "global_id": record["global_id"],
        "change_type": record["change_type"],
        "raw_evidence": record["evidence"]["detector"],
        "reconstructed_fact_sha256": digest_value(record["geometry_change"]),
        "resolution": {"status": "resolved_unique", "match_count": 1},
    }
    return {
        "protocol_id": PROTOCOL_ID,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "artifacts": {
            "source": _artifact(ROLE_NAMES["source"], bundle / ROLE_NAMES["source"]),
            "revised": _artifact(ROLE_NAMES["revised"], bundle / ROLE_NAMES["revised"]),
            "ledger": _artifact(ROLE_NAMES["ledger"], bundle / ROLE_NAMES["ledger"], json_artifact=True),
            "raw_result": _artifact(ROLE_NAMES["raw"], bundle / ROLE_NAMES["raw"], json_artifact=True),
            "geometry_records": _artifact(ROLE_NAMES["records"], bundle / ROLE_NAMES["records"], json_artifact=True),
        },
        "detector": EXPECTED_DETECTOR,
        "entries": [{"trace_id": f"trace-{digest_value(entry_body)[:24]}", **entry_body}],
        "summary": {
            "supported_change_records": 1,
            "resolved_unique": 1,
            "trace_resolution_rate": 1.0,
            "supported_change_types": ["geometry_modified"],
            "supported_geometry_subtypes": ["placement_translation"],
        },
        "model_calls_made": 0,
    }


def build_bundle(source: Path, output: Path, *, delta_m: tuple[float, float, float] = PRIMARY_DELTA_M) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    source_role = output / ROLE_NAMES["source"]
    revised_role = output / ROLE_NAMES["revised"]
    shutil.copyfile(source, source_role)
    ledger = generate_revision(source_role, revised_role, variant="translation", delta_m=delta_m)
    write_json(output / ROLE_NAMES["ledger"], ledger)
    source_model = ifcopenshell.open(source_role)
    revised_model = ifcopenshell.open(revised_role)
    raw = run_geometry_diff(source_model, revised_model)
    write_json(output / ROLE_NAMES["raw"], raw)
    records = _records_artifact(source_role, revised_role, ledger, raw)
    Draft202012Validator(_schema("geometry-records.schema.json")).validate(records)
    write_json(output / ROLE_NAMES["records"], records)
    manifest = _manifest(output)
    Draft202012Validator(_schema("trace-manifest.schema.json")).validate(manifest)
    write_json(output / ROLE_NAMES["manifest"], manifest)
    return verify_bundle(output)


def _privacy_violations(value: Any) -> list[str]:
    violations: list[str] = []

    def visit(item: Any, path: str) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                visit(child, f"{path}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]")
        elif isinstance(item, str):
            if WINDOWS_ABSOLUTE.match(item) or UNC_ABSOLUTE.match(item) or Path(item).is_absolute():
                violations.append(f"absolute_path:{path}")
            if CREDENTIAL_TEXT.search(item):
                violations.append(f"credential_text:{path}")

    visit(value, "root")
    return violations


def verify_bundle(bundle: Path) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    try:
        paths = {key: bundle / name for key, name in ROLE_NAMES.items()}
        ledger = strict_load_json(paths["ledger"])
        raw = strict_load_json(paths["raw"])
        records = strict_load_json(paths["records"])
        manifest = strict_load_json(paths["manifest"])
        violations = _privacy_violations(
            {"ledger": ledger, "raw": raw, "records": records, "manifest": manifest}
        )
        if violations:
            raise R3GeometryError(
                "privacy_boundary_violation", ",".join(violations)
            )
        Draft202012Validator(_schema("geometry-records.schema.json")).validate(records)
        Draft202012Validator(_schema("trace-manifest.schema.json")).validate(manifest)
        if ifcdiff_version != "0.8.5" or records["detector"] != EXPECTED_DETECTOR or manifest["detector"] != EXPECTED_DETECTOR:
            raise R3GeometryError("detector_configuration_mismatch", "Detector metadata drifted")
        expected_tolerances = {
            "mesh_quantization_m": MESH_QUANTIZATION_M,
            "rotation_tolerance": ROTATION_TOLERANCE,
            "translation_agreement_tolerance_m": TRANSLATION_AGREEMENT_TOLERANCE_M,
            "translation_support_threshold_m": _translation_threshold(ifcopenshell.open(paths["source"])),
        }
        if records["tolerances"] != expected_tolerances:
            raise R3GeometryError("tolerance_configuration_mismatch", "Tolerance metadata drifted")
        for key, manifest_key in (("source", "source"), ("revised", "revised"), ("ledger", "ledger"), ("raw", "raw_result"), ("records", "geometry_records")):
            registered = manifest["artifacts"][manifest_key]
            if registered["role_name"] != ROLE_NAMES[key] or registered["sha256"] != sha256_file(paths[key]):
                raise R3GeometryError("artifact_hash_mismatch", f"Artifact binding drifted: {key}")
            if key in {"ledger", "raw", "records"} and registered["canonical_json_sha256"] != digest_value(strict_load_json(paths[key])):
                raise R3GeometryError("artifact_semantic_hash_mismatch", f"Semantic binding drifted: {key}")
        if ledger["source_sha256"] != sha256_file(paths["source"]) or ledger["revised_sha256"] != sha256_file(paths["revised"]):
            raise R3GeometryError("ledger_hash_mismatch", "Ledger input binding drifted")
        if records["ledger_sha256"] != digest_value(ledger):
            raise R3GeometryError("ledger_hash_mismatch", "Record ledger binding drifted")
        source_model = ifcopenshell.open(paths["source"])
        revised_model = ifcopenshell.open(paths["revised"])
        replay = run_geometry_diff(source_model, revised_model)
        if normalized_ifcdiff_semantics(raw) != replay:
            raise R3GeometryError("detector_replay_mismatch", "IfcDiff replay differs from raw")
        expected_record = reconstruct_translation_record(source_model, revised_model, raw, ledger)
        if records["changes"] != [expected_record]:
            raise R3GeometryError("reconstructed_fact_mismatch", "Candidate record differs from IFC reconstruction")
        expected_manifest = _manifest(bundle)
        if manifest != expected_manifest:
            raise R3GeometryError("manifest_reconstruction_mismatch", "Manifest differs from independent rebuild")
    except DuplicateJsonKeyError as error:
        failures.append({"code": "duplicate_json_key", "message": str(error)})
    except R3GeometryError as error:
        failures.append({"code": error.code, "message": str(error)})
    except Exception as error:
        failures.append({"code": "validation_failure", "message": f"{type(error).__name__}: {error}"})
    return {
        "status": "PASS" if not failures else "FAIL",
        "protocol_id": PROTOCOL_ID,
        "supported_change_records": 1 if not failures else 0,
        "trace_resolution_rate": 1.0 if not failures else 0.0,
        "privacy_violation_count": 0 if not failures else sum(item["code"] == "privacy_boundary_violation" for item in failures),
        "failures": failures,
        "model_calls_made": 0,
    }
