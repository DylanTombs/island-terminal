"""What gets drawn: scene choice, the chart, the image escapes and the demo story."""

import base64
import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import chart
import demo
import inline_image
import pixelview
import scenes

TODAY = date(2026, 11, 19)


def days(*minutes):
    start = TODAY - timedelta(days=len(minutes) - 1)
    return {(start + timedelta(days=i)).isoformat(): m for i, m in enumerate(minutes)}


class SceneChoice(unittest.TestCase):
    def cond(self, d):
        return pixelview.person_condition(d, 240, TODAY)

    def test_each_scene(self):
        self.assertEqual(self.cond(days(300, 300, 100)), "thriving")
        self.assertEqual(self.cond(days(100, 100, 300)), "drought")
        self.assertEqual(self.cond(days(300, 300, 300)), "overgrown")
        self.assertEqual(self.cond({}), "winter")

    def test_demo_story(self):
        """Each demo mode lands on its scene; you're over today iff it isn't thriving."""
        for mode, want in (("grow", "thriving"), ("wilt", "drought"), ("abandon", "overgrown")):
            d = demo.sample(TODAY, mode)
            with self.subTest(mode=mode):
                self.assertEqual(pixelview.person_condition(d, demo.LIMIT, TODAY), want)
                self.assertEqual(d[TODAY.isoformat()] > demo.LIMIT, want != "thriving")

    def test_demo_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            demo.sample(TODAY, "nope")


class Chart(unittest.TestCase):
    def test_fmt_hm(self):
        self.assertEqual([chart.fmt_hm(m) for m in (45, 60, 214, 420)],
                         ["45m", "1h", "3h 34m", "7h"])

    def test_summary(self):
        d = days(*([360] * 7 + [180] * 7))
        self.assertEqual(chart.summary(d, TODAY, 240),
                         "this week 6h → 3h a day (−50%) · over 0/7 days")
        self.assertIn("not enough history", chart.summary({}, TODAY))

    def test_plain_render_has_no_escapes_and_fixed_width(self):
        lines = chart.render_chart(demo.sample(TODAY), 240, TODAY, False)
        self.assertFalse(any("\x1b" in line for line in lines))
        axis = next(line for line in lines if "└" in line)
        self.assertEqual(len(axis), chart.WIDTH)

    def test_bars_red_only_above_limit(self):
        red = chart.rgb(chart.OVER_RGB)
        for minutes, want_red in ((200, False), (300, True)):
            lines = chart.render_chart({TODAY.isoformat(): minutes}, 240, TODAY, True)
            with self.subTest(minutes=minutes):
                self.assertEqual(any(red in line for line in lines[1:-4]), want_red)


class Images(unittest.TestCase):
    def test_all_scene_pngs_installed(self):
        for state in ("thriving", "drought", "overgrown", "winter"):
            self.assertIsNotNone(inline_image.scene_png(state), state)
            self.assertIsNotNone(scenes.scene(state, 40), state)

    def test_escape_carries_the_file_unchanged(self):
        png = inline_image.scene_png("thriving")
        esc = inline_image.escape(png, 60, 12)
        self.assertTrue(esc.startswith("\x1b]1337;File=inline=1;"))
        self.assertIn("width=60;height=12", esc)
        payload = esc.split(":", 1)[1].rstrip("\x07")
        self.assertEqual(base64.b64decode(payload), png.read_bytes())

    def test_not_a_png_is_refused(self):
        with mock.patch.object(scenes, "SCENE_DIR", Path(__file__).parent):
            self.assertIsNone(inline_image.scene_png("__init__"))

    def test_supported_terminals(self):
        cases = ({"TERM_PROGRAM": "iTerm.app"}, {"LC_TERMINAL": "iTerm2"},
                 {"TERM_PROGRAM": "Apple_Terminal"},
                 {"TERM_PROGRAM": "iTerm.app", "ISLAND_INLINE_IMAGES": "0"})
        for env, want in zip(cases, (True, True, False, False)):
            with self.subTest(env=env), mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(inline_image.supported(), want)

    def test_bad_ppm_raises(self):
        with self.assertRaises(scenes.SceneError):
            scenes._parse_ppm(b"P3 1 1 255\n...")


if __name__ == "__main__":
    unittest.main()
