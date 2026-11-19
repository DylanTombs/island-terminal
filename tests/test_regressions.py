"""Bugs found in review: each test failed before its fix."""

import argparse
import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest import mock

import chart
import config
import demo
import island
import render

TODAY = date(2026, 11, 19)
ITERM = {"TERM_PROGRAM": "iTerm.app", "ISLAND_FORCE_COLOR": "1", "COLUMNS": "80"}


class ImagesInNormalSizeTerminal(unittest.TestCase):
    """An 80-column iTerm2 window used to fall back to ASCII (needed 122 columns)."""

    def test_80_column_iterm_gets_real_images(self):
        me, sam = demo.sample(TODAY)
        people = [render.Person("A", me, 240, "wheat"), render.Person("B", sam, 240, "flower")]
        out = io.StringIO()
        with mock.patch.dict(os.environ, ITERM), redirect_stdout(out):
            render.show(people, TODAY, on=True, animate=False, with_chart=False)
        self.assertEqual(out.getvalue().count("\x1b]1337;File="), 2)

    def test_ascii_mode_never_sends_images(self):
        me, _ = demo.sample(TODAY)
        out = io.StringIO()
        with mock.patch.dict(os.environ, ITERM), redirect_stdout(out):
            render.show([render.Person("A", me, 240, "wheat")], TODAY, on=True,
                        animate=False, with_chart=False, art_mode="ascii")
        self.assertNotIn("\x1b]1337", out.getvalue())


class DemoIgnoresPersonalConfig(unittest.TestCase):
    """--demo used your configured limit, which broke the story (Sam not over)."""

    def _people(self, cfg):
        args = argparse.Namespace(demo="wilt")
        people, _ = island._people(cfg, args)
        return people

    def test_demo_uses_its_own_limit(self):
        people = self._people(config.Config(name="Alex", limit_minutes=480))
        self.assertEqual([p.limit for p in people], [demo.LIMIT, demo.LIMIT])
        sam = people[1]
        self.assertGreater(sam.days[date.today().isoformat()], sam.limit)

    def test_demo_names_default_to_generic(self):
        people = self._people(config.Config())
        self.assertEqual([p.name for p in people], ["You", "Sam"])

    def test_demo_keeps_configured_names(self):
        people = self._people(config.Config(name="Alex", friend="Jo"))
        self.assertEqual([p.name for p in people], ["Alex", "Jo"])


class FriendBarsUseFriendLimit(unittest.TestCase):
    """The friend's bars turned red against *my* limit, not theirs."""

    def test_friend_under_own_limit_is_not_red(self):
        key = TODAY.isoformat()
        lines = chart.render_chart({key: 100}, 240, TODAY, True, {key: 300}, ("me", "f"),
                                   friend_limit=360)
        red = chart.rgb(chart.OVER_RGB)
        self.assertFalse(any(red in line for line in lines[1:-4]))

    def test_friend_over_own_limit_is_red(self):
        key = TODAY.isoformat()
        lines = chart.render_chart({key: 100}, 240, TODAY, True, {key: 300}, ("me", "f"),
                                   friend_limit=200)
        red = chart.rgb(chart.OVER_RGB)
        self.assertTrue(any(red in line for line in lines[1:-4]))


if __name__ == "__main__":
    unittest.main()
