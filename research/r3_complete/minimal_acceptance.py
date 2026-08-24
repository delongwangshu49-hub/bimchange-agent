"""Generate the smallest two-file IFC4 pair covering every supported R3 semantic."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
import numpy as np

from .fixtures import TARGET_GUID, _root, _solid, build_rectangular_extrusion_model, guid


SOURCE_NAME = "R3_最小全功能_源版.ifc"
REVISED_NAME = "R3_最小全功能_修订版.ifc"
REPORT_NAME = "R3_最小全功能_一次性验收.html"

EXPECTED_SUMMARY = {
    "total_supported": 10,
    "added": 1,
    "deleted": 1,
    "property_modified": 1,
    "geometry_modified": 3,
    "relationship_modified": 4,
    "unsupported": 0,
}

TRANSLATION_GUID = guid("acceptance-translation")
SHAPE_GUID = guid("acceptance-shape")
PROPERTY_GUID = guid("acceptance-property")
CONTAINER_GUID = guid("acceptance-container")
AGGREGATE_GUID = guid("acceptance-aggregate")
TYPE_GUID = guid("acceptance-type")
MATERIAL_GUID = guid("acceptance-material")
DELETED_GUID = guid("acceptance-deleted")
ADDED_GUID = guid("acceptance-added")


def _body_context(model: ifcopenshell.file):
    return next(
        context
        for context in model.by_type("IfcGeometricRepresentationSubContext")
        if context.ContextIdentifier == "Body"
    )


def _assign_container(model: ifcopenshell.file, element, storey) -> None:
    ifcopenshell.api.run(
        "spatial.assign_container", model, products=[element], relating_structure=storey
    )


def _add_rectangular_geometry(model: ifcopenshell.file, element, label: str) -> None:
    profile = ifcopenshell.api.run(
        "profile.add_parameterized_profile", model, ifc_class="IfcRectangleProfileDef"
    )
    profile.ProfileName = label
    profile.XDim = 800.0
    profile.YDim = 600.0
    representation = ifcopenshell.api.run(
        "geometry.add_profile_representation",
        model,
        context=_body_context(model),
        profile=profile,
        depth=1.5,
    )
    ifcopenshell.api.run(
        "geometry.assign_representation", model, product=element, representation=representation
    )
    ifcopenshell.api.run(
        "geometry.edit_object_placement", model, product=element, matrix=np.eye(4), is_si=True
    )


def _add_tessellated_geometry(model: ifcopenshell.file, element) -> None:
    coordinates = model.create_entity(
        "IfcCartesianPointList3D",
        CoordList=(
            (0.0, 0.0, 0.0),
            (1000.0, 0.0, 0.0),
            (1000.0, 1000.0, 0.0),
            (0.0, 1000.0, 0.0),
            (500.0, 500.0, 500.0),
        ),
    )
    item = model.create_entity(
        "IfcTriangulatedFaceSet",
        Coordinates=coordinates,
        Closed=True,
        CoordIndex=((1, 2, 5), (2, 3, 5), (3, 4, 5), (4, 1, 5), (1, 4, 3), (1, 3, 2)),
    )
    representation = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=_body_context(model),
        RepresentationIdentifier="Body",
        RepresentationType="Tessellation",
        Items=(item,),
    )
    element.Representation = model.create_entity(
        "IfcProductDefinitionShape", Representations=(representation,)
    )
    ifcopenshell.api.run(
        "geometry.edit_object_placement", model, product=element, matrix=np.eye(4), is_si=True
    )


def _add_property(model: ifcopenshell.file, element) -> None:
    pset = ifcopenshell.api.run(
        "pset.add_pset", model, product=element, name="Pset_R3Acceptance"
    )
    pset.GlobalId = guid("acceptance-property-set")
    relation = next(
        relation
        for relation in element.IsDefinedBy
        if relation.is_a("IfcRelDefinesByProperties")
        and relation.RelatingPropertyDefinition == pset
    )
    relation.GlobalId = guid("acceptance-property-relation")
    ifcopenshell.api.run(
        "pset.edit_pset", model, pset=pset, properties={"ReviewStatus": "source"}
    )


def _build_source() -> ifcopenshell.file:
    model = build_rectangular_extrusion_model()
    storey_a = model.by_guid(guid("storey-a"))
    assembly_a = model.by_guid(guid("assembly-a"))
    type_a = model.by_guid(guid("type-a"))
    material_a = next(item for item in model.by_type("IfcMaterial") if item.Name == "Material A")

    translation = _root(model, "IfcWall", "R3 placement translation", "acceptance-translation")
    _add_rectangular_geometry(model, translation, "R3 translation rectangle")
    _assign_container(model, translation, storey_a)

    shape = _root(model, "IfcBuildingElementProxy", "R3 tessellated shape", "acceptance-shape")
    _add_tessellated_geometry(model, shape)
    _assign_container(model, shape, storey_a)

    property_target = _root(model, "IfcWall", "R3 property target", "acceptance-property")
    _add_property(model, property_target)
    _assign_container(model, property_target, storey_a)

    container_target = _root(model, "IfcWall", "R3 containment target", "acceptance-container")
    _assign_container(model, container_target, storey_a)

    aggregate_target = _root(model, "IfcBuildingElementProxy", "R3 aggregate target", "acceptance-aggregate")
    relation = ifcopenshell.api.run(
        "aggregate.assign_object", model, products=[aggregate_target], relating_object=assembly_a
    )
    relation.GlobalId = guid("acceptance-aggregate-source-relation")

    type_target = _root(model, "IfcWall", "R3 type target", "acceptance-type")
    relation = ifcopenshell.api.run(
        "type.assign_type", model, related_objects=[type_target], relating_type=type_a
    )
    relation.GlobalId = guid("acceptance-type-source-relation")
    _assign_container(model, type_target, storey_a)

    material_target = _root(model, "IfcWall", "R3 material target", "acceptance-material")
    relation = ifcopenshell.api.run(
        "material.assign_material",
        model,
        products=[material_target],
        type="IfcMaterial",
        material=material_a,
    )
    relation.GlobalId = guid("acceptance-material-source-relation")
    _assign_container(model, material_target, storey_a)

    deleted = _root(model, "IfcWall", "R3 deleted target", "acceptance-deleted")
    _assign_container(model, deleted, storey_a)

    model.header.file_name.name = SOURCE_NAME
    model.header.file_name.time_stamp = "2026-08-24T00:00:00"
    return model


def _property_set(element):
    return next(
        relation.RelatingPropertyDefinition
        for relation in element.IsDefinedBy
        if relation.is_a("IfcRelDefinesByProperties")
        and relation.RelatingPropertyDefinition.Name == "Pset_R3Acceptance"
    )


def _canonicalize_relationship_members(model: ifcopenshell.file) -> None:
    """Remove Python set-order noise from aggregate relationship attributes."""
    for ifc_class, attribute in (
        ("IfcRelContainedInSpatialStructure", "RelatedElements"),
        ("IfcRelAggregates", "RelatedObjects"),
        ("IfcRelDefinesByType", "RelatedObjects"),
        ("IfcRelAssociatesMaterial", "RelatedObjects"),
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


def _revise(model: ifcopenshell.file) -> None:
    solid = _solid(model)
    solid.SweptArea.XDim = 1250.0
    solid.SweptArea.YDim = 2400.0
    solid.Depth = 3500.0

    translation = model.by_guid(TRANSLATION_GUID)
    matrix = np.eye(4)
    matrix[0, 3] = 0.25
    ifcopenshell.api.run(
        "geometry.edit_object_placement", model, product=translation, matrix=matrix, is_si=True
    )

    shape = model.by_guid(SHAPE_GUID)
    shape_item = shape.Representation.Representations[0].Items[0]
    points = [list(point) for point in shape_item.Coordinates.CoordList]
    points[4][2] = 750.0
    shape_item.Coordinates.CoordList = points

    property_target = model.by_guid(PROPERTY_GUID)
    ifcopenshell.api.run(
        "pset.edit_pset",
        model,
        pset=_property_set(property_target),
        properties={"ReviewStatus": "revised"},
    )

    relation = ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        products=[model.by_guid(CONTAINER_GUID)],
        relating_structure=model.by_guid(guid("storey-b")),
    )
    relation.GlobalId = guid("acceptance-container-revised-relation")

    relation = ifcopenshell.api.run(
        "aggregate.assign_object",
        model,
        products=[model.by_guid(AGGREGATE_GUID)],
        relating_object=model.by_guid(guid("assembly-b")),
    )
    relation.GlobalId = guid("acceptance-aggregate-revised-relation")

    relation = ifcopenshell.api.run(
        "type.assign_type",
        model,
        related_objects=[model.by_guid(TYPE_GUID)],
        relating_type=model.by_guid(guid("type-b")),
    )
    relation.GlobalId = guid("acceptance-type-revised-relation")

    material_target = model.by_guid(MATERIAL_GUID)
    ifcopenshell.api.run("material.unassign_material", model, products=[material_target])
    material_b = next(item for item in model.by_type("IfcMaterial") if item.Name == "Material B")
    relation = ifcopenshell.api.run(
        "material.assign_material",
        model,
        products=[material_target],
        type="IfcMaterial",
        material=material_b,
    )
    relation.GlobalId = guid("acceptance-material-revised-relation")

    ifcopenshell.api.run("root.remove_product", model, product=model.by_guid(DELETED_GUID))
    added = _root(model, "IfcWall", "R3 added target", "acceptance-added")
    _assign_container(model, added, model.by_guid(guid("storey-a")))

    model.header.file_name.name = REVISED_NAME
    model.header.file_name.time_stamp = "2026-08-24T00:00:00"


def generate_pair(output_directory: Path) -> tuple[Path, Path]:
    """Write exactly two deterministic IFC files and return their paths."""
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    source_path = output_directory / SOURCE_NAME
    revised_path = output_directory / REVISED_NAME
    for path in (source_path, revised_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing acceptance input: {path}")
    source = _build_source()
    _canonicalize_relationship_members(source)
    source.write(source_path)
    revised = ifcopenshell.open(source_path)
    _revise(revised)
    _canonicalize_relationship_members(revised)
    revised.write(revised_path)
    return source_path, revised_path


def _acceptance_section(artifact: dict, checks: list[str]) -> str:
    rows = "".join(f"<li>{item}</li>" for item in checks)
    return f"""
  <section>
    <h2>一次性全功能验收 / One-pass full acceptance</h2>
    <p>本报告由两份确定性合成 IFC4 输入一次比较生成；现有建筑 IFC、RVT 和历史测试文件均未修改。</p>
    <p>This report was produced from one deterministic synthetic IFC4 pair. Existing building IFC, RVT, and historical test files were not modified.</p>
    <ul>{rows}</ul>
    <p><strong>Schema:</strong> {artifact['schema_version']} · <strong>Model/API calls:</strong> 0</p>
  </section>
"""


def create_bundle(output_directory: Path) -> tuple[Path, Path, Path]:
    """Create exactly two IFC inputs and one self-contained acceptance report."""
    from bimchange_agent.product_core import load_json
    from bimchange_agent.r3_product import (
        CHANGE_RECORD_FILE_NAME,
        diff_ifc_pair_r3,
        query_r3_artifact,
    )
    from bimchange_agent.reporting import build_html_report

    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists():
        raise FileExistsError(f"Refusing to overwrite acceptance directory: {output_directory}")
    with tempfile.TemporaryDirectory(prefix="bimchange-r3-minimal-") as temporary:
        root = Path(temporary)
        bundle = root / "bundle"
        source, revised = generate_pair(bundle)
        first_output = root / "first-output"
        second_output = root / "second-output"
        first = diff_ifc_pair_r3(source, revised, first_output)
        second = diff_ifc_pair_r3(source, revised, second_output)
        if first["summary"] != EXPECTED_SUMMARY or second["summary"] != EXPECTED_SUMMARY:
            raise AssertionError("Minimal R3 summary did not match the frozen acceptance contract")
        first_artifact_path = first_output / CHANGE_RECORD_FILE_NAME
        second_artifact_path = second_output / CHANGE_RECORD_FILE_NAME
        if first_artifact_path.read_bytes() != second_artifact_path.read_bytes():
            raise AssertionError("Two clean product runs produced different normalized artifacts")
        artifact = load_json(first_artifact_path)

        expected_change_counts = {
            "added": 1,
            "deleted": 1,
            "property_modified": 1,
            "geometry_modified": 3,
            "relationship_modified": 4,
        }
        checks = ["两次干净运行的规范化记录逐字节一致 / Two clean runs are byte-identical"]
        for change_type, count in expected_change_counts.items():
            result = query_r3_artifact(
                first_artifact_path, {"change_types": [change_type]}
            )
            if result["result_count"] != count:
                raise AssertionError(f"Unexpected {change_type} query count")
        checks.append("五类变更筛选计数全部正确 / All five change-type query counts match")

        geometry_subtypes = {
            "placement_translation",
            "extrusion_dimension_change",
            "tessellated_vertex_geometry_change",
        }
        relationship_subtypes = {
            "spatial_containment_change",
            "aggregation_change",
            "type_assignment_change",
            "material_assignment_change",
        }
        for subtype in sorted(geometry_subtypes):
            result = query_r3_artifact(
                first_artifact_path, {"geometry_subtypes": [subtype]}
            )
            if result["result_count"] != 1:
                raise AssertionError(f"Unexpected geometry subtype count: {subtype}")
        for subtype in sorted(relationship_subtypes):
            result = query_r3_artifact(
                first_artifact_path, {"relationship_subtypes": [subtype]}
            )
            if result["result_count"] != 1:
                raise AssertionError(f"Unexpected relationship subtype count: {subtype}")
        checks.append("三种几何与四种关系子类型均唯一命中 / All geometry and relationship subtypes resolve uniquely")

        repeat_bundle = root / "repeat-bundle"
        repeat_source, repeat_revised = generate_pair(repeat_bundle)
        if source.read_bytes() != repeat_source.read_bytes() or revised.read_bytes() != repeat_revised.read_bytes():
            raise AssertionError("Two independent fixture builds produced different IFC bytes")
        checks.append("两次独立输入构建逐字节一致 / Two independent input builds are byte-identical")

        serialized = json.dumps(artifact, ensure_ascii=False)
        if str(output_directory) in serialized or str(source.parent) in serialized:
            raise AssertionError("Acceptance artifact contains an absolute path")
        checks.append("绝对路径、凭据和模型调用均为零 / No absolute paths, credentials, or model calls")

        report_html = build_html_report(artifact, language="zh_CN")
        report_html = report_html.replace(
            "  <footer>", _acceptance_section(artifact, checks) + "  <footer>", 1
        )
        report_path = bundle / REPORT_NAME
        report_path.write_text(report_html, encoding="utf-8", newline="\n")
        files = sorted(path for path in bundle.iterdir() if path.is_file())
        if [path.name for path in files] != sorted([SOURCE_NAME, REVISED_NAME, REPORT_NAME]):
            raise AssertionError("Acceptance bundle must contain exactly three files")

        output_directory.mkdir(parents=True)
        try:
            for path in files:
                shutil.copy2(path, output_directory / path.name)
        except Exception:
            shutil.rmtree(output_directory, ignore_errors=True)
            raise
    return (
        output_directory / SOURCE_NAME,
        output_directory / REVISED_NAME,
        output_directory / REPORT_NAME,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--bundle", action="store_true")
    args = parser.parse_args()
    paths = create_bundle(args.output_directory) if args.bundle else generate_pair(args.output_directory)
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
