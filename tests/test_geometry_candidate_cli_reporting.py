"""CLI and deterministic HTML tests for the explicit geometry candidate."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from bimchange_agent.cli import main
from bimchange_agent.geometry_candidate_reporting import build_geometry_candidate_html
from bimchange_agent.geometry_product_candidate import CHANGE_RECORD_FILE_NAME
from bimchange_agent.product_core import load_json
from research.r3_geometry.protocol import TARGET_GLOBAL_ID, generate_revision


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"


class GeometryCandidateCliReportingTests(unittest.TestCase):
    def test_explicit_cli_diff_query_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revised = root / "revised.ifc"
            generate_revision(SOURCE, revised, variant="translation")
            output = root / "candidate"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = main(
                    [
                        "diff-geometry-candidate",
                        str(SOURCE),
                        str(revised),
                        "--output-dir",
                        str(output),
                    ]
                )
            self.assertEqual(status, 0)
            artifact_path = output / CHANGE_RECORD_FILE_NAME
            self.assertTrue(artifact_path.is_file())

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = main(
                    [
                        "query-geometry-candidate",
                        str(artifact_path),
                        "--change-type",
                        "geometry_modified",
                        "--geometry-subtype",
                        "placement_translation",
                    ]
                )
            self.assertEqual(status, 0)
            self.assertIn('"result_count": 1', stdout.getvalue())

            html_path = root / "geometry-report.html"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                status = main(
                    [
                        "report-geometry-candidate",
                        str(artifact_path),
                        "--output",
                        str(html_path),
                        "--language",
                        "en",
                    ]
                )
            self.assertEqual(status, 0)
            report = html_path.read_text(encoding="utf-8")
            self.assertIn("placement_translation", report)
            self.assertIn(TARGET_GLOBAL_ID, report)
            self.assertIn("0.25", report)
            self.assertNotIn(str(REPOSITORY_ROOT), report)

    def test_candidate_html_is_deterministic_and_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revised = root / "revised.ifc"
            generate_revision(SOURCE, revised, variant="translation")
            output = root / "candidate"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "diff-geometry-candidate",
                            str(SOURCE),
                            str(revised),
                            "--output-dir",
                            str(output),
                        ]
                    ),
                    0,
                )
            artifact = load_json(output / CHANGE_RECORD_FILE_NAME)
            first = build_geometry_candidate_html(artifact)
            second = build_geometry_candidate_html(artifact)
            self.assertEqual(first, second)
            artifact["warnings"][0] = "<script>alert(1)</script>"
            escaped = build_geometry_candidate_html(artifact)
            self.assertNotIn("<script>alert(1)</script>", escaped)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", escaped)


if __name__ == "__main__":
    unittest.main()
