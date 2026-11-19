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
    def test_personal_streak_counts_back_from_today(self):
        self.assertEqual(farm.personal_streak(days(300, 100, 100, 100), 240, TODAY), 3)

    def test_personal_streak_uses_yesterday_when_today_empty(self):
        d = days(100, 100, end=TODAY - timedelta(days=1))
        self.assertEqual(farm.personal_streak(d, 240, TODAY), 2)

    def test_simulate_returns_yesterday_and_today(self):
        before, after = farm.simulate(days(100, 100, 400), 240, TODAY)
        self.assertEqual(before.streak, 2)
        self.assertEqual(after.recent[-1], True)
        self.assertEqual(after.streak, 0)

    def test_simulate_skips_days_without_data(self):
        d = {**days(100, end=TODAY - timedelta(days=5)), **days(100)}
        _, after = farm.simulate(d, 240, TODAY)
        self.assertEqual(after.streak, 2)

    def test_simulate_without_today(self):
        before, after = farm.simulate(days(100, end=TODAY - timedelta(days=1)), 240, TODAY)
        self.assertEqual(before, after)

    def test_simulate_empty(self):
        self.assertEqual(farm.simulate({}, 240, TODAY), (Farm(), Farm()))


if __name__ == "__main__":
    unittest.main()
