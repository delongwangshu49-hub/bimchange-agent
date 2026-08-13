"""Offline tests for the isolated R1 traceability implementation."""

from __future__ import annotations

import unittest

from .acceptance import DEFAULT_REVISED, DEFAULT_SOURCE, TAMPER_CASES, run_acceptance


class R1TraceabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_acceptance(DEFAULT_SOURCE, DEFAULT_REVISED)

    def test_clean_resolution_and_rebuild(self) -> None:
        self.assertEqual(self.result["status"], "PASS")
        self.assertEqual(self.result["clean_runs_passed"], 2)
        self.assertEqual(self.result["trace_resolution_rate"], 1.0)
        self.assertTrue(self.result["clean_rebuild_match"])
        self.assertEqual(
            self.result["supported_change_types"],
            ["added", "deleted", "property_modified"],
        )

    def test_all_controlled_tampering_is_rejected(self) -> None:
        self.assertEqual(self.result["tamper_cases"], len(TAMPER_CASES))
        self.assertEqual(self.result["tamper_rejected"], len(TAMPER_CASES))
        self.assertEqual(self.result["tamper_rejection_rate"], 1.0)
        self.assertEqual(self.result["false_acceptance_count"], 0)

    def test_privacy_and_model_boundary(self) -> None:
        self.assertEqual(self.result["privacy_violation_count"], 0)
        self.assertEqual(self.result["model_calls_made"], 0)


if __name__ == "__main__":
    unittest.main()
