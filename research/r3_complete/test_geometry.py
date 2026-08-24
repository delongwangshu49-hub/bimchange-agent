from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ifcopenshell

from .fixtures import TARGET_GUID, write_rectangular_pair
from .geometry import R3ClassificationError, classify_extrusion_dimension_change, reconstruct_extrusion, run_geometry_diff


class R3A2GeometryTests(unittest.TestCase):
    def _case(self, variant: str):
        temporary = tempfile.TemporaryDirectory()
        source_path, revised_path = write_rectangular_pair(Path(temporary.name), variant)
        source = ifcopenshell.open(source_path)
        revised = ifcopenshell.open(revised_path)
        return temporary, source, revised, run_geometry_diff(source, revised)

    def test_x_y_and_depth_are_independent_and_normalized_to_metres(self):
        expected = {
            "profile_x": [("profile_x_m", 1.0, 1.25, 0.25)],
            "profile_y": [("profile_y_m", 2.0, 2.4, 0.4)],
            "depth": [("extrusion_depth_m", 3.0, 3.5, 0.5)],
            "all_dimensions": [
                ("profile_x_m", 1.0, 1.25, 0.25),
                ("profile_y_m", 2.0, 2.4, 0.4),
                ("extrusion_depth_m", 3.0, 3.5, 0.5),
            ],
        }
        for variant, values in expected.items():
            with self.subTest(variant=variant):
                temporary, source, revised, raw = self._case(variant)
                with temporary:
                    record = classify_extrusion_dimension_change(source, revised, raw, TARGET_GUID)
                    actual = [(item["field"], item["old_m"], item["new_m"], item["delta_m"]) for item in record["changed_dimensions"]]
                    self.assertEqual(actual, values)
                    self.assertEqual(record["length_unit"], "m")
                    self.assertEqual(
                        record["evidence"]["ifcdiff"]["geometry_changed"],
                        variant != "profile_x",
                    )

    def test_noop_has_no_detector_flag(self):
        temporary, source, revised, raw = self._case("noop")
        with temporary:
            self.assertEqual(raw["changed"], {})
            with self.assertRaises(R3ClassificationError) as raised:
                classify_extrusion_dimension_change(source, revised, raw, TARGET_GUID)
            self.assertEqual(raised.exception.code, "no_parameter_delta")

    def test_mixed_placement_direction_profile_and_opening_fail_closed(self):
        codes = {
            "placement": "placement_or_rotation_changed",
            "direction": "extrusion_direction_changed",
            "profile_kind": "profile_kind_unsupported",
            "opening": "openings_changed",
        }
        for variant, code in codes.items():
            with self.subTest(variant=variant):
                temporary, source, revised, raw = self._case(variant)
                with temporary:
                    with self.assertRaises(R3ClassificationError) as raised:
                        classify_extrusion_dimension_change(source, revised, raw, TARGET_GUID)
                    self.assertEqual(raised.exception.code, code)

    def test_entity_chain_and_unit_facts_are_explicit(self):
        temporary, source, _, _ = self._case("profile_x")
        with temporary:
            facts = reconstruct_extrusion(source, TARGET_GUID)
            self.assertEqual(facts["profile_kind"], "IfcRectangleProfileDef")
            self.assertEqual(facts["unit_scale_to_m"], 0.001)
            self.assertEqual(facts["dimensions_m"], {"profile_x_m": 1.0, "profile_y_m": 2.0, "extrusion_depth_m": 3.0})


if __name__ == "__main__":
    unittest.main()
