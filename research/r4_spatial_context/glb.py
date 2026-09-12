"""Small deterministic glTF 2.0 binary writer for the bounded R4 proof."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import ifcopenshell.geom


GLB_MAGIC = 0x46546C67
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942


@dataclass(frozen=True)
class MeshInput:
    element: object
    metadata: dict
    colour: str


def _colour_factor(value: str) -> list[float]:
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError(f"Invalid colour: {value}")
    return [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)] + [1.0]


def _geometry(element) -> tuple[list[float], list[int]]:
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    shape = ifcopenshell.geom.create_shape(settings, element)
    vertices = [float(value) for value in shape.geometry.verts]
    indices = [int(value) for value in shape.geometry.faces]
    if not vertices or len(vertices) % 3 or not indices or len(indices) % 3:
        raise ValueError(f"Element {element.GlobalId} has no triangle geometry")
    if min(indices) < 0 or max(indices) >= len(vertices) // 3:
        raise ValueError(f"Element {element.GlobalId} has invalid triangle indices")
    return vertices, indices


def _normals(vertices: list[float], indices: list[int]) -> list[float]:
    result = [0.0] * len(vertices)
    for offset in range(0, len(indices), 3):
        ia, ib, ic = (indices[offset + index] * 3 for index in range(3))
        ax, ay, az = vertices[ia : ia + 3]
        bx, by, bz = vertices[ib : ib + 3]
        cx, cy, cz = vertices[ic : ic + 3]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        for index in (ia, ib, ic):
            result[index] += nx
            result[index + 1] += ny
            result[index + 2] += nz
    for offset in range(0, len(result), 3):
        length = math.sqrt(sum(value * value for value in result[offset : offset + 3]))
        if length <= 1e-12:
            result[offset : offset + 3] = [0.0, 0.0, 1.0]
        else:
            result[offset : offset + 3] = [
                value / length for value in result[offset : offset + 3]
            ]
    return result


def _append_aligned(payload: bytearray, data: bytes) -> tuple[int, int]:
    while len(payload) % 4:
        payload.append(0)
    offset = len(payload)
    payload.extend(data)
    return offset, len(data)


def _bounds(vertices: list[float]) -> tuple[list[float], list[float]]:
    axes = [vertices[index::3] for index in range(3)]
    return [min(axis) for axis in axes], [max(axis) for axis in axes]


def build_glb(meshes: Iterable[MeshInput], *, scene_id: str) -> bytes:
    ordered = sorted(meshes, key=lambda item: item.element.GlobalId)
    if not ordered:
        raise ValueError("At least one mesh is required")
    buffer = bytearray()
    buffer_views: list[dict] = []
    accessors: list[dict] = []
    materials: list[dict] = []
    gltf_meshes: list[dict] = []
    nodes: list[dict] = []

    for item in ordered:
        vertices, indices = _geometry(item.element)
        normals = _normals(vertices, indices)
        minimum, maximum = _bounds(vertices)
        position_offset, position_length = _append_aligned(
            buffer, struct.pack(f"<{len(vertices)}f", *vertices)
        )
        normal_offset, normal_length = _append_aligned(
            buffer, struct.pack(f"<{len(normals)}f", *normals)
        )
        index_offset, index_length = _append_aligned(
            buffer, struct.pack(f"<{len(indices)}I", *indices)
        )
        position_view = len(buffer_views)
        buffer_views.append(
            {"buffer": 0, "byteOffset": position_offset, "byteLength": position_length, "target": 34962}
        )
        normal_view = len(buffer_views)
        buffer_views.append(
            {"buffer": 0, "byteOffset": normal_offset, "byteLength": normal_length, "target": 34962}
        )
        index_view = len(buffer_views)
        buffer_views.append(
            {"buffer": 0, "byteOffset": index_offset, "byteLength": index_length, "target": 34963}
        )
        position_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": position_view,
                "componentType": 5126,
                "count": len(vertices) // 3,
                "type": "VEC3",
                "min": minimum,
                "max": maximum,
            }
        )
        normal_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": normal_view,
                "componentType": 5126,
                "count": len(normals) // 3,
                "type": "VEC3",
            }
        )
        index_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": index_view,
                "componentType": 5125,
                "count": len(indices),
                "type": "SCALAR",
                "min": [min(indices)],
                "max": [max(indices)],
            }
        )
        material_index = len(materials)
        materials.append(
            {
                "name": f"{item.metadata['role']}-{item.element.GlobalId}",
                "doubleSided": True,
                "pbrMetallicRoughness": {
                    "baseColorFactor": _colour_factor(item.colour),
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.7,
                },
            }
        )
        mesh_index = len(gltf_meshes)
        gltf_meshes.append(
            {
                "name": item.element.GlobalId,
                "primitives": [
                    {
                        "attributes": {"POSITION": position_accessor, "NORMAL": normal_accessor},
                        "indices": index_accessor,
                        "material": material_index,
                        "mode": 4,
                    }
                ],
            }
        )
        nodes.append(
            {
                "name": item.element.GlobalId,
                "mesh": mesh_index,
                "extras": dict(sorted(item.metadata.items())),
            }
        )

    document = {
        "accessors": accessors,
        "asset": {
            "version": "2.0",
            "generator": "BIMChange-Agent R4 bounded GLB writer",
            "extras": {"protocol_version": "r4-local-spatial-context-0.1.0", "scene_id": scene_id},
        },
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(buffer)}],
        "materials": materials,
        "meshes": gltf_meshes,
        "nodes": nodes,
        "scene": 0,
        "scenes": [{"name": scene_id, "nodes": list(range(len(nodes)))}],
    }
    json_payload = json.dumps(
        document, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    json_payload += b" " * ((-len(json_payload)) % 4)
    binary_payload = bytes(buffer) + b"\x00" * ((-len(buffer)) % 4)
    total_length = 12 + 8 + len(json_payload) + 8 + len(binary_payload)
    return b"".join(
        (
            struct.pack("<III", GLB_MAGIC, GLB_VERSION, total_length),
            struct.pack("<II", len(json_payload), JSON_CHUNK),
            json_payload,
            struct.pack("<II", len(binary_payload), BIN_CHUNK),
            binary_payload,
        )
    )


def write_glb(path: Path, meshes: Iterable[MeshInput], *, scene_id: str) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite GLB: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_glb(meshes, scene_id=scene_id))


def read_glb_document(path: Path) -> dict:
    payload = path.read_bytes()
    if len(payload) < 28:
        raise ValueError("GLB is too short")
    magic, version, total_length = struct.unpack_from("<III", payload, 0)
    if (magic, version, total_length) != (GLB_MAGIC, GLB_VERSION, len(payload)):
        raise ValueError("Invalid GLB header")
    json_length, json_type = struct.unpack_from("<II", payload, 12)
    if json_type != JSON_CHUNK:
        raise ValueError("First GLB chunk is not JSON")
    json_end = 20 + json_length
    if json_end + 8 > len(payload):
        raise ValueError("GLB JSON chunk is truncated")
    binary_length, binary_type = struct.unpack_from("<II", payload, json_end)
    if binary_type != BIN_CHUNK or json_end + 8 + binary_length != len(payload):
        raise ValueError("Invalid GLB binary chunk")
    return json.loads(payload[20:json_end].decode("utf-8").rstrip(" "))

