#!/usr/bin/env python3
"""island: your Apple Screen Time as a farm in your terminal."""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta

import chart
import colors as c
import config
import demo
import farm as farm_rules
import pixelview
import render
import store
from screentime import biome, sources


def _pick_source(cfg: config.Config) -> tuple[sources.Source | None, list[str]]:
    """iPhone first (if fresh), then Mac. Returns (source, explanation notes)."""
    notes = []
    if cfg.source in ("auto", "iphone"):
        phone = sources.read_iphone(cfg.iphone_device_id)
        if phone.found and phone.fresh:
            return phone, notes
        notes.append(f"iPhone: {phone.reason or 'no recent data'}")
        if cfg.source == "iphone":
            return None, notes
    for mac in (sources.read_mac_knowledge(), sources.read_mac_biome()):
        if mac.found:
            notes.append(f"using {mac.name} instead")
            return mac, notes
        notes.append(f"{mac.name}: {mac.reason}")
    return None, notes + ["no Screen Time source found: use `island log <minutes>`"]


def cmd_sync(cfg, args) -> int:
    src, notes = _pick_source(cfg)
    path = store.my_path(cfg.name)
    existing, _ = store.read_days(path)
    manual, _ = store.read_days(store.MANUAL_PATH)
    apple = src.days if src else {}
    days = {**existing, **apple, **manual}
    store.write_days(path, days)
    if not args.quiet:
        label = src.name if src else "no source"
        today = days.get(date.today().isoformat())
        print(f"synced {len(apple)} day(s) from {label}; today "
              f"{chart.fmt_hm(today) if today is not None else '--'} -> {path.name}")
    for line in notes if not args.quiet or not src else []:
        print(line, file=sys.stderr)
    return 0


def _person(cfg, args) -> tuple[render.Person, list[str]]:
    if args.demo:
        name = cfg.name if cfg.name != config.Config.name else demo.NAME
        return render.Person(name, demo.sample(date.today(), args.demo), demo.LIMIT), []
    days, bad = store.read_days(store.my_path(cfg.name))
    notes = []
    if not days:
        notes.append("no data yet: run `island sync` or `island log <minutes>`")
    if bad:
        notes.append(f"skipped {bad} malformed entr{'y' if bad == 1 else 'ies'} in my data file")
    return render.Person(cfg.name, days, cfg.limit_minutes), notes


def cmd_show(cfg, args) -> int:
    person, notes = _person(cfg, args)
    on = c.color_enabled()
    animate = sys.stdout.isatty() and args.anim
    render.show(person, date.today(), on, animate, notes=notes, art_mode=args.art, size=args.size)
    return 0


def cmd_graph(cfg, args) -> int:
    person, notes = _person(cfg, args)
    lines = chart.render_chart(person.days, person.limit, date.today(), c.color_enabled())
    print("\n".join(lines + notes))
    return 0


def cmd_status(cfg, args) -> int:
    days, _ = store.read_days(store.my_path(cfg.name))
    today = date.today()
    mins = days.get(today.isoformat())
    streak = farm_rules.personal_streak(days, cfg.limit_minutes, today)
    hm = chart.fmt_hm(mins).replace(" ", "") if mins is not None else "--"
    print(f"island {hm} · streak {streak}")
    return 0


def cmd_log(cfg, args) -> int:
    if not 0 <= args.minutes <= 1440:
        print("minutes must be between 0 and 1440", file=sys.stderr)
        return 2
    try:
        day = date.fromisoformat(args.date) if args.date else date.today()
    except ValueError:
        print(f"bad date {args.date!r}: use YYYY-MM-DD", file=sys.stderr)
        return 2
    manual, _ = store.read_days(store.MANUAL_PATH)
    store.write_days(store.MANUAL_PATH, {**manual, day.isoformat(): args.minutes})
    path = store.my_path(cfg.name)
    days, _ = store.read_days(path)
    store.write_days(path, {**days, day.isoformat(): args.minutes})
    print(f"logged {chart.fmt_hm(args.minutes)} for {day} (manual entries win over Apple data)")
    return 0


def _ts(t: float | None) -> str:
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M") if t else "--"


def cmd_doctor(cfg, args) -> int:
    print(f"config: {config.CONFIG_PATH if config.CONFIG_PATH.exists() else 'defaults (no config.json)'}")
    print(f"name {cfg.name} · limit {chart.fmt_hm(cfg.limit_minutes)} · source {cfg.source}\n")
    try:
        devices = sources.remote_devices()
        names = sources.device_names()
    except PermissionError as exc:
        devices, names = [], {}
        print(f"remote devices: blocked ({exc}); give your terminal Full Disk Access")
    print("synced devices (Biome App.InFocus/remote):")
    for d, mt in devices:
        print(f"  {d}  newest file {_ts(mt)}  {names.get(d, '')}")
    if not devices:
        print(f"  none ({sources.SHARE_HINT})")
    srcs = [sources.read_iphone(cfg.iphone_device_id, args.samples),
            sources.read_mac_knowledge(), sources.read_mac_biome(args.samples)]
    print()
    for s in srcs:
        status = "found" if s.found else "MISSING"
        extra = f" device {s.device_id}" if s.device_id and s.device_id != "local" else ""
        print(f"{s.name:<17} {status}{extra} · last record {_ts(s.last_event)}"
              + (f" · {s.files} file(s)" if s.files else ""))
        if s.reason:
            print(f"{'':<17} {s.reason}")
        for bad in s.bad_files[:3]:
            print(f"{'':<17} unreadable: {bad}")
    _doctor_table(srcs, cfg)
    if args.apps:
        for s in srcs:
            if s.top_apps:
                print(f"\ntop apps, last 7 days ({s.name}; printed only, never saved):")
                for b, m in s.top_apps:
                    print(f"  {chart.fmt_hm(m):>8}  {b}")
    for s in srcs:
        for i, rec in enumerate(s.samples):
            print(f"\n{s.name} sample {i} @ offset {rec.offset} state {rec.state}")
            print("  hex: " + rec.payload[:96].hex(" "))
            print("\n".join("  " + line for line in biome.describe_fields(rec.payload)))
            ev = biome.extract_event(rec)
            print(f"  -> decoded: {ev}")
    return 0


def _doctor_table(srcs, cfg) -> None:
    stored, _ = store.read_days(store.my_path(cfg.name))
    print("\nlast 7 days (compare with Settings > Screen Time on iPhone/Mac):")
    print(f"  {'date':<12}" + "".join(f"{s.name:>18}" for s in srcs) + f"{'stored':>10}")
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        cells = "".join(f"{(chart.fmt_hm(s.days[d]) if d in s.days else '--'):>18}" for s in srcs)
        st = chart.fmt_hm(stored[d]) if d in stored else "--"
        print(f"  {d:<12}{cells}{st:>10}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="island", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync", help="read Screen Time and save each day's minutes")
    s.add_argument("--quiet", action="store_true")
    for name, helptext in (("show", "draw the farm(s) and graph"), ("graph", "just the graph")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--demo", nargs="?", const=demo.MODES[0], choices=demo.MODES,
                        help="sample data: grow (default, under today: thriving), wilt (over "
                             "today: drought), abandon (over 3 days running: overgrown)")
        sp.add_argument("--anim", action="store_true", help="play today's grow/wilt animation")
        sp.add_argument("--no-anim", action="store_true", help=argparse.SUPPRESS)  # default now
        sp.add_argument("--art", choices=("auto", "pixel", "ascii"), default="auto",
                        help="pixel = TrueColor pixel farm, ascii = classic")
        sp.add_argument("--size", choices=tuple(pixelview.SIZES), default=pixelview.DEFAULT_SIZE,
                        help="pixel farm size: full = 122 columns (default, crisp), small = 82 (downscaled)")
    lg = sub.add_parser("log", help="manually log minutes for a day")
    lg.add_argument("minutes", type=int)
    lg.add_argument("--date", help="YYYY-MM-DD (default today)")
    dr = sub.add_parser("doctor", help="show sources, device IDs and the 7-day check table")
    dr.add_argument("--samples", type=int, default=0, help="dump N raw records per Biome source")
    dr.add_argument("--apps", action="store_true", help="print top apps (terminal only)")
    sub.add_parser("status", help="one-line summary for the Claude Code status line")
    args = p.parse_args(argv)
    try:
        cfg = config.load()
    except config.ConfigError as exc:
        print(f"island: {exc}", file=sys.stderr)
        return 2
    handlers = {"sync": cmd_sync, "show": cmd_show, "graph": cmd_graph, "log": cmd_log,
                "doctor": cmd_doctor, "status": cmd_status}
    try:
        return handlers[args.cmd](cfg, args)
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        print(f"island {args.cmd}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
