"""Validation at the edges: data files, config.json, Screen Time day splitting."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import config
import store
from screentime import daily


class ValidateDays(unittest.TestCase):
    def test_keeps_good_entries_sorted_and_rounded(self):
        days, skipped = store.validate_days({"2026-11-19": 90.6, "2026-11-18": 0})
        self.assertEqual(days, {"2026-11-18": 0, "2026-11-19": 91})
        self.assertEqual(skipped, 0)

    def test_skips_bad_entries(self):
        raw = {"2026-11-19": 1441, "2026-13-01": 5, "nope": 5, "2026-11-18": True,
               "2026-11-17": "60", "2026-11-16": -1, "2026-11-15": 30}
        days, skipped = store.validate_days(raw)
        self.assertEqual(days, {"2026-11-15": 30})
        self.assertEqual(skipped, 6)

    def test_non_dict_is_one_bad_entry(self):
        self.assertEqual(store.validate_days([1, 2]), ({}, 1))

    def test_read_write_round_trip_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "me.json"
            store.write_days(path, {"2026-11-19": 10})
            self.assertEqual(store.read_days(path), ({"2026-11-19": 10}, 0))
            path.write_text("{not json")
            self.assertEqual(store.read_days(path), ({}, 1))
            self.assertEqual(store.read_days(Path(tmp) / "missing.json"), ({}, 0))


class Config(unittest.TestCase):
    def _load(self, obj):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(obj if isinstance(obj, str) else json.dumps(obj))
            return config.load(path)

    def test_missing_file_gives_defaults(self):
        self.assertEqual(config.load(Path("/nonexistent/config.json")), config.Config())

    def test_values_and_friend_limit_fallback(self):
        cfg = self._load({"name": "Alex", "friend": "Jo", "limit_minutes": 300})
        self.assertEqual((cfg.name, cfg.friend, cfg.friend_limit), ("Alex", "Jo", 300))

    def test_rejects_bad_input(self):
        for bad in ("{oops", "[]", {"limit_minutes": 0}, {"limit_minutes": True},
                    {"limit_minutes": "240"}, {"source": "android"}):
            with self.subTest(bad=bad), self.assertRaises(config.ConfigError):
                self._load(bad)

    def test_slug(self):
        self.assertEqual(config.slug("Sam O'Neil"), "sam-o-neil")
        self.assertEqual(config.slug("!!!"), "me")


class DailyMinutes(unittest.TestCase):
    def ts(self, *args):
        return datetime(*args).timestamp()

    def test_overlaps_merge_and_noise_dropped(self):
        a = self.ts(2026, 11, 19, 10)
        merged = daily.merge_intervals([(a, a + 600), (a + 300, a + 900), (a, a + 0.5),
                                        (a, a + 13 * 3600)])
        self.assertEqual(merged, [(a, a + 900)])

    def test_session_across_midnight_is_split(self):
        s, e = self.ts(2026, 11, 18, 23, 30), self.ts(2026, 11, 19, 0, 45)
        self.assertEqual(daily.daily_minutes([(s, e)]), {"2026-11-18": 30, "2026-11-19": 45})


if __name__ == "__main__":
    unittest.main()
