"""Find Screen Time sources on this Mac and turn each into minutes per day."""

from __future__ import annotations

import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import biome, knowledge
from .daily import daily_minutes

BIOME_ROOT = Path.home() / "Library/Biome"
INFOCUS = BIOME_ROOT / "streams/restricted/App.InFocus"
SYNC_DB = BIOME_ROOT / "sync/sync.db"
STALE_AFTER_S = 2 * 86400
SHARE_HINT = "turn on 'Share across devices' in Screen Time on both iPhone and Mac"

# Not counted by Apple's Screen Time totals.
IGNORED_BUNDLES = frozenset({
    "com.apple.springboard", "com.apple.loginwindow", "com.apple.ScreenSaver.Engine",
    "com.apple.backboardd", "com.apple.InCallService",
})


@dataclass(frozen=True)
class Source:
    name: str
    found: bool
    reason: str = ""
    days: dict = field(default_factory=dict)
    last_event: float | None = None
    device_id: str | None = None
    top_apps: tuple = ()
    samples: tuple = ()
    files: int = 0
    bad_files: tuple = ()

    @property
    def fresh(self) -> bool:
        return bool(self.last_event and time.time() - self.last_event < STALE_AFTER_S)


def _top_apps(events_or_rows, since: float) -> tuple:
    c = Counter()
    for bundle, s, e in events_or_rows:
        if s >= since and e and bundle:
            c[bundle] += (e - s) / 60
    return tuple((b, round(m)) for b, m in c.most_common(8))


def _from_biome(name: str, path: Path, device_id: str | None, samples: int) -> Source:
    try:
        read = biome.read_stream_dir(path, sample_count=samples)
    except PermissionError:
        return Source(name, False, f"macOS blocked reading {path}: give your terminal "
                      "Full Disk Access (System Settings > Privacy & Security)")
    except OSError as exc:
        return Source(name, False, f"could not read {path}: {exc}")
    if not read.events:
        why = f"no app-focus records decoded from {read.files} file(s) in {path}"
        return Source(name, False, why, device_id=device_id, files=read.files,
                      bad_files=read.bad_files, samples=read.samples)
    intervals = biome.events_to_intervals(read.events, IGNORED_BUNDLES)
    last = max(e.end or e.start for e in read.events)
    week_ago = time.time() - 7 * 86400
    top = _top_apps(_intervals_with_bundles(read.events), week_ago)
    return Source(name, True, "", daily_minutes(intervals), last, device_id, top,
                  read.samples, read.files, read.bad_files)


def _intervals_with_bundles(events):
    for b, s, e in biome.events_to_app_intervals(events):
        if e - s < 12 * 3600:
            yield b, s, e


def remote_devices() -> list[tuple[str, float]]:
    """(device id, newest file mtime) for every synced device, newest first."""
    remote = INFOCUS / "remote"
    if not remote.is_dir():
        return []
    out = []
    for d in remote.iterdir():
        if d.is_dir():
            mtimes = [f.stat().st_mtime for f in d.rglob("*") if f.is_file()]
            out.append((d.name, max(mtimes, default=0.0)))
    return sorted(out, key=lambda x: -x[1])


def device_names() -> dict[str, str]:
    """Best effort: look for device names/models in Biome's sync.db (read-only)."""
    if not SYNC_DB.exists():
        return {}
    names = {}
    try:
        with sqlite3.connect(f"file:{SYNC_DB}?mode=ro", uri=True) as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")]
            for t in tables:
                cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{t}")')]
                id_col = next((c for c in cols if "device" in c.lower() and "id" in c.lower()), None)
                label = [c for c in cols if c.lower() in ("name", "model", "device_name", "platform")]
                if not id_col or not label:
                    continue
                q = f'SELECT "{id_col}", {", ".join(f"{chr(34)}{c}{chr(34)}" for c in label)} FROM "{t}"'
                for row in conn.execute(q):
                    names[str(row[0])] = " / ".join(str(v) for v in row[1:] if v is not None)
    except sqlite3.Error:
        return names
    return names


def pick_iphone(configured: str | None) -> tuple[str | None, str]:
    devices = remote_devices()
    if configured:
        if any(d == configured for d, _ in devices):
            return configured, "from config.json"
        return None, f"configured iphone_device_id {configured} not found in {INFOCUS}/remote"
    if not devices:
        return None, f"no synced devices under {INFOCUS}/remote: {SHARE_HINT}"
    names = device_names()
    phones = [d for d, _ in devices if "iphone" in names.get(d, "").lower()]
    if phones:
        return phones[0], f"named '{names[phones[0]]}' in sync.db"
    return devices[0][0], "most recently synced remote device (set iphone_device_id to override)"


def read_iphone(configured: str | None = None, samples: int = 0) -> Source:
    try:
        device, why = pick_iphone(configured)
    except PermissionError:
        return Source("iPhone", False, f"macOS blocked reading {INFOCUS}: give your "
                      "terminal Full Disk Access")
    if not device:
        return Source("iPhone", False, why)
    src = _from_biome("iPhone", INFOCUS / "remote" / device, device, samples)
    if src.found and not src.fresh:
        return Source(**{**src.__dict__, "reason": f"last iPhone record is over 2 days old: {SHARE_HINT}"})
    return src


def read_mac_biome(samples: int = 0) -> Source:
    path = INFOCUS / "local"
    if not path.is_dir():
        return Source("Mac (Biome)", False, f"{path} not found")
    return _from_biome("Mac (Biome)", path, "local", samples)


def read_mac_knowledge() -> Source:
    try:
        rows = knowledge.read_app_usage()
    except knowledge.KnowledgeError as exc:
        return Source("Mac (knowledgeC)", False, str(exc))
    ignored = {b.lower() for b in IGNORED_BUNDLES}
    rows = [r for r in rows if (r[2] or "").lower() not in ignored]
    if not rows:
        return Source("Mac (knowledgeC)", False, "no /app/usage rows in knowledgeC.db")
    intervals = [(s, e) for s, e, _ in rows]
    top = _top_apps(((b, s, e) for s, e, b in rows), time.time() - 7 * 86400)
    return Source("Mac (knowledgeC)", True, "", daily_minutes(intervals),
                  max(e for _, e, _ in rows), "local", top)
