"""Regression tests for the bounded R4 standalone research gate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .acceptance import run_acceptance, validate_bundle
from .proof import build_bundle, load_json


class R4SpatialContextTests(unittest.TestCase):
    def test_bundle_maps_each_target_once_and_stays_local(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r4-proof-test-") as temporary:
            result = build_bundle(Path(temporary) / "bundle")
            validation = validate_bundle(result.bundle)
            manifest = load_json(result.manifest)
            self.assertEqual(validation["scene_count"], 3)
            self.assertEqual(validation["unique_target_resolution_rate"], 1.0)
            self.assertEqual(
                [item["selected_ifc_role"] for item in manifest["scenes"]],
                ["source", "revised", "revised"],
            )
            self.assertTrue(all(len(item["nodes"]) <= 3 for item in manifest["scenes"]))
            self.assertFalse(manifest["viewer"]["cdn"])
            self.assertFalse(manifest["viewer"]["uploads"])

    def test_full_acceptance_rejects_fixed_tamper_matrix(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r4-acceptance-test-") as temporary:
            report = run_acceptance(Path(temporary) / "result")
            self.assertEqual(report["tamper_rejected"], report["tamper_total"])
            self.assertEqual(report["false_acceptance"], 0)
            self.assertEqual(report["clean_builds"], 2)
            self.assertEqual(report["browser_qa"], "PENDING")


if __name__ == "__main__":
    unittest.main()

