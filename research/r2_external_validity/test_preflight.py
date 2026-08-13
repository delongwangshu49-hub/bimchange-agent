"""Offline unit tests for the R2 sample preflight decisions."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .preflight import audit_sample_set


def _sample(role: str, schema: str, digest: str) -> tuple[dict[str, object], set[str]]:
    return (
        {
            "role": role,
            "sha256": digest,
            "file_size_bytes": 1,
            "ifc_schema": schema,
            "entity_count": 1,
            "element_count": 1,
            "root_count": 1,
            "missing_or_invalid_root_guid_count": 0,
            "duplicate_root_guid_excess_count": 0,
        },
        {"0" + "A" * 21},
    )


class ExternalValidityPreflightTests(unittest.TestCase):
    @patch("research.r2_external_validity.preflight._inspect_ledger")
    @patch("research.r2_external_validity.preflight._inspect_ifc")
    def test_report_is_path_free_and_does_not_claim_ifc2x3_support(
        self, inspect_ifc, inspect_ledger
    ) -> None:
        inspect_ifc.side_effect = (
            _sample("ifc4_baseline", "IFC4", "a" * 64),
            _sample("ifc4_repeat", "IFC4", "a" * 64),
            _sample("ifc4_revised", "IFC4", "b" * 64),
            _sample("ifc2x3_boundary", "IFC2X3", "c" * 64),
        )
        inspect_ledger.return_value = {
            "role": "change-ledger.csv",
            "sha256": "d" * 64,
            "row_count": 3,
            "operation_counts": {
                "added": 1,
                "deleted": 1,
                "property_modified": 1,
            },
            "case_id_set_sha256": "e" * 64,
            "global_id_set_sha256": "f" * 64,
        }
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private-project.ifc"
            report = audit_sample_set(private, private, private, private, private)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["privacy_violation_count"], 0)
        self.assertEqual(
            report["research_state"]["ifc2x3_cross_schema_pair"],
            "NOT_AVAILABLE_SINGLE_FILE_ONLY",
        )
        self.assertEqual(
            report["research_state"]["ifc2x3_product_support_claim"],
            "NOT_PERMITTED",
        )

    @patch("research.r2_external_validity.preflight._inspect_ledger")
    @patch("research.r2_external_validity.preflight._inspect_ifc")
    def test_non_identical_repeat_fails(self, inspect_ifc, inspect_ledger) -> None:
        inspect_ifc.side_effect = (
            _sample("ifc4_baseline", "IFC4", "a" * 64),
            _sample("ifc4_repeat", "IFC4", "x" * 64),
            _sample("ifc4_revised", "IFC4", "b" * 64),
            _sample("ifc2x3_boundary", "IFC2X3", "c" * 64),
        )
        inspect_ledger.return_value = {
            "role": "change-ledger.csv",
            "sha256": "d" * 64,
            "row_count": 3,
            "operation_counts": {
                "added": 1,
                "deleted": 1,
                "property_modified": 1,
            },
            "case_id_set_sha256": "e" * 64,
            "global_id_set_sha256": "f" * 64,
        }
        report = audit_sample_set(*(Path("unused") for _ in range(5)))
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["checks"]["baseline_repeat_byte_identical"])


if __name__ == "__main__":
    unittest.main()
