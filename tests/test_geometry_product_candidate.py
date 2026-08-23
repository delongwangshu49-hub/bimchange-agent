"""Backend-only product candidate tests for placement translation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bimchange_agent.geometry_product_candidate import (
    CHANGE_RECORD_FILE_NAME,
    diff_ifc_pair_geometry_candidate,
    query_geometry_candidate_artifact,
)
from bimchange_agent.product_core import (
    CHANGE_RECORD_FILE_NAME as LEGACY_CHANGE_RECORD_FILE_NAME,
    diff_ifc_pair,
    load_json,
)
from research.r3_geometry.protocol import generate_revision


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"
GATE2_REVISED = (
    REPOSITORY_ROOT / "data" / "generated" / "Building-Structural-gate2-v2.ifc"
)


class GeometryProductCandidateTests(unittest.TestCase):
    def _revision(self, root: Path, variant: str, **kwargs: object) -> Path:
        revised = root / f"{variant}.ifc"
        generate_revision(SOURCE, revised, variant=variant, **kwargs)
        return revised

    def test_translation_artifact_and_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revised = self._revision(root, "translation")
            output = root / "candidate"
            result = diff_ifc_pair_geometry_candidate(SOURCE, revised, output)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["summary"]["geometry_modified"], 1)
            artifact_path = output / CHANGE_RECORD_FILE_NAME
            artifact = load_json(artifact_path)
            self.assertEqual(artifact["schema_version"], "0.3.0-preview.1-candidate")
            record = artifact["changes"][0]
            self.assertEqual(record["change_type"], "geometry_modified")
            self.assertEqual(record["geometry_change"]["subtype"], "placement_translation")
            self.assertEqual(record["geometry_change"]["delta"], [0.25, 0.0, 0.0])
            self.assertEqual(record["geometry_change"]["distance"], 0.25)
            self.assertNotIn(str(REPOSITORY_ROOT), json.dumps(artifact))
            query = query_geometry_candidate_artifact(
                artifact_path,
                {
                    "change_types": ["geometry_modified"],
                    "geometry_subtypes": ["placement_translation"],
                },
            )
            self.assertEqual(query["result_count"], 1)
            property_query = query_geometry_candidate_artifact(
                artifact_path, {"property_set": "Pset_BeamCommon"}
            )
            self.assertEqual(property_query["result_count"], 0)
            repeat = root / "candidate-repeat"
            diff_ifc_pair_geometry_candidate(SOURCE, revised, repeat)
            self.assertEqual(
                artifact_path.read_bytes(),
                (repeat / CHANGE_RECORD_FILE_NAME).read_bytes(),
            )

    def test_rotation_shape_and_below_threshold_fail_closed(self) -> None:
        cases = (
            ("rotation", {}, "rotation_changed"),
            ("local_shape", {}, "local_shape_changed"),
            ("translation", {"delta_m": (2e-5, 0.0, 0.0)}, "below_support_threshold"),
        )
        for index, (variant, kwargs, code) in enumerate(cases):
            with self.subTest(variant=variant, code=code), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                revised = root / f"{variant}.ifc"
                generate_revision(SOURCE, revised, variant=variant, **kwargs)
                result = diff_ifc_pair_geometry_candidate(SOURCE, revised, root / f"out-{index}")
                self.assertEqual(result["summary"]["geometry_modified"], 0)
                self.assertEqual(result["summary"]["unsupported"], 1)
                artifact = load_json(root / f"out-{index}" / CHANGE_RECORD_FILE_NAME)
                self.assertIn(code, artifact["unsupported_changes"][0]["reason"])

    def test_missing_body_is_not_claimed_and_warning_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revised = self._revision(root, "missing_body")
            output = root / "candidate"
            result = diff_ifc_pair_geometry_candidate(SOURCE, revised, output)
            self.assertEqual(result["summary"]["geometry_modified"], 0)
            artifact = load_json(output / CHANGE_RECORD_FILE_NAME)
            self.assertTrue(any("Body removal" in item for item in artifact["warnings"]))

    def test_candidate_preserves_existing_gate2_change_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate"
            result = diff_ifc_pair_geometry_candidate(SOURCE, GATE2_REVISED, output)
            self.assertEqual(
                result["summary"],
                {
                    "total_supported": 3,
                    "added": 1,
                    "deleted": 1,
                    "property_modified": 1,
                    "geometry_modified": 0,
                    "unsupported": 0,
                },
            )
            artifact = load_json(output / CHANGE_RECORD_FILE_NAME)
            self.assertEqual(
                {record["change_type"] for record in artifact["changes"]},
                {"added", "deleted", "property_modified"},
            )
            self.assertTrue(
                all(record["geometry_change"] is None for record in artifact["changes"])
            )

    def test_legacy_artifact_remains_frozen_and_candidate_filters_reject_unknowns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revised = self._revision(root, "translation")
            legacy = root / "legacy"
            diff_ifc_pair(SOURCE, revised, legacy)
            artifact = load_json(legacy / LEGACY_CHANGE_RECORD_FILE_NAME)
            self.assertEqual(artifact["schema_version"], "0.2.0-preview.1")
            self.assertNotIn("geometry_modified", artifact["summary"])

            candidate = root / "candidate"
            diff_ifc_pair_geometry_candidate(SOURCE, revised, candidate)
            path = candidate / CHANGE_RECORD_FILE_NAME
            with self.assertRaises(ValueError):
                query_geometry_candidate_artifact(
                    path, {"geometry_subtypes": ["arbitrary_shape"]}
                )
            with self.assertRaises(ValueError):
                query_geometry_candidate_artifact(
                    path, {"change_types": ["GEOMETRY_MODIFIED"]}
                )


if __name__ == "__main__":
    unittest.main()
