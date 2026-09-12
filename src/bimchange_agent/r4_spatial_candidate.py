"""Isolated product candidate for one Change Record's local spatial scene."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom

from .r4_glb import MeshInput, write_glb, _geometry


CONTRACT_VERSION = "r4-local-spatial-product-candidate-0.1.0"
VIEWER_RESOURCE_ROOT = Path(__file__).resolve().parent / "resources" / "r4_viewer"
ROLE_BY_CHANGE_TYPE = {
    "deleted": "source",
    "added": "revised",
    "property_modified": "revised",
    "geometry_modified": "revised",
    "relationship_modified": "revised",
}
COLOURS = {
    "deleted": "#D84A3A",
    "added": "#2E9D62",
    "property_modified": "#E39B2E",
    "geometry_modified": "#8A63D2",
    "relationship_modified": "#3B82B4",
    "context": "#8B949E",
}
MAXIMUM_DISTANCE_M = 6.0
MAXIMUM_NEIGHBOURS = 2


class R4SpatialCandidateError(ValueError):
    """A failure-closed candidate scene classification error."""


@dataclass(frozen=True)
class SpatialSceneResult:
    bundle: Path
    entrypoint: Path
    manifest: Path
    target_global_id: str
    selected_ifc_role: str
    scene_sha256: str
    context_count: int


class SpatialSessionCache:
    """Worker-owned, bounded mesh cache; never shared across report sessions."""

    def __init__(self, maximum_mesh_bytes: int = 64 * 1024 * 1024) -> None:
        self.maximum_mesh_bytes = maximum_mesh_bytes
        self._fingerprints: dict[str, str] = {}
        self._models: dict[str, object] = {}
        self._meshes: OrderedDict = OrderedDict()
        self._bounds: dict = {}
        self._mesh_bytes = 0

    def verify_inputs(self, source: Path, revised: Path, artifact: dict) -> dict:
        hashes = {}
        for role, path in (("source", source), ("revised", revised)):
            if path.stat().st_size > 50 * 1024 * 1024:
                raise R4SpatialCandidateError("input_size_limit")
            fingerprint = _sha256(path)
            expected = artifact.get(role, {}).get("sha256")
            if (expected and fingerprint != expected) or (
                role in self._fingerprints and self._fingerprints[role] != fingerprint
            ):
                raise R4SpatialCandidateError("input_changed_since_analysis")
            hashes[role] = fingerprint
        self._fingerprints.update(hashes)
        return hashes

    def model(self, role: str, path: Path):
        if role not in self._models:
            model = ifcopenshell.open(path)
            if model.schema != "IFC4":
                raise R4SpatialCandidateError("unsupported_schema")
            if len(model.by_type("IfcElement")) > 5000:
                raise R4SpatialCandidateError("element_limit")
            roots = model.by_type("IfcRoot")
            ids = [item.GlobalId for item in roots]
            if any(not item or len(item) != 22 for item in ids) or len(set(ids)) != len(ids):
                raise R4SpatialCandidateError("non_unique_global_id")
            self._models[role] = model
        return self._models[role]

    def geometry(self, role: str, element):
        key = (role, element.GlobalId)
        if key in self._meshes:
            self._meshes.move_to_end(key)
            return self._meshes[key][0]
        try:
            geometry = _geometry(element)
        except Exception as error:
            raise R4SpatialCandidateError("target_geometry_unavailable") from error
        vertices, indices = geometry
        if not all(math.isfinite(value) for value in vertices):
            raise R4SpatialCandidateError("target_geometry_unavailable")
        axes = [vertices[index::3] for index in range(3)]
        self._bounds[key] = ([min(axis) for axis in axes], [max(axis) for axis in axes])
        # Python list slots and scalar objects, conservatively rounded upward.
        size = 40 * (len(vertices) + len(indices))
        while self._meshes and self._mesh_bytes + size > self.maximum_mesh_bytes:
            _, (_, previous_size) = self._meshes.popitem(last=False)
            self._mesh_bytes -= previous_size
        if size <= self.maximum_mesh_bytes:
            self._meshes[key] = (geometry, size)
            self._mesh_bytes += size
        return geometry

    def bounds(self, role: str, element):
        key = (role, element.GlobalId)
        if key not in self._bounds:
            self.geometry(role, element)
        return self._bounds[key]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_by_guid(model: ifcopenshell.file, global_id: str):
    try:
        return model.by_guid(global_id)
    except RuntimeError:
        return None


def _direct_storey(element):
    relationships = [
        relation.RelatingStructure
        for relation in element.ContainedInStructure
        if relation.is_a("IfcRelContainedInSpatialStructure")
        and relation.RelatingStructure.is_a("IfcBuildingStorey")
    ]
    if len(relationships) != 1:
        raise R4SpatialCandidateError("direct_storey_unavailable")
    return relationships[0]


def _bounds(element) -> tuple[list[float], list[float]]:
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    try:
        shape = ifcopenshell.geom.create_shape(settings, element)
    except Exception as error:
        raise R4SpatialCandidateError("target_geometry_unavailable") from error
    vertices = [float(value) for value in shape.geometry.verts]
    if not vertices or len(vertices) % 3:
        raise R4SpatialCandidateError("target_geometry_unavailable")
    axes = [vertices[index::3] for index in range(3)]
    return [min(axis) for axis in axes], [max(axis) for axis in axes]


def _centre(bounds: tuple[list[float], list[float]]) -> list[float]:
    return [(low + high) / 2 for low, high in zip(*bounds)]


def _distance(first: list[float], second: list[float]) -> float:
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(first, second)))


def _context(model, target, changed_global_ids: set[str], bounds=_bounds) -> list[tuple[object, float]]:
    storey = _direct_storey(target)
    target_centre = _centre(bounds(target))
    candidates: list[tuple[float, str, object]] = []
    for element in model.by_type("IfcElement"):
        if element.GlobalId in changed_global_ids:
            continue
        try:
            candidate_storey = _direct_storey(element)
            if candidate_storey.GlobalId != storey.GlobalId:
                continue
            distance = _distance(target_centre, _centre(bounds(element)))
        except (R4SpatialCandidateError, RuntimeError):
            continue
        if candidate_storey.GlobalId != storey.GlobalId:
            continue
        if distance <= MAXIMUM_DISTANCE_M:
            candidates.append((distance, element.GlobalId, element))
    candidates.sort(key=lambda item: (round(item[0], 9), item[1]))
    return [
        (element, distance)
        for distance, _, element in candidates[:MAXIMUM_NEIGHBOURS]
    ]


def _node(element, *, role: str, distance_m: float) -> dict:
    storey = _direct_storey(element)
    return {
        "global_id": element.GlobalId,
        "entity_type": element.is_a(),
        "storey_global_id": storey.GlobalId,
        "storey_name": storey.Name,
        "role": role,
        "distance_m": round(distance_m, 6),
    }


def _camera(elements: list[object], get_bounds=_bounds) -> dict:
    bounds = [get_bounds(element) for element in elements]
    low = [min(item[0][axis] for item in bounds) for axis in range(3)]
    high = [max(item[1][axis] for item in bounds) for axis in range(3)]
    target = [(left + right) / 2 for left, right in zip(low, high)]
    diagonal = max(_distance(low, high), 1.0)
    return {
        "target": [round(value, 6) for value in target],
        "position": [
            round(target[0] + diagonal * 1.15, 6),
            round(target[1] - diagonal * 1.35, 6),
            round(target[2] + diagonal * 0.9, 6),
        ],
        "near": 0.01,
        "far": round(max(50.0, diagonal * 10), 6),
    }


def build_spatial_scene(
    *,
    source_ifc: Path,
    revised_ifc: Path,
    artifact: dict,
    change: dict,
    output_directory: Path,
    cache: SpatialSessionCache | None = None,
    include_viewer: bool = True,
) -> SpatialSceneResult:
    """Build one path-sanitized local scene without copying either IFC binary."""
    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists():
        raise FileExistsError(f"Refusing to overwrite R4 product scene: {output_directory}")
    change_type = str(change.get("change_type", ""))
    if change_type not in ROLE_BY_CHANGE_TYPE:
        raise R4SpatialCandidateError("unsupported_change_type")
    global_id = str(change.get("global_id", ""))
    if len(global_id) != 22:
        raise R4SpatialCandidateError("target_global_id_missing")
    selected_role = ROLE_BY_CHANGE_TYPE[change_type]
    cache = cache or SpatialSessionCache()
    input_hashes = cache.verify_inputs(source_ifc, revised_ifc, artifact)
    selected_path = source_ifc if selected_role == "source" else revised_ifc
    model = cache.model(selected_role, selected_path)
    if model.schema != "IFC4":
        raise R4SpatialCandidateError("unsupported_schema")
    target = _optional_by_guid(model, global_id)
    if target is None:
        raise R4SpatialCandidateError("target_absent_from_selected_revision")
    if target.is_a() != change.get("entity_type"):
        raise R4SpatialCandidateError("target_entity_type_mismatch")
    _direct_storey(target)
    get_bounds = lambda element: cache.bounds(selected_role, element)
    get_bounds(target)
    changed_global_ids = {
        str(item.get("global_id"))
        for item in artifact.get("changes", [])
        if item.get("global_id")
    }
    context = _context(model, target, changed_global_ids, get_bounds)
    elements = [target] + [element for element, _ in context]
    output_directory.mkdir(parents=True)
    scene_path = output_directory / "scenes" / f"{global_id}-{selected_role}.glb"
    highlight = COLOURS[change_type]
    meshes = [
        MeshInput(
            element=element,
            metadata={
                "change_id": str(change.get("change_id", global_id)),
                "entity_type": element.is_a(),
                "global_id": element.GlobalId,
                "ifc_role": selected_role,
                "role": "target" if element.GlobalId == global_id else "context",
                "storey_global_id": _direct_storey(element).GlobalId,
                "storey_name": _direct_storey(element).Name,
            },
            colour=highlight if element.GlobalId == global_id else COLOURS["context"],
            geometry=cache.geometry(selected_role, element),
        )
        for element in elements
    ]
    try:
        write_glb(scene_path, meshes, scene_id=str(change.get("change_id", global_id)))
    except Exception as error:
        raise R4SpatialCandidateError("context_conversion_failed") from error
    if include_viewer:
        shutil.copytree(VIEWER_RESOURCE_ROOT, output_directory / "viewer")
    nodes = [_node(target, role="target", distance_m=0.0)] + [
        _node(element, role="context", distance_m=distance)
        for element, distance in context
    ]
    scene_hash = _sha256(scene_path)
    manifest = {
        "schema_version": "0.1.0-product-candidate",
        "contract_version": CONTRACT_VERSION,
        "inputs": {
            "source": {"sha256": input_hashes["source"], "schema": "IFC4"},
            "revised": {"sha256": input_hashes["revised"], "schema": "IFC4"},
        },
        "viewer": {"cdn": False, "uploads": False},
        "scenes": [
            {
                "change_id": str(change.get("change_id", global_id)),
                "change_type": change_type,
                "target_global_id": global_id,
                "selected_ifc_role": selected_role,
                "file": scene_path.relative_to(output_directory).as_posix(),
                "sha256": scene_hash,
                "highlight_colour": highlight,
                "context_colour": COLOURS["context"],
                "nodes": nodes,
                "camera": _camera(elements, get_bounds),
            }
        ],
        "privacy": {
            "ifc_binaries_copied": 0,
            "absolute_paths": 0,
            "uploads": 0,
            "model_or_api_calls": 0,
        },
    }
    manifest_path = output_directory / "manifest.json"
    cache.verify_inputs(source_ifc, revised_ifc, artifact)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return SpatialSceneResult(
        bundle=output_directory,
        entrypoint=output_directory / "viewer" / "index.html",
        manifest=manifest_path,
        target_global_id=global_id,
        selected_ifc_role=selected_role,
        scene_sha256=scene_hash,
        context_count=len(context),
    )
