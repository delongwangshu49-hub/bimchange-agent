"""Direct, fail-closed R3-B relationship reconstruction."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any

from ifcdiff import IfcDiff, __version__ as ifcdiff_version
from ifcopenshell.util.element import get_aggregate, get_container, get_material, get_type

from .geometry import R3ClassificationError, _element


RELATIONSHIP_FIELDS = {
    "container": "spatial_containment_change",
    "aggregate": "aggregation_change",
    "type": "type_assignment_change",
    "material": "material_assignment_change",
}


def _root_reference(entity) -> dict[str, Any] | None:
    if entity is None:
        return None
    return {"entity_type": entity.is_a(), "global_id": entity.GlobalId, "name": getattr(entity, "Name", None)}


def _material_reference(material) -> dict[str, Any] | None:
    if material is None:
        return None
    return {
        "entity_type": material.is_a(), "name": getattr(material, "Name", None),
        "category": getattr(material, "Category", None),
    }


def reconstruct_relationships(model, global_id: str) -> dict[str, Any]:
    element = _element(model, global_id)
    return {
        "global_id": element.GlobalId,
        "entity_type": element.is_a(),
        "container": _root_reference(get_container(element, should_get_direct=True)),
        "aggregate": _root_reference(get_aggregate(element)),
        "type": _root_reference(get_type(element)),
        "material": _material_reference(get_material(element, should_skip_usage=False)),
    }


def run_relationship_diff(source, revised) -> dict[str, Any]:
    detector = IfcDiff(source, revised, relationships=["container", "aggregate", "type"], is_shallow=False, filter_elements=None)
    with redirect_stdout(io.StringIO()):
        detector.diff()
    return {"added": sorted(detector.added_elements), "deleted": sorted(detector.deleted_elements), "changed": detector.change_register}


def classify_relationship_change(source, revised, raw: dict[str, Any], global_id: str) -> dict[str, Any]:
    old = reconstruct_relationships(source, global_id)
    new = reconstruct_relationships(revised, global_id)
    if (old["global_id"], old["entity_type"]) != (new["global_id"], new["entity_type"]):
        raise R3ClassificationError("identity_changed", "Element identity changed")
    changed = [field for field in RELATIONSHIP_FIELDS if old[field] != new[field]]
    if len(changed) != 1:
        raise R3ClassificationError("relationship_scope_ambiguous", f"Expected one changed relationship, found {changed}")
    field = changed[0]
    flag_name = {"container": "container_changed", "aggregate": "aggregate_changed", "type": "type_changed"}.get(field)
    flags = raw.get("changed", {}).get(global_id, {})
    observed = bool(flag_name and isinstance(flags, dict) and flags.get(flag_name) is True)
    return {
        "change_type": "relationship_modified", "relationship_subtype": RELATIONSHIP_FIELDS[field],
        "global_id": global_id, "entity_type": new["entity_type"],
        "relationship": field, "old_relation": old[field], "new_relation": new[field],
        "evidence": {
            "primary_detector": "direct_ifc_relationship_comparison",
            "reconstruction_rule": f"r3b-{field}-v1",
            "ifcdiff": {
                "detector": f"IfcDiff {ifcdiff_version}", "flag": flag_name,
                "observed": observed,
                "known_limit": "0.8.5 compares cross-file relationship entity instances and can miss the requested flag or emit unrelated relationship flags",
                "material_not_supported_by_ifcdiff_0_8_5": field == "material",
            },
        },
    }
