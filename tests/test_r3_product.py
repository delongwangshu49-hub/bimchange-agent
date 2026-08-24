"""Stable product tests for all bounded R3 semantics."""

from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from bimchange_agent.product_core import load_json
from bimchange_agent.r3_product import (
    CHANGE_RECORD_FILE_NAME,
    diff_ifc_pair_r3,
    query_r3_artifact,
    validate_r3_artifact,
)
from bimchange_agent.r3_semantics import relationship_change
from bimchange_agent.geometry_product_candidate import GeometryClassificationError
from research.r3_complete.fixtures import write_rectangular_pair, write_relationship_pair
from research.r3_geometry.protocol import generate_revision


ROOT = Path(__file__).resolve().parents[1]
TESSELLATED_SOURCE = ROOT / "data" / "raw" / "Building-Structural.ifc"


class R3ProductTests(unittest.TestCase):
    def test_extrusion_dimensions_and_query(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, revised = write_rectangular_pair(root / "pair", "all_dimensions")
            result = diff_ifc_pair_r3(source, revised, root / "out")
            self.assertEqual(result["summary"]["geometry_modified"], 1)
            artifact_path = root / "out" / CHANGE_RECORD_FILE_NAME
            artifact = load_json(artifact_path)
            geometry = artifact["changes"][0]["geometry_change"]
            self.assertEqual(geometry["subtype"], "extrusion_dimension_change")
            self.assertEqual([item["field"] for item in geometry["changed_dimensions"]], ["profile_x_m", "profile_y_m", "extrusion_depth_m"])
            query = query_r3_artifact(artifact_path, {"geometry_subtypes": ["extrusion_dimension_change"]})
            self.assertEqual(query["result_count"], 1)

    def test_tessellated_shape_and_placement_translation_coexist_as_subtypes(self):
        for variant, subtype in (("local_shape", "tessellated_vertex_geometry_change"), ("translation", "placement_translation")):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                revised = root / "revised.ifc"
                generate_revision(TESSELLATED_SOURCE, revised, variant=variant)
                result = diff_ifc_pair_r3(TESSELLATED_SOURCE, revised, root / "out")
                self.assertEqual(result["summary"]["geometry_modified"], 1)
                artifact = load_json(root / "out" / CHANGE_RECORD_FILE_NAME)
                record = next(item for item in artifact["changes"] if item["change_type"] == "geometry_modified")
                self.assertEqual(record["geometry_change"]["subtype"], subtype)

    def test_all_relationship_subtypes_and_query(self):
        expected = {
            "container_storey": "spatial_containment_change", "container_space": "spatial_containment_change",
            "aggregate": "aggregation_change", "type": "type_assignment_change", "material": "material_assignment_change",
        }
        for variant, subtype in expected.items():
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source, revised = write_relationship_pair(root / "pair", variant)
                result = diff_ifc_pair_r3(source, revised, root / "out")
                self.assertEqual(result["summary"]["relationship_modified"], 1)
                artifact_path = root / "out" / CHANGE_RECORD_FILE_NAME
                query = query_r3_artifact(artifact_path, {"relationship_subtypes": [subtype]})
                self.assertEqual(query["result_count"], 1)
                self.assertEqual(query["results"][0]["relationship_change"]["subtype"], subtype)

    def test_repeat_artifact_semantics_are_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, revised = write_rectangular_pair(root / "pair", "profile_x")
            diff_ifc_pair_r3(source, revised, root / "first")
            diff_ifc_pair_r3(source, revised, root / "second")
            self.assertEqual(
                (root / "first" / CHANGE_RECORD_FILE_NAME).read_bytes(),
                (root / "second" / CHANGE_RECORD_FILE_NAME).read_bytes(),
            )

    def test_semantic_tampering_and_absolute_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, revised = write_rectangular_pair(root / "pair", "all_dimensions")
            diff_ifc_pair_r3(source, revised, root / "out")
            artifact = load_json(root / "out" / CHANGE_RECORD_FILE_NAME)
            mutations = []
            changed_path = deepcopy(artifact)
            changed_path["source"]["file_name"] = "C:\\private\\source.ifc"
            mutations.append(changed_path)
            changed_evidence = deepcopy(artifact)
            changed_evidence["changes"][0]["evidence"]["result_file"] = "..\\raw.json"
            mutations.append(changed_evidence)
            changed_delta = deepcopy(artifact)
            changed_delta["changes"][0]["geometry_change"]["changed_dimensions"][0]["delta_m"] += 0.1
            mutations.append(changed_delta)
            changed_id = deepcopy(artifact)
            changed_id["changes"][0]["change_id"] = "chg-0000000000000000"
            mutations.append(changed_id)
            for mutation in mutations:
                with self.assertRaises(ValueError):
                    validate_r3_artifact(mutation)

    def test_relationship_subtype_mismatch_and_container_rename_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path, revised_path = write_relationship_pair(root / "pair", "type")
            diff_ifc_pair_r3(source_path, revised_path, root / "out")
            artifact = load_json(root / "out" / CHANGE_RECORD_FILE_NAME)
            tampered = deepcopy(artifact)
            relation = next(item for item in tampered["changes"] if item["change_type"] == "relationship_modified")
            relation["relationship_change"]["relationship"] = "container"
            with self.assertRaises(ValueError):
                validate_r3_artifact(tampered)

            import ifcopenshell
            source = ifcopenshell.open(source_path)
            revised = ifcopenshell.open(source_path)
            container = next(item for item in revised.by_type("IfcBuildingStorey") if item.Name == "Level A")
            container.Name = "Renamed Level A"
            with self.assertRaises(GeometryClassificationError) as captured:
                relationship_change(source, revised, artifact["changes"][0]["global_id"])
            self.assertEqual(captured.exception.code, "no_relationship_delta")


if __name__ == "__main__":
    unittest.main()
