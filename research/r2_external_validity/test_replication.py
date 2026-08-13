"""Offline integration tests for the R2 replication evaluator."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from bimchange_agent.product_core import CHANGE_RECORD_FILE_NAME, diff_ifc_pair

from research.r1_traceability.acceptance import (
    DEFAULT_REVISED,
    DEFAULT_SOURCE,
    _build_clean_bundle,
    run_acceptance,
)
from research.r1_traceability.traceability import (
    MANIFEST_FILE_NAME,
    sha256_file,
    strict_load_json,
)

from .evaluate_replication import evaluate_replication


def _ledger_rows(artifact: dict[str, object]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, record in enumerate(artifact["changes"], start=1):
        field = record["field"]
        operation = record["change_type"]
        old_value = ""
        new_value = ""
        field_name = ""
        if operation == "property_modified":
            field_name = f"{field['property_set']}.{field['name']}"
            old_value = json.dumps(record["old_value"], ensure_ascii=False)
            new_value = json.dumps(record["new_value"], ensure_ascii=False)
        elif operation == "added":
            snapshot = record["new_value"]
            new_value = json.dumps(
                {"name": snapshot["name"], "tag": snapshot["tag"]},
                ensure_ascii=False,
            )
        else:
            old_value = "baseline element"
        rows.append(
            {
                "case_id": f"controlled-{index:03d}",
                "global_id": record["global_id"],
                "entity_type": record["entity_type"],
                "operation": operation,
                "field": field_name,
                "old_value": old_value,
                "new_value": new_value,
                "expected_product_result": operation,
            }
        )
    return rows


class ReplicationEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="bimchange-r2-evaluate-")
        root = Path(cls.temporary.name)
        ab_dir = root / "ab"
        bc_dir = root / "bc"
        ab_dir.mkdir()
        bc_dir.mkdir()
        diff_ifc_pair(DEFAULT_SOURCE, DEFAULT_SOURCE, ab_dir)
        _build_clean_bundle(DEFAULT_SOURCE, DEFAULT_REVISED, bc_dir)
        cls.ab = strict_load_json(ab_dir / CHANGE_RECORD_FILE_NAME)
        cls.bc = strict_load_json(bc_dir / CHANGE_RECORD_FILE_NAME)
        cls.manifest = strict_load_json(bc_dir / MANIFEST_FILE_NAME)
        cls.manifest_sha256 = sha256_file(bc_dir / MANIFEST_FILE_NAME)
        cls.acceptance = run_acceptance(DEFAULT_SOURCE, DEFAULT_REVISED)
        cls.ledger = _ledger_rows(cls.bc)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_controlled_replication_passes(self) -> None:
        report = evaluate_replication(
            self.ab,
            self.bc,
            self.bc,
            self.ledger,
            self.acceptance,
            self.manifest,
            self.manifest_sha256,
        )
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["checks"]["r1_acceptance_bound_to_bc_manifest"])
        self.assertEqual(report["privacy_violation_count"], 0)
        self.assertEqual(report["model_calls_made"], 0)

    def test_unrelated_acceptance_manifest_is_rejected(self) -> None:
        tampered = copy.deepcopy(self.acceptance)
        tampered["manifest_sha256"] = "0" * 64
        report = evaluate_replication(
            self.ab,
            self.bc,
            self.bc,
            self.ledger,
            tampered,
            self.manifest,
            self.manifest_sha256,
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["checks"]["r1_acceptance_bound_to_bc_manifest"])


if __name__ == "__main__":
    unittest.main()
