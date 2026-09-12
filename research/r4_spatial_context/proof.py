"""Build the deterministic standalone R4 local-viewer proof bundle."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom

from .fixture import generate_pair
from bimchange_agent.r4_glb import MeshInput, write_glb


ROOT = Path(__file__).resolve().parent
PROTOCOL_PATH = ROOT / "protocol.json"
LEDGER_PATH = ROOT / "operation-ledger.json"
VIEWER_PATH = ROOT / "viewer"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class BuildResult:
    bundle: Path
    manifest: Path
    build_seconds: float


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _direct_storey(element):
    relations = [
        relation.RelatingStructure
        for relation in element.ContainedInStructure
        if relation.is_a("IfcRelContainedInSpatialStructure")
        and relation.RelatingStructure.is_a("IfcBuildingStorey")
    ]
    if len(relations) != 1:
        raise ValueError(
            f"Expected one direct storey for {element.GlobalId}, found {len(relations)}"
        )
    return relations[0]


def _bounds(element) -> tuple[list[float], list[float]]:
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    shape = ifcopenshell.geom.create_shape(settings, element)
    vertices = [float(value) for value in shape.geometry.verts]
    if not vertices or len(vertices) % 3:
        raise ValueError(f"Missing geometry for {element.GlobalId}")
    axes = [vertices[index::3] for index in range(3)]
    return [min(axis) for axis in axes], [max(axis) for axis in axes]


def _centre(bounds: tuple[list[float], list[float]]) -> list[float]:
    return [(low + high) / 2 for low, high in zip(*bounds)]


def _distance(first: list[float], second: list[float]) -> float:
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(first, second)))


def _context_nodes(
    model: ifcopenshell.file,
    *,
    target,
    changed_global_ids: set[str],
    maximum_distance: float,
    maximum_neighbours: int,
) -> list[tuple[object, float]]:
    storey = _direct_storey(target)
    target_centre = _centre(_bounds(target))
    candidates: list[tuple[float, str, object]] = []
    for element in model.by_type("IfcElement"):
        if element.GlobalId in changed_global_ids:
            continue
        try:
            element_storey = _direct_storey(element)
            bounds = _bounds(element)
        except (RuntimeError, ValueError):
            continue
        if element_storey.GlobalId != storey.GlobalId:
            continue
        distance = _distance(target_centre, _centre(bounds))
        if distance <= maximum_distance:
            candidates.append((distance, element.GlobalId, element))
    candidates.sort(key=lambda item: (round(item[0], 9), item[1]))
    return [(element, distance) for distance, _, element in candidates[:maximum_neighbours]]


def _node_record(element, *, role: str, distance: float) -> dict:
    storey = _direct_storey(element)
    return {
        "global_id": element.GlobalId,
        "entity_type": element.is_a(),
        "storey_global_id": storey.GlobalId,
        "storey_name": storey.Name,
        "role": role,
        "distance_m": round(distance, 6),
    }


def _camera(elements: list[object]) -> dict:
    bounds = [_bounds(element) for element in elements]
    low = [min(item[0][axis] for item in bounds) for axis in range(3)]
    high = [max(item[1][axis] for item in bounds) for axis in range(3)]
    target = [(left + right) / 2 for left, right in zip(low, high)]
    diagonal = max(_distance(low, high), 1.0)
    position = [
        target[0] + diagonal * 1.15,
        target[1] - diagonal * 1.35,
        target[2] + diagonal * 0.9,
    ]
    return {
        "target": [round(value, 6) for value in target],
        "position": [round(value, 6) for value in position],
        "near": 0.01,
        "far": round(max(50.0, diagonal * 10), 6),
    }


def _relative(path: Path, bundle: Path) -> str:
    return path.relative_to(bundle).as_posix()


def build_bundle(output_directory: Path) -> BuildResult:
    started = time.perf_counter()
    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists():
        raise FileExistsError(f"Refusing to overwrite R4 proof bundle: {output_directory}")
    output_directory.mkdir(parents=True)
    inputs_directory = output_directory / "inputs"
    scenes_directory = output_directory / "scenes"
    source_path, revised_path = generate_pair(inputs_directory)
    source = ifcopenshell.open(source_path)
    revised = ifcopenshell.open(revised_path)
    models = {"source": source, "revised": revised}
    protocol = load_json(PROTOCOL_PATH)
    ledger = load_json(LEDGER_PATH)
    changed_global_ids = {item["global_id"] for item in ledger["changes"]}
    colours = protocol["colours"]
    context_policy = protocol["context_policy"]
    scenes: list[dict] = []

    for change in ledger["changes"]:
        selected_role = protocol["scene_selection"][change["change_type"]]
        if selected_role != change["selected_ifc_role"]:
            raise ValueError(f"Ledger role conflicts with protocol for {change['change_id']}")
        model = models[selected_role]
        target = model.by_guid(change["global_id"])
        if target is None:
            raise ValueError(f"Target is absent from selected {selected_role} IFC")
        if target.is_a() != change["entity_type"]:
            raise ValueError(f"Target IFC class mismatch for {change['change_id']}")
        if _direct_storey(target).GlobalId != change["storey_global_id"]:
            raise ValueError(f"Target storey mismatch for {change['change_id']}")
        context = _context_nodes(
            model,
            target=target,
            changed_global_ids=changed_global_ids,
            maximum_distance=context_policy["maximum_distance_m"],
            maximum_neighbours=context_policy["maximum_neighbours"],
        )
        nodes = [_node_record(target, role="target", distance=0.0)] + [
            _node_record(element, role="context", distance=distance)
            for element, distance in context
        ]
        elements = [target] + [element for element, _ in context]
        scene_path = scenes_directory / f"{change['change_id']}-{selected_role}.glb"
        highlight = colours[change["change_type"]]
        meshes = [
            MeshInput(
                element=element,
                metadata={
                    "change_id": change["change_id"],
                    "entity_type": element.is_a(),
                    "global_id": element.GlobalId,
                    "ifc_role": selected_role,
                    "role": "target" if element.GlobalId == target.GlobalId else "context",
                    "storey_global_id": _direct_storey(element).GlobalId,
                    "storey_name": _direct_storey(element).Name,
                },
                colour=highlight if element.GlobalId == target.GlobalId else colours["context"],
            )
            for element in elements
        ]
        write_glb(scene_path, meshes, scene_id=change["change_id"])
        scenes.append(
            {
                "change_id": change["change_id"],
                "change_type": change["change_type"],
                "target_global_id": change["global_id"],
                "selected_ifc_role": selected_role,
                "file": _relative(scene_path, output_directory),
                "sha256": sha256(scene_path),
                "highlight_colour": highlight,
                "context_colour": colours["context"],
                "nodes": nodes,
                "camera": _camera(elements),
            }
        )

    shutil.copytree(VIEWER_PATH, output_directory / "viewer")
    payload_bytes = sum(
        path.stat().st_size
        for path in output_directory.rglob("*")
        if path.is_file()
    )
    manifest = {
        "schema_version": "0.1.0",
        "protocol_version": protocol["protocol_version"],
        "inputs": {
            "source": {
                "role": "source",
                "file": _relative(source_path, output_directory),
                "sha256": sha256(source_path),
                "schema": source.schema,
            },
            "revised": {
                "role": "revised",
                "file": _relative(revised_path, output_directory),
                "sha256": sha256(revised_path),
                "schema": revised.schema,
            },
        },
        "context_policy": {
            "maximum_distance_m": context_policy["maximum_distance_m"],
            "maximum_neighbours": context_policy["maximum_neighbours"],
            "same_storey_only": context_policy["same_storey_only"],
        },
        "viewer": {
            "entrypoint": "viewer/index.html",
            "local_assets": [
                "viewer/app.js",
                "viewer/styles.css",
                "viewer/vendor/three.module.js",
                "viewer/vendor/three.core.js",
                "viewer/vendor/addons/loaders/GLTFLoader.js",
                "viewer/vendor/addons/controls/OrbitControls.js",
                "viewer/vendor/addons/utils/BufferGeometryUtils.js",
                "viewer/vendor/addons/utils/SkeletonUtils.js",
                "viewer/vendor/THREE-LICENSE.txt",
            ],
            "cdn": False,
            "uploads": False,
        },
        "scenes": scenes,
        "metrics": {
            "payload_bytes_excluding_manifest": payload_bytes,
            "model_or_api_calls": 0,
            "privacy_violations": 0,
        },
    }
    manifest_path = output_directory / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return BuildResult(
        bundle=output_directory,
        manifest=manifest_path,
        build_seconds=time.perf_counter() - started,
    )
