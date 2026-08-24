"""Fail-closed R3-A2 and R3-A3 reconstruction primitives."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any

import ifcopenshell
import numpy as np
from ifcdiff import IfcDiff, __version__ as ifcdiff_version
from ifcopenshell.util.placement import get_local_placement
from ifcopenshell.util.unit import calculate_unit_scale


DIMENSION_FIELDS = ("profile_x_m", "profile_y_m", "extrusion_depth_m")
MIN_DIMENSION_TOLERANCE_M = 1e-6
MATRIX_TOLERANCE = 1e-8


class R3ClassificationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _round(value: float) -> float:
    value = round(float(value), 12)
    return 0.0 if value == 0 else value


def run_geometry_diff(source: ifcopenshell.file, revised: ifcopenshell.file) -> dict[str, Any]:
    detector = IfcDiff(source, revised, relationships=["geometry"], is_shallow=False, filter_elements=None)
    with redirect_stdout(io.StringIO()):
        detector.diff()
    return {"added": sorted(detector.added_elements), "deleted": sorted(detector.deleted_elements), "changed": detector.change_register}


def _element(model: ifcopenshell.file, global_id: str):
    matches = [entity for entity in model.by_type("IfcRoot") if getattr(entity, "GlobalId", None) == global_id]
    if len(matches) != 1 or not matches[0].is_a("IfcElement"):
        raise R3ClassificationError("identity_unresolved", "GlobalId must resolve to one IfcElement")
    return matches[0]


def _solid(element):
    representation = element.Representation
    bodies = [rep for rep in (representation.Representations if representation else []) if rep.RepresentationIdentifier == "Body"]
    if len(bodies) != 1 or len(bodies[0].Items) != 1 or not bodies[0].Items[0].is_a("IfcExtrudedAreaSolid"):
        raise R3ClassificationError("representation_unsupported", "Expected one Body IfcExtrudedAreaSolid")
    solid = bodies[0].Items[0]
    if not solid.SweptArea.is_a("IfcRectangleProfileDef"):
        raise R3ClassificationError("profile_kind_unsupported", "Expected IfcRectangleProfileDef")
    return solid


def _precision_m(model: ifcopenshell.file) -> float:
    contexts = [context for context in model.by_type("IfcGeometricRepresentationContext") if context.ContextType == "Model"]
    precision = float(contexts[0].Precision or 1e-5) if contexts else 1e-5
    return precision * float(calculate_unit_scale(model))


def reconstruct_extrusion(model: ifcopenshell.file, global_id: str) -> dict[str, Any]:
    element = _element(model, global_id)
    solid = _solid(element)
    profile = solid.SweptArea
    scale = float(calculate_unit_scale(model))
    direction = np.asarray(solid.ExtrudedDirection.DirectionRatios, dtype=float)
    direction /= np.linalg.norm(direction)
    return {
        "global_id": element.GlobalId,
        "entity_type": element.is_a(),
        "object_matrix": np.asarray(get_local_placement(element.ObjectPlacement), dtype=float).round(12).tolist(),
        "profile_kind": profile.is_a(),
        "profile_position": None if profile.Position is None else profile.Position.get_info(recursive=True),
        "extrusion_position": solid.Position.get_info(recursive=True),
        "extrusion_direction": [_round(value) for value in direction],
        "openings": sorted(item.RelatedOpeningElement.GlobalId for item in (element.HasOpenings or [])),
        "projections": sorted(item.RelatedFeatureElement.GlobalId for item in (element.HasProjections or [])),
        "dimensions_m": {
            "profile_x_m": _round(profile.XDim * scale),
            "profile_y_m": _round(profile.YDim * scale),
            "extrusion_depth_m": _round(solid.Depth * scale),
        },
        "precision_m": _round(_precision_m(model)),
        "unit_scale_to_m": _round(scale),
    }


def classify_extrusion_dimension_change(source, revised, raw: dict[str, Any], global_id: str) -> dict[str, Any]:
    flags = raw.get("changed", {}).get(global_id)
    ifcdiff_geometry_flag = isinstance(flags, dict) and flags.get("geometry_changed") is True
    old = reconstruct_extrusion(source, global_id)
    new = reconstruct_extrusion(revised, global_id)
    for key in ("global_id", "entity_type", "profile_kind", "profile_position", "extrusion_position", "extrusion_direction", "openings", "projections"):
        if old[key] != new[key]:
            raise R3ClassificationError(f"{key}_changed", f"{key} is outside extrusion_dimension_change")
    if np.max(np.abs(np.asarray(old["object_matrix"]) - np.asarray(new["object_matrix"]))) > MATRIX_TOLERANCE:
        raise R3ClassificationError("placement_or_rotation_changed", "Object placement changed")
    tolerance = max(MIN_DIMENSION_TOLERANCE_M, 10 * old["precision_m"], 10 * new["precision_m"])
    dimensions = []
    for field in DIMENSION_FIELDS:
        before = old["dimensions_m"][field]
        after = new["dimensions_m"][field]
        delta = _round(after - before)
        if abs(delta) > tolerance:
            dimensions.append({"field": field, "old_m": before, "new_m": after, "delta_m": delta})
    if not dimensions:
        raise R3ClassificationError("no_parameter_delta", "No supported parameter changed above tolerance")
    return {
        "change_type": "geometry_modified", "geometry_subtype": "extrusion_dimension_change",
        "global_id": global_id, "entity_type": new["entity_type"], "length_unit": "m",
        "changed_dimensions": dimensions, "dimension_tolerance_m": _round(tolerance),
        "evidence": {
            "primary_detector": "direct_ifc_parameter_comparison",
            "reconstruction_rule": "rectangular-extrusion-parameters-v1",
            "ifcdiff": {
                "detector": f"IfcDiff {ifcdiff_version}",
                "selector": f"changed.{global_id}.geometry_changed",
                "geometry_changed": ifcdiff_geometry_flag,
                "known_limit": "symmetric profile changes may preserve IfcDiff 0.8.5 shape summary extrema and sum",
            },
        },
    }
