"""End to end: the CLI as a user runs it."""

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class Cli(unittest.TestCase):
    def run_island(self, *args, **env):
        full_env = {**os.environ, "NO_COLOR": "1", **env}
        full_env.pop("ISLAND_FORCE_COLOR", None)
        return subprocess.run([sys.executable, str(ROOT / "island.py"), *args],
                              capture_output=True, text=True, env=full_env, timeout=60)

    def test_show_demo(self):
        res = self.run_island("show", "--demo")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertRegex(res.stdout, r"(Your|\w+'s) island · today 3h 34m")
        self.assertIn("· under", res.stdout)
        self.assertIn("screen time · last 14 days", res.stdout)

    def test_graph_demo_modes(self):
        for mode in ("wilt", "grow", "abandon"):
            with self.subTest(mode=mode):
                self.assertEqual(self.run_island("graph", "--demo", mode).returncode, 0)

    def test_bad_args_and_log_validation(self):
        self.assertNotEqual(self.run_island("show", "--demo", "nope").returncode, 0)
        self.assertEqual(self.run_island("log", "2000").returncode, 2)
        self.assertEqual(self.run_island("log", "10", "--date", "19-11-2026").returncode, 2)


if __name__ == "__main__":
    unittest.main()
