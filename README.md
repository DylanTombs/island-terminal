# island (terminal edition)

[![test](https://github.com/DylanTombs/island-terminal/actions/workflows/test.yml/badge.svg)](https://github.com/DylanTombs/island-terminal/actions/workflows/test.yml)

A weekend rebuild of [Island](https://techcrunch.com/2026/11/16/island-is-a-new-screen-time-app-that-turns-staying-off-your-phone-into-a-game/),
the YC startup that turns your screen time into a farm. This version reads your **real
Apple Screen Time** on your Mac, shows your farm in the terminal with a 14-day graph
underneath, and can greet you every time you open Claude Code.

Not affiliated with Island. macOS only (that's where Screen Time lives). Python 3.9+,
standard library only: nothing to `pip install`.

**Privacy:** nothing leaves your Mac. Screen Time is read locally and **read-only**
(SQLite in `mode=ro` on a temp copy, Biome files read into memory), and the only thing
saved is `{"YYYY-MM-DD": minutes}` in `data/`. No app names or bundle IDs are ever
written to disk.

## What you'll see

Your farm shows one of four scenes, picked from your recent days:

| scene | when |
|---|---|
| **Thriving** (peak harvest) | under your limit today |
| **Severe drought** (parched) | over your limit today |
| **Overgrown** (abandoned) | over 3 days in a row |
| **Deep winter** (frozen) | no data for 3 days |

Underneath: a 14-day bar chart (red where a bar crosses your limit) and a week-on-week
summary.

**Use [iTerm2](https://iterm2.com)** (`brew install --cask iterm2`). It can display
real images, so the farm is the actual artwork, as wide as the graph. Other terminals (Apple Terminal etc.)
get a half-block colour approximation, or ASCII if colour is off. The first time, iTerm2
asks *"Allow Terminal-Initiated Display?"*: tick *Remember my choice* and click *Yes*.

## Setup

```sh
git clone https://github.com/DylanTombs/island-terminal.git
cd island-terminal
mkdir -p ~/.local/bin && ln -s "$PWD/island" ~/.local/bin/island   # needs ~/.local/bin on PATH
island show --demo                                                 # try it with sample data
```

Then, with your own data:

1. **Turn on Screen Time sharing.** On your iPhone and Mac: Settings → Screen Time →
   *Share Across Devices*. That syncs your iPhone's app usage to your Mac.
2. **Configure:** `cp config.example.json config.json`, then set your name, limit
   (minutes, default 240).
3. **Check it against Apple:** `island doctor` prints the sources it found, the iPhone
   device ID and a 7-day table. Compare it with Settings → Screen Time. If macOS blocks
   access, give your terminal Full Disk Access (System Settings → Privacy & Security).
4. **Sync and look:** `island sync && island show`.

## Commands

| command | does |
|---|---|
| `island sync [--quiet]` | read Screen Time → `data/<you>.json` |
| `island show` | farm + graph |
| `island show --demo [grow\|wilt\|abandon]` | sample data ending under today (thriving, default), over today (drought) or over 3 days running (overgrown) |
| `island show --art pixel\|ascii` | force the pixel/image view or classic ASCII |
| `island graph` | just the 14-day graph |
| `island log <minutes> [--date YYYY-MM-DD]` | manual day (wins over Apple data) |
| `island doctor [--samples N] [--apps]` | sources, device IDs, 7-day table, raw record dump |
| `island status` | one line for the Claude Code status line |

To make the farm smaller or bigger, change your terminal's font size (Cmd − / Cmd +):
the images keep their sharpness.

## Rules

The crops underneath the scenes follow these (they drive the ASCII view and the streak):

- Under your limit: a crop grows one stage (bare `. .` → sprout → stalk → tall → in bloom).
  Over: your newest crop wilts. Back under the next day and it recovers. Two bad days in a
  row and the wilted crop dies back.
- 3+ good days in a row adds a scarecrow, birds and grass; a bad stretch greys the sky.

## Show it when Claude Code opens

- **Shell alias (always works, shows the full farm and animation):**
  `alias claude='island sync --quiet; island show; command claude'` in `~/.zshrc`.
  Remove that line to undo.
- **Status line:** in `~/.claude/settings.json`:
  `"statusLine": {"type": "command", "command": "island status"}`.
- **Keep data fresh at session start:** a `SessionStart` hook running
  `island sync --quiet` (hook output goes to Claude's context, not your screen, which is
  why the alias draws the farm).

## How the Screen Time decoding works

- **iPhone:** `~/Library/Biome/streams/restricted/App.InFocus/remote/<device-id>/`,
  SEGB files holding protobuf app-focus events (`screentime/biome.py` decodes both SEGB
  v1 and v2 and reads protobuf with a tiny varint reader).
- **Mac:** `knowledgeC.db` `/app/usage` rows, with Biome `local/` as a fallback.
- Intervals are merged (no double counting), split at local midnight, and sessions under
  1 s or over 12 h are dropped (`screentime/daily.py`).

## Development

No dependencies, so tests are plain `unittest`:

```sh
python3 -m unittest -v
```

They cover the farm rules, data/config validation, Screen Time day splitting, the chart,
scene choice, the iTerm2 image escapes and the CLI end to end. CI runs them on macOS with Python 3.9 and 3.13.

## Artwork

The four farm scenes were generated with Google Gemini and live in `assets/scenes/`
(`.png` for iTerm2, `.ppm` for the half-block fallback). To use your own art, put a 2×2
sheet (thriving, drought / overgrown, winter) at `assets/scenes.png`, adjust the panel
boxes in `tools/import_scenes.py` and run `python3 tools/import_scenes.py`.

## Licence

[MIT](LICENSE). Fork it, change it, ship your own.
