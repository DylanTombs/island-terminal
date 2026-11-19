"""Stdlib decoder for Apple Biome SEGB files and the protobuf records inside them.

Biome streams (e.g. ~/Library/Biome/streams/restricted/App.InFocus) are stored as
SEGB containers. Two layouts exist:

  v1 (macOS <= 13): 56-byte header with b"SEGB" at offset 52. Records follow, each
     with a 32-byte header: int32 length, int32 state, double ts1, double ts2,
     uint32 crc, uint32 unknown; payload is 8-byte aligned.
  v2 (macOS >= 14): b"SEGB" at offset 0, int32 entry count, double creation time,
     32-byte header. A trailer at the end of the file holds `count` 16-byte entries
     (int32 end offset, int32 state, double creation time). Each record has an
     8-byte header (uint32 crc32, uint32 unknown) then its payload, 4-byte aligned.

All timestamps are Cocoa time (seconds since 2001-01-01 UTC).
Files are only ever read, never written.
"""

from __future__ import annotations

import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

COCOA_EPOCH = 978307200
# Plausible Cocoa timestamps: 2015-01-01 .. 2035-01-01.
_MIN_COCOA, _MAX_COCOA = 441_763_200.0, 1_072_915_200.0
_BUNDLE_RE = re.compile(r"^[A-Za-z0-9-]+(\.[A-Za-z0-9_-]+)+$")
STATE_DELETED = 3


class SegbError(ValueError):
    """Raised when a file is not a readable SEGB container."""


@dataclass(frozen=True)
class SegbRecord:
    offset: int
    state: int
    cocoa_time: float | None
    payload: bytes


@dataclass(frozen=True)
class AppEvent:
    bundle: str | None
    start: float  # unix seconds
    end: float | None  # unix seconds, when the record carries an interval
    starting: bool | None  # focus (True) / unfocus (False), when present


# ---------------------------------------------------------------- SEGB

def _align(n: int, a: int) -> int:
    return (n + a - 1) // a * a


def parse_segb(data: bytes) -> list[SegbRecord]:
    if data[:4] == b"SEGB":
        return _parse_v2(data)
    if len(data) >= 56 and data[52:56] == b"SEGB":
        return _parse_v1(data)
    raise SegbError("missing SEGB magic")


def _parse_v1(data: bytes) -> list[SegbRecord]:
    end_of_data = min(struct.unpack_from("<i", data, 0)[0], len(data))
    records, pos = [], 56
    while pos + 32 <= end_of_data:
        length, state, ts1, _ts2, _crc, _unk = struct.unpack_from("<iiddII", data, pos)
        if length <= 0 or pos + 32 + length > len(data):
            break
        payload = data[pos + 32 : pos + 32 + length]
        records.append(SegbRecord(pos, state, ts1, payload))
        pos = _align(pos + 32 + length, 8)
    return records


def _parse_v2(data: bytes) -> list[SegbRecord]:
    if len(data) < 32:
        raise SegbError("SEGB v2 header truncated")
    count = struct.unpack_from("<i", data, 4)[0]
    trailer = len(data) - count * 16
    if count < 0 or trailer < 32:
        raise SegbError(f"SEGB v2 bad entry count {count}")
    entries = sorted(
        struct.unpack_from("<iid", data, trailer + i * 16) for i in range(count)
    )
    base = _detect_v2_base(data, entries, trailer)
    records, start = [], 32
    for end_off, state, created in entries:
        end = base + end_off
        if end <= start + 8 or end > trailer:
            start = _align(max(end, start), 4)
            continue
        payload = data[start + 8 : end]
        records.append(SegbRecord(start, state, created, payload))
        start = _align(end, 4)
    return records


def _detect_v2_base(data: bytes, entries: list, trailer: int) -> int:
    """End offsets are relative to the 32-byte header on every file seen so far;
    verify with the first record's CRC and fall back to absolute offsets."""
    if not entries:
        return 32
    for base in (32, 0):
        end = base + entries[0][0]
        if 40 < end <= trailer:
            crc = struct.unpack_from("<I", data, 32)[0]
            if zlib.crc32(data[40:end]) == crc:
                return base
    return 32


# ---------------------------------------------------------------- protobuf

def read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        if pos >= len(buf) or shift > 63:
            raise SegbError("truncated varint")
        b = buf[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if not b & 0x80:
            return result, pos
        shift += 7


def parse_protobuf(buf: bytes) -> list[tuple[int, int, object]]:
    """Minimal protobuf reader: returns (field number, wire type, value)."""
    fields, pos = [], 0
    while pos < len(buf):
        key, pos = read_varint(buf, pos)
        num, wt = key >> 3, key & 7
        if num == 0:
            raise SegbError("field number 0")
        if wt == 0:
            val, pos = read_varint(buf, pos)
        elif wt == 1:
            if pos + 8 > len(buf):
                raise SegbError("truncated fixed64")
            val, pos = buf[pos : pos + 8], pos + 8
        elif wt == 2:
            n, pos = read_varint(buf, pos)
            if pos + n > len(buf):
                raise SegbError("truncated bytes")
            val, pos = buf[pos : pos + n], pos + n
        elif wt == 5:
            if pos + 4 > len(buf):
                raise SegbError("truncated fixed32")
            val, pos = buf[pos : pos + 4], pos + 4
        else:
            raise SegbError(f"unsupported wire type {wt}")
        fields.append((num, wt, val))
    return fields


def describe_fields(buf: bytes, depth: int = 0) -> list[str]:
    """Human-readable dump of a protobuf payload, for `island doctor --samples`."""
    pad = "  " * depth
    try:
        fields = parse_protobuf(buf)
    except SegbError as exc:
        return [f"{pad}<not protobuf: {exc}>"]
    out = []
    for num, wt, val in fields:
        if wt == 0:
            out.append(f"{pad}{num}: varint {val}")
        elif wt == 1:
            d = struct.unpack("<d", val)[0]
            note = f" (cocoa -> unix {d + COCOA_EPOCH:.0f})" if _MIN_COCOA < d < _MAX_COCOA else ""
            out.append(f"{pad}{num}: double {d!r}{note}")
        elif wt == 5:
            out.append(f"{pad}{num}: fixed32 {val.hex()}")
        else:
            text = _as_text(val)
            if text is not None:
                out.append(f"{pad}{num}: string {text!r}")
            else:
                out.append(f"{pad}{num}: bytes[{len(val)}]")
                if depth < 2:
                    out.extend(describe_fields(val, depth + 1))
    return out


def _as_text(val: bytes) -> str | None:
    try:
        text = val.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return text if text.isprintable() and text else None


# ---------------------------------------------------------------- events

def _walk(buf: bytes, depth: int = 0):
    try:
        fields = parse_protobuf(buf)
    except SegbError:
        return
    for num, wt, val in fields:
        yield depth, num, wt, val
        if wt == 2 and depth < 2 and _as_text(val) is None:
            yield from _walk(val, depth + 1)


# App.InFocus fields, confirmed against real records on macOS 26 / iOS 26:
#   1 transition reason (optional string), 3 starting (1 focus / 0 unfocus),
#   4 Cocoa timestamp (double), 6 bundle ID.
F_STARTING, F_TIME, F_BUNDLE = 3, 4, 6


def extract_event(rec: SegbRecord) -> AppEvent | None:
    """Pull bundle ID, time and focus flag out of an App.InFocus record, using the
    known field numbers, falling back to shape-based guessing if they're absent."""
    try:
        fields = {num: (wt, val) for num, wt, val in parse_protobuf(rec.payload)}
    except SegbError:
        fields = {}
    if fields.get(F_TIME, (None,))[0] == 1 and fields.get(F_BUNDLE, (None,))[0] == 2:
        t = struct.unpack("<d", fields[F_TIME][1])[0]
        bundle = _as_text(fields[F_BUNDLE][1])
        wt, val = fields.get(F_STARTING, (0, 1))
        if _MIN_COCOA < t < _MAX_COCOA and bundle:
            return AppEvent(bundle, t + COCOA_EPOCH, None, bool(val) if wt == 0 else None)
    return _guess_event(rec)


def _guess_event(rec: SegbRecord) -> AppEvent | None:
    """Shape-based fallback for unknown layouts (see `island doctor --samples`)."""
    bundle, times, flag = None, [], None
    for depth, _num, wt, val in _walk(rec.payload):
        if wt == 2 and bundle is None:
            text = _as_text(val)
            if text and _BUNDLE_RE.match(text):
                bundle = text
        elif wt == 1:
            d = struct.unpack("<d", val)[0]
            if _MIN_COCOA < d < _MAX_COCOA:
                times.append(d)
        elif wt == 0 and depth == 0 and flag is None and val in (0, 1):
            flag = bool(val)
    if not times and rec.cocoa_time and _MIN_COCOA < rec.cocoa_time < _MAX_COCOA:
        times.append(rec.cocoa_time)
    if not times:
        return None
    start, end = min(times), max(times)
    return AppEvent(
        bundle=bundle,
        start=start + COCOA_EPOCH,
        end=end + COCOA_EPOCH if end - start >= 1 else None,
        starting=flag,
    )


@dataclass(frozen=True)
class StreamRead:
    events: tuple[AppEvent, ...]
    files: int
    bad_files: tuple[str, ...]
    samples: tuple[SegbRecord, ...]


def read_stream_dir(path: Path, sample_count: int = 0) -> StreamRead:
    """Read every SEGB file under `path` (read-only, into memory)."""
    events, bad, samples, files = [], [], [], 0
    for f in sorted(p for p in path.rglob("*") if p.is_file()):
        if f.name.startswith(".") or "tombstone" in f.parts:
            continue
        files += 1
        try:
            records = parse_segb(f.read_bytes())
        except (SegbError, struct.error) as exc:
            bad.append(f"{f.name}: {exc}")
            continue
        for rec in records:
            if rec.state == STATE_DELETED or not rec.payload:
                continue
            if len(samples) < sample_count:
                samples.append(rec)
            ev = extract_event(rec)
            if ev:
                events.append(ev)
    return StreamRead(tuple(events), files, tuple(bad), tuple(samples))


def events_to_intervals(events, ignore=frozenset()) -> list[tuple[float, float]]:
    """Pair each focus start with its unfocus. Only one app is in front at a time,
    so a new start also closes anything still open (covers lost unfocus events).
    A session still open at the end is dropped rather than guessed."""
    ignore = {b.lower() for b in ignore}
    out, open_ = [], {}
    # Ends sort before starts at the same instant (A unfocus + B focus together).
    for e in sorted(events, key=lambda e: (e.start, e.starting is not False)):
        if e.end is not None:  # interval-style record
            if e.starting is not False:
                out.append((e.bundle, e.start, e.end))
            continue
        if e.starting is False:
            if e.bundle in open_:
                out.append((e.bundle, open_.pop(e.bundle), e.start))
            continue
        for b, s in open_.items():
            out.append((b, s, e.start))
        open_ = {e.bundle: e.start}
    return [(s, t) for b, s, t in out if (b or "").lower() not in ignore and t > s]


def events_to_app_intervals(events) -> list[tuple[str | None, float, float]]:
    """Same pairing as events_to_intervals but keeps the bundle, for doctor --apps."""
    ivs = []
    open_ = {}
    for e in sorted(events, key=lambda e: (e.start, e.starting is not False)):
        if e.starting is False:
            if e.bundle in open_:
                ivs.append((e.bundle, open_.pop(e.bundle), e.start))
        elif e.end is None:
            ivs.extend((b, s, e.start) for b, s in open_.items())
            open_ = {e.bundle: e.start}
    return ivs
