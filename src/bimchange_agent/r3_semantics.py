"""Reusable fail-closed semantics promoted from the controlled R3 gate."""

from __future__ import annotations

from typing import Any

import numpy as np
from ifcopenshell.util.element import get_aggregate, get_container, get_material, get_type
from ifcopenshell.util.placement import get_local_placement
from ifcopenshell.util.unit import calculate_unit_scale

from .geometry_product_candidate import (
    ROTATION_TOLERANCE,
    GeometryClassificationError,
    _element_facts,
)


MIN_DIMENSION_TOLERANCE_M = 1e-6
DIMENSION_FIELDS = ("profile_x_m", "profile_y_m", "extrusion_depth_m")


def _round(value: float) -> float:
    value = round(float(value), 12)
    return 0.0 if value == 0 else value


def _element(model, global_id: str):
    matches = [item for item in model.by_type("IfcRoot") if getattr(item, "GlobalId", None) == global_id]
    if len(matches) != 1 or not matches[0].is_a("IfcElement"):
        raise GeometryClassificationError("identity_unresolved", "Expected one IfcElement")
    return matches[0]


def _rectangular_solid(element):
    representation = element.Representation
    bodies = [rep for rep in (representation.Representations if representation else []) if rep.RepresentationIdentifier == "Body"]
    if len(bodies) != 1 or len(bodies[0].Items) != 1 or not bodies[0].Items[0].is_a("IfcExtrudedAreaSolid"):
        raise GeometryClassificationError("representation_unsupported", "Expected one Body IfcExtrudedAreaSolid")
    solid = bodies[0].Items[0]
    if not solid.SweptArea.is_a("IfcRectangleProfileDef"):
        raise GeometryClassificationError("profile_kind_unsupported", "Expected IfcRectangleProfileDef")
    return solid


def _precision_m(model) -> float:
    contexts = [context for context in model.by_type("IfcGeometricRepresentationContext") if context.ContextType == "Model"]
    return float(contexts[0].Precision or 1e-5) * float(calculate_unit_scale(model)) if contexts else 1e-5


def _extrusion_facts(model, global_id: str) -> dict[str, Any]:
    element = _element(model, global_id)
    solid = _rectangular_solid(element)
    profile = solid.SweptArea
    scale = float(calculate_unit_scale(model))
    direction = np.asarray(solid.ExtrudedDirection.DirectionRatios, dtype=float)
    direction /= np.linalg.norm(direction)
    return {
        "element": element,
        "entity_type": element.is_a(),
        "matrix": np.asarray(get_local_placement(element.ObjectPlacement), dtype=float),
        "profile_kind": profile.is_a(),
        "profile_position": None if profile.Position is None else profile.Position.get_info(recursive=True),
        "solid_position": solid.Position.get_info(recursive=True),
        "direction": [_round(value) for value in direction],
        "openings": sorted(item.RelatedOpeningElement.GlobalId for item in (element.HasOpenings or [])),
        "projections": sorted(item.RelatedFeatureElement.GlobalId for item in (element.HasProjections or [])),
        "dimensions": {
            "profile_x_m": _round(profile.XDim * scale),
            "profile_y_m": _round(profile.YDim * scale),
            "extrusion_depth_m": _round(solid.Depth * scale),
        },
        "precision_m": _precision_m(model),
    }


def extrusion_dimension_change(old_model, new_model, global_id: str, *, ifcdiff_flag: bool) -> dict[str, Any]:
    old, new = _extrusion_facts(old_model, global_id), _extrusion_facts(new_model, global_id)
    for key in ("entity_type", "profile_kind", "profile_position", "solid_position", "direction", "openings", "projections"):
        if old[key] != new[key]:
            raise GeometryClassificationError(f"{key}_changed", f"{key} changed outside the slice")
    if np.max(np.abs(old["matrix"] - new["matrix"])) > ROTATION_TOLERANCE:
        raise GeometryClassificationError("placement_or_rotation_changed", "Object placement changed")
    tolerance = max(MIN_DIMENSION_TOLERANCE_M, 10 * old["precision_m"], 10 * new["precision_m"])
    dimensions = []
    for field in DIMENSION_FIELDS:
        before, after = old["dimensions"][field], new["dimensions"][field]
        delta = _round(after - before)
        if abs(delta) > tolerance:
            dimensions.append({"field": field, "old_m": before, "new_m": after, "delta_m": delta})
    if not dimensions:
        raise GeometryClassificationError("no_parameter_delta", "No supported parameter delta")
    return {
        "subtype": "extrusion_dimension_change", "length_unit": "m",
        "changed_dimensions": dimensions, "dimension_tolerance_m": _round(tolerance),
        "ifcdiff_geometry_changed": ifcdiff_flag,
    }


def tessellated_shape_change(old_model, new_model, global_id: str) -> dict[str, Any]:
    old_element, new_element = _element(old_model, global_id), _element(new_model, global_id)
    if old_element.is_a() != new_element.is_a():
        raise GeometryClassificationError("identity_changed", "Element type changed")
    def item(element):
        bodies = [rep for rep in element.Representation.Representations if rep.RepresentationIdentifier == "Body"]
        if len(bodies) != 1 or len(bodies[0].Items) != 1 or not bodies[0].Items[0].is_a("IfcTriangulatedFaceSet"):
            raise GeometryClassificationError("shape_representation_unsupported", "Expected one IfcTriangulatedFaceSet")
        return bodies[0].Items[0]
    old_item, new_item = item(old_element), item(new_element)
    old, new = _element_facts(old_model, global_id, role="source"), _element_facts(new_model, global_id, role="revised")
    if np.max(np.abs(np.asarray(old["object_matrix_si"]) - np.asarray(new["object_matrix_si"]))) > ROTATION_TOLERANCE:
        raise GeometryClassificationError("placement_or_rotation_changed", "Placement changed")
    if old["openings"] != new["openings"] or old["projections"] != new["projections"]:
        raise GeometryClassificationError("feature_relationship_changed", "Opening/projection changed")
    if [list(row) for row in old_item.CoordIndex] != [list(row) for row in new_item.CoordIndex]:
        raise GeometryClassificationError("tessellated_topology_changed", "Topology changes remain unsupported")
    if old["local_mesh"]["sha256"] == new["local_mesh"]["sha256"]:
        raise GeometryClassificationError("local_shape_unchanged", "Local shape did not change")
    old_points = np.asarray(old_item.Coordinates.CoordList, dtype=float)
    new_points = np.asarray(new_item.Coordinates.CoordList, dtype=float)
    if old_points.shape != new_points.shape:
        raise GeometryClassificationError("vertex_cardinality_changed", "Vertex cardinality changed")
    old_points_m = old_points * float(calculate_unit_scale(old_model))
    new_points_m = new_points * float(calculate_unit_scale(new_model))
    deltas = np.linalg.norm(new_points_m - old_points_m, axis=1)
    changed = int(np.count_nonzero(deltas > 1e-6))
    if not changed:
        raise GeometryClassificationError("below_shape_tolerance", "Shape change below tolerance")
    return {
        "subtype": "tessellated_vertex_geometry_change", "length_unit": "m",
        "changed_vertex_count": changed, "max_vertex_displacement_m": round(float(deltas.max()), 9),
        "topology_unchanged": True,
        "old_local_shape_sha256": old["local_mesh"]["sha256"],
        "new_local_shape_sha256": new["local_mesh"]["sha256"],
    }


def _root_ref(entity):
    return None if entity is None else {"entity_type": entity.is_a(), "global_id": entity.GlobalId, "name": getattr(entity, "Name", None)}


def _material_ref(entity):
    return None if entity is None else {"entity_type": entity.is_a(), "name": getattr(entity, "Name", None), "category": getattr(entity, "Category", None)}


def relationship_facts(model, global_id: str) -> dict[str, Any]:
    element = _element(model, global_id)
    return {
        "element": element,
        "entity_type": element.is_a(),
        "container": _root_ref(get_container(element, should_get_direct=True)),
        "aggregate": _root_ref(get_aggregate(element)),
        "type": _root_ref(get_type(element)),
        "material": _material_ref(get_material(element, should_skip_usage=False)),
    }


def relationship_change(old_model, new_model, global_id: str) -> dict[str, Any]:
    old, new = relationship_facts(old_model, global_id), relationship_facts(new_model, global_id)
    if old["entity_type"] != new["entity_type"]:
        raise GeometryClassificationError("identity_changed", "Element type changed")

    def identity(field: str, value: dict[str, Any] | None):
        if value is None:
            return None
        if field == "material":
            return value["entity_type"], value["name"], value["category"]
        return value["entity_type"], value["global_id"]

    fields = [
        field for field in ("container", "aggregate", "type", "material")
        if identity(field, old[field]) != identity(field, new[field])
    ]
    if not fields:
        raise GeometryClassificationError("no_relationship_delta", "No supported relationship changed")
    if len(fields) != 1:
        raise GeometryClassificationError("relationship_scope_ambiguous", f"Multiple relationships changed: {fields}")
    field = fields[0]
    subtype = {
        "container": "spatial_containment_change", "aggregate": "aggregation_change",
        "type": "type_assignment_change", "material": "material_assignment_change",
    }[field]
    return {"subtype": subtype, "relationship": field, "old_relation": old[field], "new_relation": new[field]}
