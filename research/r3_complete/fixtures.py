"""Deterministic synthetic IFC4 fixtures for the complete R3 programme."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

import ifcopenshell
import ifcopenshell.api
import numpy as np


GUID_NAMESPACE = uuid.UUID("c6f6a3a1-f466-4e1c-93c7-d11c707707c4")
TARGET_GUID = ifcopenshell.guid.compress(uuid.uuid5(GUID_NAMESPACE, "target").hex)


def guid(label: str) -> str:
    return ifcopenshell.guid.compress(uuid.uuid5(GUID_NAMESPACE, label).hex)


def _root(model: ifcopenshell.file, ifc_class: str, name: str, label: str):
    entity = ifcopenshell.api.run("root.create_entity", model, ifc_class=ifc_class, name=name)
    entity.GlobalId = guid(label)
    return entity


def build_rectangular_extrusion_model() -> ifcopenshell.file:
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = _root(model, "IfcProject", "R3 synthetic project", "project")
    length = ifcopenshell.api.run("unit.add_si_unit", model, unit_type="LENGTHUNIT", prefix="MILLI")
    ifcopenshell.api.run("unit.assign_unit", model, units=[length])
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run(
        "context.add_context", model, context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=context,
    )
    site = _root(model, "IfcSite", "Site", "site")
    building = _root(model, "IfcBuilding", "Building", "building")
    storey_a = _root(model, "IfcBuildingStorey", "Level A", "storey-a")
    storey_b = _root(model, "IfcBuildingStorey", "Level B", "storey-b")
    assembly_a = _root(model, "IfcElementAssembly", "Assembly A", "assembly-a")
    assembly_b = _root(model, "IfcElementAssembly", "Assembly B", "assembly-b")
    space_a = _root(model, "IfcSpace", "Space A", "space-a")
    space_b = _root(model, "IfcSpace", "Space B", "space-b")
    wall = _root(model, "IfcWall", "R3 target", "target")
    wall_type_a = _root(model, "IfcWallType", "Wall Type A", "type-a")
    wall_type_b = _root(model, "IfcWallType", "Wall Type B", "type-b")
    for products, parent, label in (
        ([site], project, "project-site"), ([building], site, "site-building"),
        ([storey_a, storey_b], building, "building-storeys"),
    ):
        relation = ifcopenshell.api.run("aggregate.assign_object", model, products=products, relating_object=parent)
        relation.GlobalId = guid("rel-" + label)
    relation = ifcopenshell.api.run("spatial.assign_container", model, products=[wall, assembly_a, assembly_b], relating_structure=storey_a)
    relation.GlobalId = guid("rel-containment-a")
    relation = ifcopenshell.api.run("aggregate.assign_object", model, products=[space_a], relating_object=storey_a)
    relation.GlobalId = guid("rel-space-a")
    relation = ifcopenshell.api.run("aggregate.assign_object", model, products=[space_b], relating_object=storey_b)
    relation.GlobalId = guid("rel-space-b")
    profile = ifcopenshell.api.run("profile.add_parameterized_profile", model, ifc_class="IfcRectangleProfileDef")
    profile.ProfileName = "R3 rectangle"
    profile.XDim = 1000.0
    profile.YDim = 2000.0
    representation = ifcopenshell.api.run("geometry.add_profile_representation", model, context=body, profile=profile, depth=3.0)
    ifcopenshell.api.run("geometry.assign_representation", model, product=wall, representation=representation)
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=wall, matrix=np.eye(4), is_si=True)
    relation = ifcopenshell.api.run("type.assign_type", model, related_objects=[wall], relating_type=wall_type_a)
    relation.GlobalId = guid("rel-type-a")
    material_a = ifcopenshell.api.run("material.add_material", model, name="Material A", category="R3")
    material_b = ifcopenshell.api.run("material.add_material", model, name="Material B", category="R3")
    relation = ifcopenshell.api.run("material.assign_material", model, products=[wall], type="IfcMaterial", material=material_a)
    relation.GlobalId = guid("rel-material-a")
    model.header.file_name.time_stamp = "2026-08-24T00:00:00"
    model.header.file_name.author = ("BIMChange-Agent",)
    model.header.file_name.organization = ("Synthetic R3 research",)
    return model


def _solid(model: ifcopenshell.file):
    wall = model.by_guid(TARGET_GUID)
    return wall.Representation.Representations[0].Items[0]


def write_rectangular_pair(
    root: Path,
    variant: Literal[
        "noop", "profile_x", "profile_y", "depth", "all_dimensions",
        "placement", "direction", "profile_kind", "opening",
    ],
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    source_path = root / "source.ifc"
    revised_path = root / f"revised-{variant}.ifc"
    model = build_rectangular_extrusion_model()
    model.write(source_path)
    revised = ifcopenshell.open(source_path)
    wall = revised.by_guid(TARGET_GUID)
    solid = _solid(revised)
    if variant == "profile_x":
        solid.SweptArea.XDim = 1250.0
    elif variant == "profile_y":
        solid.SweptArea.YDim = 2400.0
    elif variant == "depth":
        solid.Depth = 3500.0
    elif variant == "all_dimensions":
        solid.SweptArea.XDim = 1250.0
        solid.SweptArea.YDim = 2400.0
        solid.Depth = 3500.0
    elif variant == "placement":
        solid.SweptArea.XDim = 1250.0
        matrix = np.eye(4)
        matrix[0, 3] = 0.25
        ifcopenshell.api.run("geometry.edit_object_placement", revised, product=wall, matrix=matrix, is_si=True)
    elif variant == "direction":
        solid.SweptArea.XDim = 1250.0
        solid.ExtrudedDirection.DirectionRatios = (0.0, 1.0, 0.0)
    elif variant == "profile_kind":
        solid.SweptArea = revised.create_entity("IfcCircleProfileDef", ProfileType="AREA", Radius=500.0)
    elif variant == "opening":
        solid.SweptArea.XDim = 1250.0
        opening = _root(revised, "IfcOpeningElement", "Synthetic opening", "opening")
        relation = revised.create_entity(
            "IfcRelVoidsElement", GlobalId=guid("rel-opening"),
            RelatingBuildingElement=wall, RelatedOpeningElement=opening,
        )
        relation.Name = "R3 opening"
    elif variant != "noop":
        raise ValueError(variant)
    revised.write(revised_path)
    return source_path, revised_path


def write_relationship_pair(
    root: Path,
    variant: Literal["container_storey", "container_space", "aggregate", "type", "material"],
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    source_path = root / "source.ifc"
    revised_path = root / f"revised-{variant}.ifc"
    source = build_rectangular_extrusion_model()
    wall = source.by_guid(TARGET_GUID)
    if variant == "container_space":
        ifcopenshell.api.run("spatial.assign_container", source, products=[wall], relating_structure=source.by_guid(guid("space-a")))
    elif variant == "aggregate":
        ifcopenshell.api.run("aggregate.assign_object", source, products=[wall], relating_object=source.by_guid(guid("assembly-a")))
    source.write(source_path)
    revised = ifcopenshell.open(source_path)
    wall = revised.by_guid(TARGET_GUID)
    if variant == "container_storey":
        ifcopenshell.api.run("spatial.assign_container", revised, products=[wall], relating_structure=revised.by_guid(guid("storey-b")))
    elif variant == "container_space":
        ifcopenshell.api.run("spatial.assign_container", revised, products=[wall], relating_structure=revised.by_guid(guid("space-b")))
    elif variant == "aggregate":
        ifcopenshell.api.run("aggregate.assign_object", revised, products=[wall], relating_object=revised.by_guid(guid("assembly-b")))
    elif variant == "type":
        ifcopenshell.api.run("type.assign_type", revised, related_objects=[wall], relating_type=revised.by_guid(guid("type-b")))
    elif variant == "material":
        existing = ifcopenshell.api.run("material.unassign_material", revised, products=[wall])
        del existing
        material_b = next(item for item in revised.by_type("IfcMaterial") if item.Name == "Material B")
        ifcopenshell.api.run("material.assign_material", revised, products=[wall], type="IfcMaterial", material=material_b)
    else:
        raise ValueError(variant)
    revised.write(revised_path)
    return source_path, revised_path
