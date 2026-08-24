from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ifcopenshell

from research.r3_geometry.protocol import TARGET_GLOBAL_ID, generate_revision, run_geometry_diff

from .geometry import R3ClassificationError
from .shape import classify_tessellated_shape_change


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "raw" / "Building-Structural.ifc"


class R3A3ShapeTests(unittest.TestCase):
    def test_tessellated_vertex_deformation_is_reconstructed(self):
        with tempfile.TemporaryDirectory() as directory:
            revised_path = Path(directory) / "shape.ifc"
            generate_revision(SOURCE, revised_path, variant="local_shape")
            source, revised = ifcopenshell.open(SOURCE), ifcopenshell.open(revised_path)
            record = classify_tessellated_shape_change(source, revised, run_geometry_diff(source, revised), TARGET_GLOBAL_ID)
            self.assertEqual(record["geometry_subtype"], "tessellated_vertex_geometry_change")
            self.assertEqual(record["changed_vertex_count"], 1)
            self.assertTrue(record["topology_unchanged"])

    def test_translation_and_rotation_do_not_become_shape_change(self):
        for variant in ("translation", "rotation"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                revised_path = Path(directory) / f"{variant}.ifc"
                generate_revision(SOURCE, revised_path, variant=variant)
                source, revised = ifcopenshell.open(SOURCE), ifcopenshell.open(revised_path)
                with self.assertRaises(R3ClassificationError):
                    classify_tessellated_shape_change(source, revised, run_geometry_diff(source, revised), TARGET_GLOBAL_ID)


if __name__ == "__main__":
    unittest.main()
