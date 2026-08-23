"""Offline acceptance tests for the isolated R3-A geometry research path."""

from __future__ import annotations

import unittest

from .acceptance import TAMPER_CASES, run_acceptance


class R3GeometryAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_acceptance()

    def test_clean_rebuild_and_unique_trace(self) -> None:
        self.assertEqual(self.result["status"], "PASS")
        self.assertEqual(self.result["clean_runs_passed"], 2)
        self.assertTrue(self.result["clean_rebuild_match"])
        self.assertEqual(self.result["supported_change_records"], 1)
        self.assertEqual(self.result["trace_resolution_rate"], 1.0)

    def test_controls_fail_closed(self) -> None:
        self.assertTrue(self.result["controls_passed"])
        controls = {item["case_id"]: item for item in self.result["controls"]}
        self.assertTrue(controls["P1-translation-x"]["classified_supported"])
        self.assertTrue(controls["P2-translation-vector"]["classified_supported"])
        for case_id in (
            "C0-exact",
            "C1-noop-rewrite",
            "N1-sub-detector-noise",
            "N2-boundary-1e-5",
            "N2-boundary-2e-5",
            "N3-rotation-only",
            "N4-local-shape-change",
            "N5-missing-body",
        ):
            self.assertFalse(controls[case_id]["classified_supported"])

    def test_fixed_tamper_matrix_is_rejected(self) -> None:
        self.assertEqual(self.result["tamper_cases"], len(TAMPER_CASES))
        self.assertEqual(self.result["tamper_rejected"], len(TAMPER_CASES))
        self.assertEqual(self.result["false_acceptance_count"], 0)
        self.assertEqual(self.result["tamper_rejection_rate"], 1.0)

    def test_privacy_and_model_boundary(self) -> None:
        self.assertEqual(self.result["privacy_violation_count"], 0)
        self.assertEqual(self.result["model_calls_made"], 0)


if __name__ == "__main__":
    unittest.main()
