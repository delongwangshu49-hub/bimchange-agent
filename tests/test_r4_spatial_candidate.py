"""Product-candidate tests for bounded report-row spatial mapping."""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from pathlib import Path

from bimchange_agent.r4_glb import read_glb_document
from bimchange_agent.r4_loopback import LocalViewerServer
from bimchange_agent.r4_spatial_candidate import (
    R4SpatialCandidateError,
    build_spatial_scene,
    SpatialSessionCache,
)
from research.r4_spatial_context.fixture import generate_pair, guid


CHANGES = [
    {
        "change_id": "r4-change-deleted-wall",
        "change_type": "deleted",
        "entity_type": "IfcWall",
        "global_id": guid("deleted-wall"),
    },
    {
        "change_id": "r4-change-added-beam",
        "change_type": "added",
        "entity_type": "IfcBeam",
        "global_id": guid("added-beam"),
    },
    {
        "change_id": "r4-change-modified-column",
        "change_type": "property_modified",
        "entity_type": "IfcColumn",
        "global_id": guid("modified-column"),
    },
]


class R4SpatialProductCandidateTests(unittest.TestCase):
    def test_session_reuses_geometry_without_changing_glb(self) -> None:
        import ifcopenshell.geom
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, revised, artifact = self._inputs(root)
            cache = SpatialSessionCache()
            results = []
            with patch("ifcopenshell.geom.create_shape", wraps=ifcopenshell.geom.create_shape) as shape:
                for name in ("first", "again"):
                    results.append(build_spatial_scene(
                        source_ifc=source, revised_ifc=revised, artifact=artifact,
                        change=CHANGES[1], output_directory=root / name, cache=cache))
                    if name == "first":
                        first_count = shape.call_count
                self.assertGreater(first_count, 0)
                self.assertEqual(first_count, shape.call_count)
            self.assertEqual(results[0].scene_sha256, results[1].scene_sha256)

    def test_changed_input_is_rejected_even_after_cache_hit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, revised, artifact = self._inputs(root)
            cache = SpatialSessionCache()
            cache.verify_inputs(source, revised, artifact)
            revised.write_bytes(revised.read_bytes() + b"\n")
            with self.assertRaisesRegex(R4SpatialCandidateError, "input_changed_since_analysis"):
                cache.verify_inputs(source, revised, artifact)

    def test_mesh_cache_budget_keeps_bounds_without_retaining_oversized_mesh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, revised, artifact = self._inputs(root)
            cache = SpatialSessionCache(maximum_mesh_bytes=1)
            cache.verify_inputs(source, revised, artifact)
            element = cache.model("revised", revised).by_guid(CHANGES[1]["global_id"])
            geometry = cache.geometry("revised", element)
            self.assertTrue(geometry[0])
            self.assertEqual(len(cache._meshes), 0)
            self.assertEqual(cache._mesh_bytes, 0)
            with patch("bimchange_agent.r4_spatial_candidate._geometry", side_effect=AssertionError):
                self.assertEqual(len(cache.bounds("revised", element)), 2)

    def test_loopback_requires_registration_for_new_scene_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with LocalViewerServer(root) as server:
                bundle = root / "records" / "owned"
                bundle.mkdir(parents=True)
                (bundle / "manifest.json").write_text("{}", encoding="utf-8")
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(server.url("records/owned/manifest.json"), timeout=5)
                with self.assertRaises(ValueError):
                    server.allow_directory(root.parent)
                server.allow_directory(bundle)
                with urllib.request.urlopen(server.url("records/owned/manifest.json"), timeout=5) as response:
                    self.assertEqual(response.read(), b"{}")

    def _inputs(self, root: Path):
        source, revised = generate_pair(root / "inputs")
        return source, revised, {"changes": CHANGES}

    def test_report_rows_select_correct_revision_and_unique_glb_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r4-product-test-") as temporary:
            root = Path(temporary)
            source, revised, artifact = self._inputs(root)
            observed = []
            for index, change in enumerate(CHANGES):
                result = build_spatial_scene(
                    source_ifc=source,
                    revised_ifc=revised,
                    artifact=artifact,
                    change=change,
                    output_directory=root / f"scene-{index}",
                )
                manifest = json.loads(result.manifest.read_text(encoding="utf-8"))
                scene = manifest["scenes"][0]
                document = read_glb_document(result.bundle / scene["file"])
                targets = [
                    node["extras"]
                    for node in document["nodes"]
                    if node.get("extras", {}).get("role") == "target"
                ]
                self.assertEqual([item["global_id"] for item in targets], [change["global_id"]])
                self.assertNotIn(str(root), result.manifest.read_text(encoding="utf-8"))
                self.assertFalse(any(result.bundle.rglob("*.ifc")))
                observed.append((result.selected_ifc_role, result.context_count))
            self.assertEqual(observed, [("source", 2), ("revised", 2), ("revised", 1)])

    def test_candidate_outputs_are_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r4-repeat-test-") as temporary:
            root = Path(temporary)
            source, revised, artifact = self._inputs(root)
            first = build_spatial_scene(
                source_ifc=source,
                revised_ifc=revised,
                artifact=artifact,
                change=CHANGES[1],
                output_directory=root / "first",
            )
            second = build_spatial_scene(
                source_ifc=source,
                revised_ifc=revised,
                artifact=artifact,
                change=CHANGES[1],
                output_directory=root / "second",
            )
            first_files = sorted(path.relative_to(first.bundle) for path in first.bundle.rglob("*") if path.is_file())
            second_files = sorted(path.relative_to(second.bundle) for path in second.bundle.rglob("*") if path.is_file())
            self.assertEqual(first_files, second_files)
            self.assertTrue(
                all((first.bundle / path).read_bytes() == (second.bundle / path).read_bytes() for path in first_files)
            )

    def test_wrong_revision_mapping_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r4-fail-test-") as temporary:
            root = Path(temporary)
            source, revised, artifact = self._inputs(root)
            forged = dict(CHANGES[0], global_id=guid("added-beam"), entity_type="IfcBeam")
            with self.assertRaisesRegex(R4SpatialCandidateError, "target_absent_from_selected_revision"):
                build_spatial_scene(
                    source_ifc=source,
                    revised_ifc=revised,
                    artifact=artifact,
                    change=forged,
                    output_directory=root / "forged",
                )

    def test_loopback_server_allows_only_tokenized_bundle_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r4-server-test-") as temporary:
            root = Path(temporary)
            source, revised, artifact = self._inputs(root)
            result = build_spatial_scene(
                source_ifc=source,
                revised_ifc=revised,
                artifact=artifact,
                change=CHANGES[2],
                output_directory=root / "bundle",
            )
            with LocalViewerServer(result.bundle) as server:
                with urllib.request.urlopen(server.url("manifest.json"), timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers["Cache-Control"], "no-store")
                with self.assertRaises(urllib.error.HTTPError) as blocked:
                    urllib.request.urlopen(f"{server.origin}/wrong/manifest.json", timeout=5)
                self.assertEqual(blocked.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
