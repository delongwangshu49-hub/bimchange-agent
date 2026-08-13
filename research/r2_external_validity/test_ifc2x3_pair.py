"""Offline tests for preregistered IFC2X3 pair preparation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ifcopenshell

from .ifc2x3_pair import build_revision, plan_pair, verify_reproducibility
from .evaluate_ifc2x3_pair import compare_evaluations, evaluate_pair


def _guid(index: int) -> str:
    return ifcopenshell.guid.compress(f"{index:032x}")


def _fixture(path: Path) -> None:
    model = ifcopenshell.file(schema="IFC2X3")
    storey = model.create_entity("IfcBuildingStorey", GlobalId=_guid(1), Name="Storey")
    elements = []
    index = 10
    for entity_type, count in (
        ("IfcBeam", 2),
        ("IfcColumn", 2),
        ("IfcWallStandardCase", 1),
        ("IfcSlab", 1),
        ("IfcDoor", 1),
    ):
        for offset in range(count):
            element = model.create_entity(
                entity_type,
                GlobalId=_guid(index),
                Name=f"{entity_type}-{offset}",
                Tag=f"T-{index}",
            )
            index += 1
            elements.append(element)
            if entity_type in {"IfcBeam", "IfcColumn"}:
                pset_name = "Pset_BeamCommon" if entity_type == "IfcBeam" else "Pset_ColumnCommon"
                prop = model.create_entity(
                    "IfcPropertySingleValue",
                    Name="IsExternal",
                    NominalValue=model.create_entity("IfcBoolean", False),
                )
                pset = model.create_entity(
                    "IfcPropertySet",
                    GlobalId=_guid(index),
                    Name=pset_name,
                    HasProperties=[prop],
                )
                index += 1
                model.create_entity(
                    "IfcRelDefinesByProperties",
                    GlobalId=_guid(index),
                    RelatedObjects=[element],
                    RelatingPropertyDefinition=pset,
                )
                index += 1
    model.create_entity(
        "IfcRelContainedInSpatialStructure",
        GlobalId=_guid(100),
        RelatedElements=elements,
        RelatingStructure=storey,
    )
    model.write(str(path))


class Ifc2x3PairTests(unittest.TestCase):
    def test_plan_build_and_reproducibility_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bimchange-ifc2x3-pair-") as directory:
            root = Path(directory)
            source = root / "source.ifc"
            _fixture(source)
            source_before = source.read_bytes()
            preregistration = root / "preregistration"
            plan = plan_pair(source, preregistration)
            self.assertEqual(plan["status"], "FROZEN_BEFORE_REVISION_AND_DIFF")
            self.assertFalse(plan["ifcdiff_executed"])
            build_a = root / "build-a"
            build_b = root / "build-b"
            report_a = build_revision(source, preregistration, build_a)
            report_b = build_revision(source, preregistration, build_b)
            self.assertEqual(report_a["status"], "READY_FOR_PREREGISTERED_DIFF")
            self.assertEqual(report_b["status"], "READY_FOR_PREREGISTERED_DIFF")
            reproducibility = verify_reproducibility(
                source,
                build_a / "revised.ifc",
                build_b / "revised.ifc",
                preregistration,
            )
            self.assertEqual(reproducibility["status"], "READY_FOR_PREREGISTERED_DIFF")
            self.assertTrue(reproducibility["clean_revisions_byte_identical"])
            self.assertEqual(reproducibility["model_calls_made"], 0)
            evaluation_a = root / "evaluation-a"
            evaluation_b = root / "evaluation-b"
            result_a = evaluate_pair(
                source, build_a / "revised.ifc", preregistration, evaluation_a
            )
            result_b = evaluate_pair(
                source, build_b / "revised.ifc", preregistration, evaluation_b
            )
            self.assertEqual(result_a["status"], "PASS_CONTROLLED_IFC2X3_DIFF_ONLY")
            self.assertEqual(result_b["status"], "PASS_CONTROLLED_IFC2X3_DIFF_ONLY")
            self.assertEqual(result_a["summary"]["total"], 6)
            comparison = compare_evaluations(evaluation_a, evaluation_b)
            self.assertEqual(comparison["status"], "PASS_CONTROLLED_IFC2X3_DIFF_ONLY")
            self.assertTrue(all(comparison["byte_identical"].values()))
            self.assertEqual(source.read_bytes(), source_before)

    def test_ledger_drift_is_rejected_before_revision_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bimchange-ifc2x3-tamper-") as directory:
            root = Path(directory)
            source = root / "source.ifc"
            _fixture(source)
            preregistration = root / "preregistration"
            plan_pair(source, preregistration)
            ledger = preregistration / "change-ledger.csv"
            ledger.write_text(ledger.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            output = root / "rejected-build"
            with self.assertRaisesRegex(ValueError, "ledger hash differs"):
                build_revision(source, preregistration, output)
            self.assertFalse((output / "revised.ifc").exists())


if __name__ == "__main__":
    unittest.main()
