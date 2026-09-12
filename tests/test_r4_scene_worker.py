"""Exercise the real process protocol without starting Qt or accessing APIs."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from research.r4_spatial_context.fixture import generate_pair
from tests.test_r4_spatial_candidate import CHANGES


class SceneWorkerTests(unittest.TestCase):
    def test_persistent_worker_cache_and_report_membership(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, revised = generate_pair(root / "inputs")
            inputs = {"source": str(source), "revised": str(revised),
                      "artifact": {"changes": CHANGES}, "root": str(root / "session")}
            changes = [CHANGES[1], CHANGES[1], dict(CHANGES[1], change_id="not-in-report")]
            requests = [{"id": i, "inputs": inputs, "change": c} for i, c in enumerate(changes)]
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
            result = subprocess.run([sys.executable, "-B", "-m", "bimchange_agent.r4_scene_worker"],
                                    input="".join(json.dumps(r) + "\n" for r in requests),
                                    capture_output=True, text=True, encoding="utf-8", env=env, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            replies = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual([r["id"] for r in replies], [0, 1, 2])
            self.assertFalse(replies[0]["cache_hit"])
            self.assertTrue(replies[1]["cache_hit"])
            self.assertEqual(replies[0]["manifest"], replies[1]["manifest"])
            self.assertEqual(replies[2]["error"], "change_not_in_report")


if __name__ == "__main__":
    unittest.main()
