"""Bugs found in review: each test failed before its fix."""

import argparse
import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest import mock

import config
import demo
import island
import render

TODAY = date(2026, 11, 19)
ITERM = {"TERM_PROGRAM": "iTerm.app", "ISLAND_FORCE_COLOR": "1", "COLUMNS": "80"}


def show(person, **kwargs) -> str:
    out = io.StringIO()
    with mock.patch.dict(os.environ, ITERM), redirect_stdout(out):
        render.show(person, TODAY, on=True, animate=False, with_chart=False, **kwargs)
    return out.getvalue()


class ImagesInNormalSizeTerminal(unittest.TestCase):
    """An 80-column iTerm2 window used to fall back to ASCII (needed 122 columns)."""

    def test_80_column_iterm_gets_the_real_image(self):
        out = show(render.Person("A", demo.sample(TODAY), 240))
        self.assertEqual(out.count("\x1b]1337;File="), 1)

    def test_ascii_mode_never_sends_images(self):
        out = show(render.Person("A", demo.sample(TODAY), 240), art_mode="ascii")
        self.assertNotIn("\x1b]1337", out)


class DemoIgnoresPersonalConfig(unittest.TestCase):
    """--demo used your configured limit, which broke the story."""

    def person(self, cfg, mode="wilt"):
        person, _ = island._person(cfg, argparse.Namespace(demo=mode))
        return person

    def test_demo_uses_its_own_limit(self):
        person = self.person(config.Config(name="Alex", limit_minutes=480))
        self.assertEqual(person.limit, demo.LIMIT)
        self.assertGreater(person.days[date.today().isoformat()], person.limit)

    def test_demo_name_defaults_to_you_and_keeps_configured_name(self):
        self.assertEqual(self.person(config.Config()).name, "You")
        self.assertEqual(self.person(config.Config(name="Alex")).name, "Alex")


class HeaderNames(unittest.TestCase):
    """Default names read "Me's island" / "You's island"."""

    def test_possessive(self):
        self.assertEqual([render.possessive(n) for n in ("Me", "you", "Dylan", "James")],
                         ["My", "Your", "Dylan's", "James's"])

    def test_header_uses_it(self):
        header = render.header(render.Person("You", {}, 240), TODAY, on=False)
        self.assertTrue(header[0].startswith("Your island"))


if __name__ == "__main__":
    unittest.main()
