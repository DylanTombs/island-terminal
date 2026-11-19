"""Sample data for filming: a month of history for me and a friend (Sam).

The story: I cut down from ~6h to under 4h a day this week; Sam went the other way
and blew the 4h limit 4 of the last 7 days, including today (7h), so his farm is
parched. `wilt` (default) is that; `grow` has Sam under today (both thriving);
`abandon` has Sam over 3 days running (his farm goes overgrown).
"""

from __future__ import annotations

from datetime import date, timedelta

# Oldest first, ending today.
_ME = [300, 210, 190, 230, 280, 200, 215, 225, 180, 235, 220, 250, 205, 190,
       410, 380, 340, 395, 360, 330, 375,
       235, 235, 228, 220, 215, 240, 214]
# Steady earlier weeks so the field is well grown before the bad week.
_EARLY = 16
_FRIEND = [230, 215, 200, 260, 190, 210, 225, 235, 205, 220, 215, 230, 210, 200,
           250, 290, 230, 270, 225, 300, 265,
           230, 310, 335, 225, 350, 210, 420]
_FRIEND_GOOD_TODAY = 215
_FRIEND_BAD_YESTERDAY = 390


def _dated(values: list[int], today: date) -> dict[str, int]:
    start = today - timedelta(days=len(values) - 1)
    return {(start + timedelta(days=i)).isoformat(): v for i, v in enumerate(values)}


def sample(today: date, mode: str = "wilt") -> tuple[dict, dict]:
    early = [180 + (i * 37) % 55 for i in range(_EARLY)]
    me = early + _ME
    friend = early + _FRIEND
    if mode == "grow":
        friend = friend[:-1] + [_FRIEND_GOOD_TODAY]
    elif mode == "abandon":  # third day over in a row
        friend = friend[:-2] + [_FRIEND_BAD_YESTERDAY, friend[-1]]
    return _dated(me, today), _dated(friend, today)
