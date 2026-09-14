# SPDX-License-Identifier: MIT
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run


class RunnerTests(unittest.TestCase):
    def test_exact_outcomes(self):
        self.assertTrue(run.outcome_ok(False, 0, 0, "PASS seed=1", False))
        self.assertFalse(run.outcome_ok(False, 0, 1, "PASS seed=1", False))
        self.assertTrue(run.outcome_ok(True, 0, 1, "FAIL_STABILITY_OR_ORDER", False))
        self.assertFalse(run.outcome_ok(True, 0, 1, "some arbitrary failure", False))
        self.assertFalse(run.outcome_ok(True, 0, 1, "FAIL_STABILITY_OR_ORDER FAIL_BASIC", False))
        self.assertFalse(run.outcome_ok(True, 0, 124, "FAIL_STABILITY_OR_ORDER", True))

    def test_command_timeout_is_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output, _, timed_out = run.command(
                [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(2)"],
                0.05, Path(directory) / "timeout.log")
        self.assertEqual(code, 124)
        self.assertTrue(timed_out)
        self.assertIn("started", output)
        self.assertIn("TIMEOUT", output)

    def test_missing_tools_returns_two(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(run.ROOT / "run.py"), "--evidence-dir", directory],
                env={"PATH": directory}, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing required tool", result.stdout)


if __name__ == "__main__":
    unittest.main()
