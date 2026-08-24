from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bimchange_agent.product_core import load_json
from bimchange_agent.r3_product import CHANGE_RECORD_FILE_NAME, diff_ifc_pair_r3

from .minimal_acceptance import EXPECTED_SUMMARY, REPORT_NAME, create_bundle, generate_pair


class MinimalR3AcceptanceTests(unittest.TestCase):
    def test_two_input_files_cover_every_supported_r3_family(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, revised = generate_pair(root / "inputs")
            self.assertEqual(len(list((root / "inputs").iterdir())), 2)
            result = diff_ifc_pair_r3(source, revised, root / "output")
            self.assertEqual(
                result["summary"],
                EXPECTED_SUMMARY,
            )
            artifact = load_json(root / "output" / CHANGE_RECORD_FILE_NAME)
            geometry = {
                item["geometry_change"]["subtype"]
                for item in artifact["changes"]
                if item["change_type"] == "geometry_modified"
            }
            relationships = {
                item["relationship_change"]["subtype"]
                for item in artifact["changes"]
                if item["change_type"] == "relationship_modified"
            }
            self.assertEqual(
                geometry,
                {
                    "placement_translation",
                    "extrusion_dimension_change",
                    "tessellated_vertex_geometry_change",
                },
            )
            self.assertEqual(
                relationships,
                {
                    "spatial_containment_change",
                    "aggregation_change",
                    "type_assignment_change",
                    "material_assignment_change",
                },
            )

    def test_bundle_contains_only_two_inputs_and_one_self_contained_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "minimal-bundle"
            paths = create_bundle(output)
            self.assertEqual(len(paths), 3)
            self.assertEqual(len(list(output.iterdir())), 3)
            report = (output / REPORT_NAME).read_text(encoding="utf-8")
            self.assertIn("一次性全功能验收", report)
            self.assertIn("Two clean runs are byte-identical", report)
            self.assertNotIn(str(output), report)


if __name__ == "__main__":
    unittest.main()
