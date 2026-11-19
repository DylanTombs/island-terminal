"""End to end: friend sync through a real (local) git repo, and the CLI as a user runs it."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import config
import share

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("git"), "git not installed")
class FriendSync(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.remote = self.tmp / "shared.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def sync(self, me, friend, days):
        cfg = config.Config(name=me, friend=friend, share_repo=str(self.remote))
        with mock.patch.object(share, "SHARE_DIR", self.tmp / me):
            warning = share.sync(cfg, days)
            return warning, share.read_friend(cfg)

    def test_two_friends_swap_days_through_empty_repo(self):
        self.assertEqual(self.sync("Alex", "Sam", {"2026-11-19": 100}), (None, ({}, 0)))
        self.assertEqual(self.sync("Sam", "Alex", {"2026-11-19": 300}),
                         (None, ({"2026-11-19": 100}, 0)))
        self.assertEqual(self.sync("Alex", "Sam", {"2026-11-19": 120}),
                         (None, ({"2026-11-19": 300}, 0)))

    def test_unreachable_repo_warns_instead_of_crashing(self):
        cfg = config.Config(name="Alex", friend="Sam", share_repo=str(self.tmp / "nope.git"))
        with mock.patch.object(share, "SHARE_DIR", self.tmp / "Alex"):
            self.assertIn("offline", share.sync(cfg, {}))


class Cli(unittest.TestCase):
    def run_island(self, *args, **env):
        full_env = {**os.environ, "NO_COLOR": "1", **env}
        full_env.pop("ISLAND_FORCE_COLOR", None)
        return subprocess.run([sys.executable, str(ROOT / "island.py"), *args],
                              capture_output=True, text=True, env=full_env, timeout=60)

    def test_show_demo(self):
        res = self.run_island("show", "--demo")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("Sam's island", res.stdout)
        self.assertIn("· over", res.stdout)
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
