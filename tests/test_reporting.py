"""Deterministic HTML report tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bimchange_agent.product_core import CHANGE_RECORD_FILE_NAME, diff_ifc_pair, load_json
from bimchange_agent.reporting import build_html_report, write_html_report


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
                        "limitations": [],
                    },
                },
            )
            self.assertNotIn("<script>alert(1)</script>", injected)
            self.assertNotIn("<img src=x onerror=alert(1)>", injected)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", injected)


if __name__ == "__main__":
    unittest.main()
