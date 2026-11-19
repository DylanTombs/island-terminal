# island (terminal edition)

[![test](https://github.com/DylanTombs/island-terminal/actions/workflows/test.yml/badge.svg)](https://github.com/DylanTombs/island-terminal/actions/workflows/test.yml)

Your Apple Screen Time as a farm in your terminal. Inspired by
[Island](https://techcrunch.com/2026/11/16/island-is-a-new-screen-time-app-that-turns-staying-off-your-phone-into-a-game/),
the YC startup that turns staying off your phone into a game: stay under your daily
limit and your farm thrives, go over and it dries up. island reads your **real Screen
Time** (iPhone and Mac) on your Mac and shows the farm with a 14-day graph underneath.
It can greet you every time you open a terminal or Claude Code.

Not affiliated with Island. Free and open source ([MIT](LICENSE)).

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
| **Overgrown** (abandoned) | over your limit 3 days in a row |
| **Deep winter** (frozen) | no data for 3 days |

Underneath: a 14-day bar chart (red where a bar crosses your limit) and how this week
compares with last week.

## What you need

- **A Mac.** Screen Time data only lives on macOS. For iPhone usage, the iPhone must be
  signed in to the same Apple ID.
- **Python 3.9 or newer.** macOS already has it: run `python3 --version` in a terminal.
  If macOS offers to install the Command Line Tools, accept. That's the only install,
  because island uses the standard library only (nothing to `pip install`).
- **[iTerm2](https://iterm2.com)** (recommended): `brew install --cask iterm2`, or
  download it from the website. It can display real images, so the farm is the actual
  artwork. Other terminals, including Apple's Terminal, get a coloured block
  approximation, or plain ASCII if colour is off.

## Set it up

**1. Download island**

```sh
git clone https://github.com/DylanTombs/island-terminal.git ~/island-terminal
```

**2. Make the `island` command available everywhere**

```sh
mkdir -p ~/.local/bin
ln -s ~/island-terminal/island ~/.local/bin/island
```

If `island` then says *command not found*, `~/.local/bin` isn't on your PATH yet. Add it
and reload your shell:

```sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**3. Try it with sample data**

```sh
island show --demo
```

In iTerm2, the first time, a dialog asks *"Allow Terminal-Initiated Display?"*. Tick
*Remember my choice* and click *Yes*. You can also preview the other scenes with
`island show --demo wilt` and `island show --demo abandon`.

**4. Let island read your Screen Time**

- On your **iPhone**: Settings → Screen Time → turn on **Share Across Devices**.
- On your **Mac**: System Settings → Screen Time → turn on **Share across devices**.
  Your iPhone's usage now syncs to your Mac, which can take a few hours the first time.
- macOS protects Screen Time data, so give your terminal access: System Settings →
  Privacy & Security → **Full Disk Access** → turn on **iTerm** (or Terminal). Quit and
  reopen the terminal afterwards.

**5. Set your name and daily limit**

```sh
cd ~/island-terminal
cp config.example.json config.json
open -e config.json
```

```json
{
  "name": "Alex",
  "limit_minutes": 240,
  "iphone_device_id": null,
  "source": "auto"
}
```

- `name`: shown on your farm.
- `limit_minutes`: your daily goal (240 = 4 hours, from 1 to 1440).
- `source`: `auto` (iPhone if it has recent data, otherwise this Mac), `iphone` or `mac`.
- `iphone_device_id`: leave `null` unless you have several devices and island picks the
  wrong one. `island doctor` lists the IDs.

**6. Check the numbers against Apple's**

```sh
island doctor
```

This lists the sources island found and a table of the last 7 days. Compare it with
Settings → Screen Time on your iPhone. If a source says *blocked* or *MISSING*, recheck
step 4.

**7. See your own farm**

```sh
island sync && island show
```

`sync` reads Screen Time and saves your daily totals; `show` draws the farm and graph.

## Use it every day

island only knows what you've synced, so run it whenever you open a terminal. Add this
line to `~/.zshrc`:

```sh
island sync --quiet && island show
```

Every new terminal window or tab now opens with your farm. Remove the line to stop.
To see it before Claude Code starts instead, see [below](#show-it-when-claude-code-opens).

No Screen Time data, or a day it got wrong? Log the minutes yourself (manual entries
always win over Apple's numbers):

```sh
island log 195                      # today: 3h 15m
island log 260 --date 2026-11-18    # a past day
```

## Commands

| command | does |
|---|---|
| `island sync [--quiet]` | read Screen Time and save each day's minutes to `data/<name>.json` |
| `island show` | farm + graph |
| `island show --demo [grow\|wilt\|abandon]` | sample data ending under today (thriving, default), over today (drought) or over 3 days running (overgrown) |
| `island show --art pixel\|ascii` | force the pixel/image view or classic ASCII |
| `island graph` | just the 14-day graph |
| `island log <minutes> [--date YYYY-MM-DD]` | log a day yourself (wins over Apple data) |
| `island doctor [--samples N] [--apps]` | sources, device IDs, 7-day check table, raw record dump |
| `island status` | one line, e.g. for the Claude Code status line |

To make the farm smaller or bigger, change your terminal's font size (Cmd − / Cmd +).
The image stays sharp.

## Troubleshooting

| problem | fix |
|---|---|
| `island: command not found` | step 2: add `~/.local/bin` to your PATH |
| ASCII farm instead of the picture | use iTerm2, keep colour on (don't set `NO_COLOR`) and click *Yes* on the display dialog. If you chose *No* with *Remember my choice*, undo it in iTerm2's Settings |
| `blocked` / permission errors | step 4: Full Disk Access for your terminal, then restart it |
| iPhone source *MISSING* or old | turn on Share Across Devices on both devices and wait for a sync; `source: "mac"` uses just this Mac meanwhile |
| numbers differ from Apple's | `island doctor` shows each source side by side; fix a day with `island log` |
| winter scene / "no data yet" | nothing synced in 3 days: run `island sync` |

**Uninstall:** `rm ~/.local/bin/island && rm -rf ~/island-terminal`, and remove any
line you added to `~/.zshrc`.

## Rules

The crops underneath the scenes follow these (they drive the ASCII view and the streak):

- Under your limit: a crop grows one stage (bare `. .` → sprout → stalk → tall → in bloom).
  Over: your newest crop wilts. Back under the next day and it recovers. Two bad days in a
  row and the wilted crop dies back.
- 3+ good days in a row adds a scarecrow, birds and grass; a bad stretch greys the sky.

## Show it when Claude Code opens

- **Shell alias (always works, shows the farm right before Claude starts):**
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
