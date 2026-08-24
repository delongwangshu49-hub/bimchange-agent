"""One bounded R3-A3 general-shape subtype: tessellated vertex deformation."""

from __future__ import annotations

import numpy as np
from ifcdiff import __version__ as ifcdiff_version

from research.r3_geometry.protocol import reconstruct_element_geometry

from .geometry import MATRIX_TOLERANCE, R3ClassificationError


def _triangulated_item(model, global_id: str):
    element = model.by_guid(global_id)
    representation = element.Representation
    bodies = [rep for rep in (representation.Representations if representation else []) if rep.RepresentationIdentifier == "Body"]
    if len(bodies) != 1 or len(bodies[0].Items) != 1 or not bodies[0].Items[0].is_a("IfcTriangulatedFaceSet"):
        raise R3ClassificationError("shape_representation_unsupported", "Expected one Body IfcTriangulatedFaceSet")
    return bodies[0].Items[0]


def classify_tessellated_shape_change(source, revised, raw, global_id: str):
    flags = raw.get("changed", {}).get(global_id)
    if not isinstance(flags, dict) or flags.get("geometry_changed") is not True:
        raise R3ClassificationError("detector_evidence_missing", "IfcDiff geometry_changed is required")
    old_item, new_item = _triangulated_item(source, global_id), _triangulated_item(revised, global_id)
    old = reconstruct_element_geometry(source, global_id, role="source")
    new = reconstruct_element_geometry(revised, global_id, role="revised")
    if (old["global_id"], old["entity_type"]) != (new["global_id"], new["entity_type"]):
        raise R3ClassificationError("identity_changed", "Identity changed")
    if np.max(np.abs(np.asarray(old["object_matrix_si"]) - np.asarray(new["object_matrix_si"]))) > MATRIX_TOLERANCE:
        raise R3ClassificationError("placement_or_rotation_changed", "Placement changed")
    if old["openings"] != new["openings"] or old["projections"] != new["projections"]:
        raise R3ClassificationError("feature_relationship_changed", "Openings or projections changed")
    old_faces = [list(face) for face in old_item.CoordIndex]
    new_faces = [list(face) for face in new_item.CoordIndex]
    if old_faces != new_faces:
        raise R3ClassificationError("tessellated_topology_changed", "Topology changes remain unsupported")
    if old["local_mesh"]["sha256"] == new["local_mesh"]["sha256"]:
        raise R3ClassificationError("local_shape_unchanged", "Local shape did not change")
    old_points = np.asarray(old_item.Coordinates.CoordList, dtype=float)
    new_points = np.asarray(new_item.Coordinates.CoordList, dtype=float)
    if old_points.shape != new_points.shape:
        raise R3ClassificationError("vertex_cardinality_changed", "Vertex cardinality changes remain unsupported")
    scale = old["unit_scale_to_m"]
    deltas = np.linalg.norm((new_points - old_points) * scale, axis=1)
    changed_vertices = int(np.count_nonzero(deltas > 1e-6))
    if changed_vertices == 0:
        raise R3ClassificationError("below_shape_tolerance", "Vertex changes are below tolerance")
    return {
        "change_type": "geometry_modified",
        "geometry_subtype": "tessellated_vertex_geometry_change",
        "global_id": global_id,
        "entity_type": new["entity_type"],
        "changed_vertex_count": changed_vertices,
        "max_vertex_displacement_m": round(float(deltas.max()), 9),
        "topology_unchanged": True,
        "old_local_shape_sha256": old["local_mesh"]["sha256"],
        "new_local_shape_sha256": new["local_mesh"]["sha256"],
        "old_local_bbox_m": {"min": old["local_mesh"]["bbox_min_m"], "max": old["local_mesh"]["bbox_max_m"]},
        "new_local_bbox_m": {"min": new["local_mesh"]["bbox_min_m"], "max": new["local_mesh"]["bbox_max_m"]},
        "evidence": {
            "detector": f"IfcDiff {ifcdiff_version}",
            "selector": f"changed.{global_id}.geometry_changed",
            "reconstruction_rule": "ifc-triangulated-face-set-vertex-deformation-v1",
        },
    }
