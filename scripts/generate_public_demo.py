"""Generate a wholly synthetic public illustration; never reads user IFC data."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

import ifcopenshell.api
from research.r4_spatial_context.fixture import build_source, revise, guid
from bimchange_agent.r3_product import diff_ifc_pair_r3
from bimchange_agent.reporting import write_html_report


def generate(output: Path) -> tuple[Path, Path, Path]:
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Choose a new directory; public demos never overwrite files")
    output.mkdir(parents=True)
    source, revised = output / "demo-source.ifc", output / "demo-revised.ifc"
    model = build_source()
    column = model.by_guid(guid("modified-column"))
    # Use a genuine I-section extrusion, not a colored rectangular marker.
    solid = column.Representation.Representations[0].Items[0]
    profile = ifcopenshell.api.run("profile.add_parameterized_profile", model,
                                  ifc_class="IfcIShapeProfileDef")
    profile.OverallWidth = 0.9
    profile.OverallDepth = 0.8
    profile.WebThickness = 0.14
    profile.FlangeThickness = 0.14
    solid.SweptArea = profile
    for item in model.by_type("IfcRoot"):
        if item.Name and not item.is_a("IfcPropertySet"):
            item.Name = item.Name.replace("R4", "Demo")
    model.header.file_name.name = source.name
    model.header.file_name.organization = ("Program-generated public illustration",)
    model.write(source)
    changed = revise(source)
    for item in changed.by_type("IfcRoot"):
        if item.Name and not item.is_a("IfcPropertySet"):
            item.Name = item.Name.replace("R4", "Demo")
    changed.header.file_name.name = revised.name
    changed.write(revised)
    diff_ifc_pair_r3(source, revised, output / "report")
    report = output / "report/r3-change-records.json"
    artifact = json.loads(report.read_text(encoding="utf-8"))
    expected = {"total_supported": 3, "added": 1, "deleted": 1,
                "property_modified": 1, "geometry_modified": 0,
                "relationship_modified": 0, "unsupported": 0}
    if artifact["summary"] != expected:
        raise AssertionError(artifact["summary"])
    write_html_report(artifact, output / "report.html", language="zh_CN")
    (output / "provenance.json").write_text(json.dumps({
        "public_synthetic_only": True, "reads_user_model": False,
        "purpose": "product illustration, not a new research benchmark",
        "summary": expected,
    }, indent=2), encoding="utf-8")
    return source, revised, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print("\n".join(map(str, generate(args.output))))
