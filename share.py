"""Friend link over a shared git repo: push my days file, pull theirs."""

from __future__ import annotations

import subprocess
from pathlib import Path

import store
from config import Config, slug

SHARE_DIR = store.STATE_DIR / "share"
GIT_TIMEOUT_S = 20


class GitError(RuntimeError):
    pass


def _git(*args: str, cwd: Path | None = None) -> str:
    try:
        res = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                             timeout=GIT_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitError(f"git {args[0]}: {exc}") from exc
    if res.returncode != 0:
        msg = (res.stderr or res.stdout).strip().splitlines()
        raise GitError(f"git {args[0]}: {msg[-1] if msg else 'failed'}")
    return res.stdout


def friend_path(cfg: Config) -> Path | None:
    return SHARE_DIR / "data" / f"{slug(cfg.friend)}.json" if cfg.friend else None


def read_friend(cfg: Config) -> tuple[dict[str, int], int]:
    path = friend_path(cfg)
    return store.read_days(path) if path else ({}, 0)


def sync(cfg: Config, my_days: dict[str, int]) -> str | None:
    """Push mine, pull theirs. Returns a one-line warning on failure, else None."""
    if not cfg.share_repo:
        return None
    try:
        if not (SHARE_DIR / ".git").exists():
            SHARE_DIR.parent.mkdir(parents=True, exist_ok=True)
            _git("clone", "-q", cfg.share_repo, str(SHARE_DIR))
        else:
            _git("pull", "-q", "--rebase", "--autostash", cwd=SHARE_DIR)
        mine = SHARE_DIR / "data" / f"{slug(cfg.name)}.json"
        store.write_days(mine, my_days)
        _git("add", str(mine.relative_to(SHARE_DIR)), cwd=SHARE_DIR)
        if _git("status", "--porcelain", cwd=SHARE_DIR).strip():
            _git("commit", "-q", "-m", f"island: {cfg.name} daily minutes", cwd=SHARE_DIR)
            _git("push", "-q", cwd=SHARE_DIR)
    except GitError as exc:
        return f"offline: friend sync failed ({exc}), showing my own data"
    return None
