import unittest
from datetime import date, timedelta

import farm
from farm import Farm, Plot

TODAY = date(2026, 11, 19)


def days(*minutes, end=TODAY):
    start = end - timedelta(days=len(minutes) - 1)
    return {(start + timedelta(days=i)).isoformat(): m for i, m in enumerate(minutes)}


class Step(unittest.TestCase):
    def test_good_day_grows_first_unfinished_plot(self):
        f = farm.step(Farm(), bad=False)
        self.assertEqual(f.plots[0], Plot(1))
        self.assertEqual(f.streak, 1)

    def test_bad_day_wilts_newest_crop_and_resets_streak(self):
        f = farm.step(farm.step(farm.step(Farm(), False), False), True)
        self.assertTrue(f.plots[0].wilted)
        self.assertEqual(f.streak, 0)

    def test_good_day_after_bad_recovers_wilted_crop(self):
        f = farm.step(farm.step(farm.step(Farm(), False), True), False)
        self.assertFalse(f.plots[0].wilted)
        self.assertEqual(f.plots[0].stage, 1)

    def test_two_bad_days_kill_crop_back(self):
        f = farm.step(farm.step(farm.step(farm.step(Farm(), False), False), True), True)
        self.assertEqual(f.plots[0].stage, 1)

    def test_step_never_mutates_input(self):
        start = Farm()
        farm.step(start, False)
        self.assertEqual(start, Farm())

    def test_recent_keeps_last_seven(self):
        f = Farm()
        for i in range(10):
            f = farm.step(f, i % 2 == 0)
        self.assertEqual(len(f.recent), 7)


class Rules(unittest.TestCase):
    def test_day_bad_if_anyone_over(self):
        key = TODAY.isoformat()
        self.assertTrue(farm.day_bad(key, [({key: 100}, 240), ({key: 300}, 240)]))
        self.assertFalse(farm.day_bad(key, [({key: 100}, 240), ({key: 200}, 240)]))
        self.assertIsNone(farm.day_bad(key, [({}, 240)]))

    def test_personal_streak_counts_back_from_today(self):
        self.assertEqual(farm.personal_streak(days(300, 100, 100, 100), 240, TODAY), 3)

    def test_personal_streak_uses_yesterday_when_today_empty(self):
        d = days(100, 100, end=TODAY - timedelta(days=1))
        self.assertEqual(farm.personal_streak(d, 240, TODAY), 2)

    def test_simulate_links_both_farms(self):
        mine, theirs = days(100, 100, 100), days(100, 100, 400)
        before, after = farm.simulate([(mine, 240), (theirs, 240)], TODAY)
        self.assertEqual(after.recent[-1], True)
        self.assertEqual(before.streak, 2)

    def test_simulate_empty(self):
        self.assertEqual(farm.simulate([({}, 240)], TODAY), (Farm(), Farm()))


if __name__ == "__main__":
    unittest.main()
