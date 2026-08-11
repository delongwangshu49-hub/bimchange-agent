"""Offline product-core tests; no credential or model call is permitted."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import ifcopenshell

from bimchange_agent.ai_providers import (
    DeepSeekExplanationProvider,
    ProviderConfigurationError,
    ProviderSettings,
    provider_catalog,
    require_enabled_provider,
)
from bimchange_agent.product_core import (
    CHANGE_RECORD_FILE_NAME,
    ProductBoundaryError,
    ProductLimits,
    _normalize_diff,
    diff_ifc_pair,
    inspect_ifc,
    load_json,
    validate_product_artifact,
)
from bimchange_agent.product_query import query_product_artifact


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"
REVISED = (
    REPOSITORY_ROOT
    / "data"
    / "generated"
    / "Building-Structural-gate2-v2.ifc"
)


class ProductCoreTests(unittest.TestCase):
    def test_inspect_enforces_declared_limits(self) -> None:
        report = inspect_ifc(SOURCE)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["model"]["ifc_schema"], "IFC4")
        self.assertGreater(report["model"]["element_count"], 1)
        model = ifcopenshell.open(SOURCE)
        self.assertEqual(
            report["model"]["element_count"], len(model.by_type("IfcElement"))
        )
        with self.assertRaises(ProductBoundaryError):
            inspect_ifc(SOURCE, limits=ProductLimits(max_elements=1))

    def test_diff_normalizes_gate2_fixture_and_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            result = diff_ifc_pair(SOURCE, REVISED, output_dir)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(
                result["summary"],
                {
                    "total_supported": 3,
                    "added": 1,
                    "deleted": 1,
                    "property_modified": 1,
                    "unsupported": 0,
                },
            )
            artifact_path = output_dir / CHANGE_RECORD_FILE_NAME
            artifact = load_json(artifact_path)
            self.assertEqual(artifact["model_calls_made"], 0)
            self.assertNotIn(str(REPOSITORY_ROOT), json.dumps(artifact))
            query = query_product_artifact(
                artifact_path,
                {
                    "change_types": ["property_modified"],
                    "property_set": "Pset_BeamCommon",
                    "property_name": "IsExternal",
                },
            )
            self.assertEqual(query["result_count"], 1)
            self.assertIs(query["results"][0]["old_value"], False)
            self.assertIs(query["results"][0]["new_value"], True)

    def test_identical_pair_produces_valid_empty_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            result = diff_ifc_pair(SOURCE, SOURCE, output_dir)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["summary"]["total_supported"], 0)
            artifact = load_json(output_dir / CHANGE_RECORD_FILE_NAME)
            self.assertEqual(artifact["changes"], [])
            self.assertEqual(artifact["unsupported_changes"], [])

    def test_query_rejects_unknown_change_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            diff_ifc_pair(SOURCE, SOURCE, output_dir)
            with self.assertRaises(ValueError):
                query_product_artifact(
                    output_dir / CHANGE_RECORD_FILE_NAME,
                    {"change_types": ["geometry_modified"]},
                )
            with self.assertRaises(ValueError):
                query_product_artifact(
                    output_dir / CHANGE_RECORD_FILE_NAME,
                    {"change_types": "added"},
                )

    def test_provider_catalog_enables_only_deepseek(self) -> None:
        enabled = [item.provider_id for item in provider_catalog() if item.status == "enabled"]
        self.assertEqual(enabled, ["deepseek"])
        with self.assertRaises(ProviderConfigurationError):
            require_enabled_provider("openai")

    def test_deepseek_request_is_bounded_and_has_no_key(self) -> None:
        provider = DeepSeekExplanationProvider()
        artifact = {
            "schema_version": "0.2.0-preview.1",
            "source": {"file_name": "old.ifc", "private": "omit"},
            "revised": {"file_name": "new.ifc", "private": "omit"},
            "summary": {"total_supported": 0},
            "warnings": [],
            "changes": [],
        }
        request = provider.build_request(artifact)
        serialized = json.dumps(request)
        self.assertEqual(request["model"], "deepseek-v4-flash")
        self.assertEqual(request["response_format"], {"type": "json_object"})
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("private", serialized)
        self.assertNotIn("old.ifc", serialized)
        self.assertNotIn("new.ifc", serialized)

    def test_deepseek_rejects_unsafe_base_urls(self) -> None:
        invalid_urls = (
            "http://api.deepseek.com",
            "https://user:secret@example.com",
            "https://api.deepseek.com?project=private",
            "not-a-url",
        )
        for base_url in invalid_urls:
            with self.subTest(base_url=base_url):
                with self.assertRaises(ProviderConfigurationError):
                    DeepSeekExplanationProvider(
                        ProviderSettings(base_url=base_url)
                    )

    def test_normalizer_preserves_out_of_scope_and_incomplete_changes(self) -> None:
        old_model = ifcopenshell.open(SOURCE)
        new_model = ifcopenshell.open(REVISED)
        storey_id = new_model.by_type("IfcBuildingStorey")[0].GlobalId
        records, unsupported = _normalize_diff(
            {"added": [storey_id]},
            old_model,
            new_model,
            raw_diff_name="ifcdiff.json",
        )
        self.assertEqual(records, [])
        self.assertEqual(unsupported[0]["reason"], "Added entity is not an IfcElement")

        element_id = next(iter(set(
            entity.GlobalId for entity in old_model.by_type("IfcElement")
        ) & set(
            entity.GlobalId for entity in new_model.by_type("IfcElement")
        )))
        records, unsupported = _normalize_diff(
            {
                "changed": {
                    element_id: {
                        "properties_changed": {
                            "values_changed": {
                                "root['Pset_Test']['Value']": {"old_value": 1}
                            }
                        }
                    }
                }
            },
            old_model,
            new_model,
            raw_diff_name="ifcdiff.json",
        )
        self.assertEqual(records, [])
        self.assertIn("outside the preview boundary", unsupported[0]["reason"])

    def test_semantic_artifact_validation_rejects_inconsistent_summary_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            diff_ifc_pair(SOURCE, REVISED, output_dir)
            artifact = load_json(output_dir / CHANGE_RECORD_FILE_NAME)
            artifact["summary"]["added"] += 1
            with self.assertRaises(ValueError):
                validate_product_artifact(artifact)

            artifact = load_json(output_dir / CHANGE_RECORD_FILE_NAME)
            artifact["source"]["file_name"] = str(SOURCE)
            with self.assertRaises(ValueError):
                validate_product_artifact(artifact)


if __name__ == "__main__":
    unittest.main()
