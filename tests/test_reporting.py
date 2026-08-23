"""Deterministic HTML report tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bimchange_agent.geometry_product_candidate import (
    CHANGE_RECORD_FILE_NAME as GEOMETRY_CHANGE_RECORD_FILE_NAME,
    diff_ifc_pair_geometry_candidate,
)
from bimchange_agent.product_core import CHANGE_RECORD_FILE_NAME, diff_ifc_pair, load_json
from bimchange_agent.reporting import build_html_report, write_html_report
from research.r3_geometry.protocol import generate_revision


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"
REVISED = REPOSITORY_ROOT / "data" / "generated" / "Building-Structural-gate2-v2.ifc"


class ReportingTests(unittest.TestCase):
    def test_html_report_contains_supported_evidence_and_no_absolute_input_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            diff_ifc_pair(SOURCE, REVISED, output)
            artifact = load_json(output / CHANGE_RECORD_FILE_NAME)
            first = build_html_report(artifact)
            second = build_html_report(artifact)
            self.assertEqual(first, second)
            self.assertIn("Pset_BeamCommon.IsExternal", first)
            self.assertIn("2ddLgAnQf4mBfh5IpUp54U", first)
            self.assertNotIn(str(REPOSITORY_ROOT), first)
            path = write_html_report(artifact, output / "report.html")
            self.assertTrue(path.is_file())

            injected = build_html_report(
                artifact,
                explanation={
                    "provider": "deepseek",
                    "model": "<script>alert(1)</script>",
                    "explanation": {
                        "summary": "<img src=x onerror=alert(1)>",
                        "key_changes": [],
                        "rational_analysis": "Evidence-bounded priority note.",
                        "limitations": [],
                    },
                },
            )
            self.assertNotIn("<script>alert(1)</script>", injected)
            self.assertNotIn("<img src=x onerror=alert(1)>", injected)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", injected)
            self.assertIn("自然语言摘要", injected)
            self.assertNotIn('"key_changes"', injected)

            english = build_html_report(artifact, language="en")
            self.assertIn('<html lang="en">', english)
            self.assertIn("Change summary", english)
            self.assertNotIn("变更摘要", english)

    def test_unified_html_report_renders_geometry_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revised = root / "translation.ifc"
            generate_revision(SOURCE, revised, variant="translation")
            output = root / "candidate"
            diff_ifc_pair_geometry_candidate(SOURCE, revised, output)
            artifact = load_json(output / GEOMETRY_CHANGE_RECORD_FILE_NAME)

            first = build_html_report(artifact, language="en")
            second = build_html_report(artifact, language="en")
            self.assertEqual(first, second)
            self.assertIn("Geometry translations", first)
            self.assertIn("placement_translation", first)
            self.assertIn("[0.25, 0.0, 0.0] m", first)
            self.assertIn("geometry_changed", first)
            self.assertNotIn(str(REPOSITORY_ROOT), first)
            path = write_html_report(
                artifact, root / "unified-geometry-report.html", language="en"
            )
            self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
