"""Offline preparation checks for the unexecuted N=1 review packets."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .prepare_n1_packets import prepare_n1_packets, verify_prepared_n1_packets


class N1PacketPreparationTests(unittest.TestCase):
    def test_packets_are_isolated_blank_and_reproducible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bimchange-r1-n1-test-") as directory:
            output = Path(directory) / "prepared-a"
            second_output = Path(directory) / "prepared-b"
            generated = prepare_n1_packets(output)
            verified = verify_prepared_n1_packets(output)
            second = prepare_n1_packets(second_output)
            self.assertEqual(generated, verified)
            self.assertEqual(generated, second)
            self.assertEqual(
                (output / "prepared-package-manifest.json").read_bytes(),
                (second_output / "prepared-package-manifest.json").read_bytes(),
            )
            self.assertEqual(verified["status"], "PASS")
            self.assertEqual(verified["packet_count"], 8)
            self.assertEqual(verified["condition_counts"], {"A": 4, "B": 4})
            self.assertEqual(verified["condition_a_trace_files"], 0)
            self.assertEqual(verified["condition_b_trace_files"], 4)
            self.assertEqual(verified["task_answer_leakage_count"], 0)
            self.assertEqual(verified["blank_trial_count"], 8)
            self.assertEqual(verified["privacy_violation_count"], 0)
            self.assertEqual(verified["execution_status"], "NOT_STARTED")
            self.assertEqual(verified["model_calls_made"], 0)


if __name__ == "__main__":
    unittest.main()
