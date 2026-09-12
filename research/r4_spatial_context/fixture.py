"""Create the pre-registered synthetic IFC4 pair for the R4 viewer proof."""

from __future__ import annotations

import uuid
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
import numpy as np


GUID_NAMESPACE = uuid.UUID("873cf259-7bf0-4e4b-9da4-62122d60c6d7")
FIXED_TIMESTAMP = "2026-08-25T00:00:00"
SOURCE_NAME = "r4-spatial-source.ifc"
REVISED_NAME = "r4-spatial-revised.ifc"


def guid(label: str) -> str:
    return ifcopenshell.guid.compress(uuid.uuid5(GUID_NAMESPACE, label).hex)


def _root(model: ifcopenshell.file, ifc_class: str, name: str, label: str):
    entity = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class=ifc_class, name=name
    )
    entity.GlobalId = guid(label)
    return entity


def _body_context(model: ifcopenshell.file):
    return next(
        context
        for context in model.by_type("IfcGeometricRepresentationSubContext")
        if context.ContextIdentifier == "Body"
    )


def _place_box(
    model: ifcopenshell.file,
    product,
    *,
    size: tuple[float, float, float],
    origin: tuple[float, float, float],
) -> None:
    profile = ifcopenshell.api.run(
        "profile.add_parameterized_profile",
        model,
        ifc_class="IfcRectangleProfileDef",
    )
    profile.ProfileName = f"R4 box {product.GlobalId}"
    profile.XDim = size[0]
    profile.YDim = size[1]
    representation = ifcopenshell.api.run(
        "geometry.add_profile_representation",
        model,
        context=_body_context(model),
        profile=profile,
        depth=size[2],
    )
    ifcopenshell.api.run(
        "geometry.assign_representation",
        model,
        product=product,
        representation=representation,
    )
    matrix = np.eye(4)
    matrix[:3, 3] = origin
    ifcopenshell.api.run(
        "geometry.edit_object_placement",
        model,
        product=product,
        matrix=matrix,
        is_si=True,
    )


def _assign_container(model: ifcopenshell.file, product, storey, label: str) -> None:
    relation = ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        products=[product],
        relating_structure=storey,
    )
    relation.GlobalId = guid(f"rel-containment-{label}")


def _add_element(
    model: ifcopenshell.file,
    storey,
    *,
    label: str,
    ifc_class: str,
    name: str,
    size: tuple[float, float, float],
    origin: tuple[float, float, float],
):
    element = _root(model, ifc_class, name, label)
    _place_box(model, element, size=size, origin=origin)
    _assign_container(model, element, storey, label)
    return element


def _add_review_property(model: ifcopenshell.file, element, value: str) -> None:
    pset = ifcopenshell.api.run(
        "pset.add_pset", model, product=element, name="Pset_R4Proof"
    )
    pset.GlobalId = guid("pset-modified-column")
    relation = next(
        relation
        for relation in element.IsDefinedBy
        if relation.is_a("IfcRelDefinesByProperties")
        and relation.RelatingPropertyDefinition == pset
    )
    relation.GlobalId = guid("rel-pset-modified-column")
    ifcopenshell.api.run(
        "pset.edit_pset", model, pset=pset, properties={"ReviewMark": value}
    )


def _review_pset(element):
    return next(
        relation.RelatingPropertyDefinition
        for relation in element.IsDefinedBy
        if relation.is_a("IfcRelDefinesByProperties")
        and relation.RelatingPropertyDefinition.Name == "Pset_R4Proof"
    )


def _canonicalize_relationship_members(model: ifcopenshell.file) -> None:
    for ifc_class, attribute in (
        ("IfcRelContainedInSpatialStructure", "RelatedElements"),
        ("IfcRelAggregates", "RelatedObjects"),
        ("IfcRelDefinesByProperties", "RelatedObjects"),
    ):
        for relation in model.by_type(ifc_class):
            members = getattr(relation, attribute)
            setattr(
                relation,
                attribute,
                tuple(
                    sorted(
                        members,
                        key=lambda item: (getattr(item, "GlobalId", ""), item.id()),
                    )
                ),
            )


def build_source() -> ifcopenshell.file:
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = _root(model, "IfcProject", "R4 synthetic project", "project")
    length = ifcopenshell.api.run("unit.add_si_unit", model, unit_type="LENGTHUNIT")
    ifcopenshell.api.run("unit.assign_unit", model, units=[length])
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    ifcopenshell.api.run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )

    site = _root(model, "IfcSite", "Synthetic Site", "site")
    building = _root(model, "IfcBuilding", "Synthetic Building", "building")
    ground = _root(model, "IfcBuildingStorey", "Ground Floor", "storey-ground")
    level_01 = _root(model, "IfcBuildingStorey", "Level 01", "storey-level-01")
    ground.Elevation = 0.0
    level_01.Elevation = 4.0
    for products, parent, label in (
        ([site], project, "project-site"),
        ([building], site, "site-building"),
        ([ground, level_01], building, "building-storeys"),
    ):
        relation = ifcopenshell.api.run(
            "aggregate.assign_object", model, products=products, relating_object=parent
        )
        relation.GlobalId = guid(f"rel-{label}")

    deleted = _add_element(
        model,
        ground,
        label="deleted-wall",
        ifc_class="IfcWall",
        name="R4 deleted wall",
        size=(0.35, 3.2, 3.0),
        origin=(0.0, 0.0, 0.0),
    )
    del deleted
    modified = _add_element(
        model,
        ground,
        label="modified-column",
        ifc_class="IfcColumn",
        name="R4 modified column",
        size=(0.5, 0.5, 3.0),
        origin=(8.0, 0.0, 0.0),
    )
    _add_review_property(model, modified, "source")
    _add_element(
        model,
        ground,
        label="context-ground-near-a",
        ifc_class="IfcColumn",
        name="R4 context A",
        size=(0.5, 0.5, 3.0),
        origin=(1.5, 2.0, 0.0),
    )
    _add_element(
        model,
        ground,
        label="context-ground-near-b",
        ifc_class="IfcColumn",
        name="R4 context B",
        size=(0.5, 0.5, 3.0),
        origin=(4.0, 2.0, 0.0),
    )
    _add_element(
        model,
        ground,
        label="context-ground-far",
        ifc_class="IfcColumn",
        name="R4 context outside radius",
        size=(0.5, 0.5, 3.0),
        origin=(15.0, 0.0, 0.0),
    )
    _add_element(
        model,
        level_01,
        label="distractor-level-01",
        ifc_class="IfcColumn",
        name="R4 other-storey distractor",
        size=(0.5, 0.5, 3.0),
        origin=(0.0, 0.0, 4.0),
    )

    model.header.file_name.name = SOURCE_NAME
    model.header.file_name.time_stamp = FIXED_TIMESTAMP
    model.header.file_name.author = ("BIMChange-Agent",)
    model.header.file_name.organization = ("Synthetic R4 research",)
    _canonicalize_relationship_members(model)
    return model


def revise(source_path: Path) -> ifcopenshell.file:
    model = ifcopenshell.open(source_path)
    ifcopenshell.api.run(
        "root.remove_product", model, product=model.by_guid(guid("deleted-wall"))
    )
    ground = model.by_guid(guid("storey-ground"))
    _add_element(
        model,
        ground,
        label="added-beam",
        ifc_class="IfcBeam",
        name="R4 added beam",
        size=(3.0, 0.35, 0.35),
        origin=(4.0, 0.0, 2.5),
    )
    modified = model.by_guid(guid("modified-column"))
    ifcopenshell.api.run(
        "pset.edit_pset",
        model,
        pset=_review_pset(modified),
        properties={"ReviewMark": "revised"},
    )
    model.header.file_name.name = REVISED_NAME
    model.header.file_name.time_stamp = FIXED_TIMESTAMP
    _canonicalize_relationship_members(model)
    return model


def generate_pair(output_directory: Path) -> tuple[Path, Path]:
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    source_path = output_directory / SOURCE_NAME
    revised_path = output_directory / REVISED_NAME
    for path in (source_path, revised_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite R4 fixture: {path.name}")
    source = build_source()
    source.write(source_path)
    revised = revise(source_path)
    revised.write(revised_path)
    return source_path, revised_path

