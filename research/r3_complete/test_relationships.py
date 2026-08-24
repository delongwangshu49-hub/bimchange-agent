from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ifcopenshell

from .fixtures import TARGET_GUID, write_relationship_pair
from .relationships import classify_relationship_change, run_relationship_diff


class R3BRelationshipTests(unittest.TestCase):
    def test_four_relationship_families_are_independently_reconstructed(self):
        expected = {
            "container_storey": "spatial_containment_change",
            "container_space": "spatial_containment_change",
            "aggregate": "aggregation_change",
            "type": "type_assignment_change",
            "material": "material_assignment_change",
        }
        for variant, subtype in expected.items():
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                source_path, revised_path = write_relationship_pair(Path(directory), variant)
                source, revised = ifcopenshell.open(source_path), ifcopenshell.open(revised_path)
                raw = run_relationship_diff(source, revised)
                record = classify_relationship_change(source, revised, raw, TARGET_GUID)
                self.assertEqual(record["relationship_subtype"], subtype)
                self.assertNotEqual(record["old_relation"], record["new_relation"])
                self.assertEqual(
                    record["evidence"]["ifcdiff"]["observed"],
                    variant in {"container_storey", "container_space"},
                )


if __name__ == "__main__":
    unittest.main()
