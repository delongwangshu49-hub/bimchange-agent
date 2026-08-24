from __future__ import annotations

import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from bimchange_agent.cli import main
from bimchange_agent.desktop_app import QApplication, ReportPage
from bimchange_agent.product_core import load_json
from research.r3_complete.fixtures import write_rectangular_pair, write_relationship_pair


class R3CliReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_cli_diff_query_and_bilingual_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, revised = write_rectangular_pair(root / "pair", "all_dimensions")
            output = root / "out"
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["diff-r3", str(source), str(revised), "--output-dir", str(output)]), 0)
                self.assertEqual(main(["query-r3", str(output / "r3-change-records.json"), "--geometry-subtype", "extrusion_dimension_change"]), 0)
                for language in ("zh_CN", "en"):
                    self.assertEqual(main(["report-r3", str(output / "r3-change-records.json"), "--output", str(root / f"report-{language}.html"), "--language", language]), 0)
            self.assertIn("profile_x_m", (root / "report-en.html").read_text(encoding="utf-8"))
            self.assertIn("几何变化", (root / "report-zh_CN.html").read_text(encoding="utf-8"))

    def test_relationship_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, revised = write_relationship_pair(root / "pair", "material")
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["diff-r3", str(source), str(revised), "--output-dir", str(root / "out")]), 0)
                self.assertEqual(main(["report-r3", str(root / "out" / "r3-change-records.json"), "--output", str(root / "report.html"), "--language", "en"]), 0)
            html = (root / "report.html").read_text(encoding="utf-8")
            self.assertIn("material_assignment_change", html)
            self.assertIn("Relationship changes", html)

    def test_desktop_summary_search_and_detail_cover_dimension_and_relationship(self):
        cases = (("dimension", "all_dimensions", "extrusion_dimension_change"), ("relationship", "material", "material_assignment_change"))
        for family, variant, visible_text in cases:
            with self.subTest(family=family), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                if family == "dimension":
                    source, revised = write_rectangular_pair(root / "pair", variant)
                else:
                    source, revised = write_relationship_pair(root / "pair", variant)
                with redirect_stdout(StringIO()):
                    main(["diff-r3", str(source), str(revised), "--output-dir", str(root / "out")])
                    main(["report-r3", str(root / "out" / "r3-change-records.json"), "--output", str(root / "report.html"), "--language", "en"])
                artifact_path = root / "out" / "r3-change-records.json"
                page = ReportPage("en")
                page.load_report(load_json(artifact_path), artifact_path, root / "report.html", None)
                self.assertEqual(page.card_labels["total_supported"].text(), "1")
                page.search_filter.setText(visible_text)
                self.assertEqual(page.table.rowCount(), 1)
                page.table.selectRow(0)
                page._update_detail()
                self.assertIn(visible_text.replace("_", " ").split()[0].casefold(), page.detail_body.toPlainText().casefold())
                page.close()


if __name__ == "__main__":
    unittest.main()
