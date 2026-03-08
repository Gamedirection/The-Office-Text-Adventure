# Office Text Adventure Template

A collaboration-first template for building office-themed text adventures.

## Goals

- Share one world (locations, items, NPCs, objects) across many adventures.
- Keep each designer/employee's stories separate in `adventures/<creator>/<adventure_name>/`.
- Run the same game engine in both a terminal UI and a Python PySide6 GUI.
- Keep save state local in `.player/` so players can resume immediately.
- Provide an AI NPC plugin interface with a built-in mock fallback.
- Keep gameplay non-combat and centered on discovery, storytelling, and learning.

## Project Layout

- `engine/`: scanner, loader/validation, command execution, save manager, AI adapter interfaces.
- `world/`: shared office content YAML (`locations`, `items`, `npcs`, `objects`, `events`, `calendar`).
- `adventures/`: per-creator adventures scanned automatically.
- `ui/tui/`: plain stdin/stdout interface for Linux terminal + Windows cmd compatibility.
- `ui/gui/`: PySide6 desktop interface (PyCharm-friendly).
- `scripts/`: launch scripts (`play.sh`, `play.cmd`).
- `.player/`: local player config + save slots.
- `docs/`: architecture, content authoring, AI plugin docs.
- `tests/`: discovery, validation, runtime, NPC, and UI smoke tests.

## Requirements

1. Python 3.11+ recommended.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## How To Play

### Terminal UI (recommended starter)

Linux/macOS:

```bash
bash scripts/play.sh
```

Windows cmd/PowerShell:

```powershell
scripts\play.cmd
```

Or directly:

```bash
python launcher.py --mode tui
```

TUI Tab completion:

- If `prompt_toolkit` is installed, `Tab` autocompletes and cycles available commands.
- Works across common terminals/shells (PowerShell, cmd, bash, zsh, fish) because completion is handled by the app, not shell-specific scripts.
- If unavailable, TUI falls back to standard input without Tab completion.

### PySide6 GUI

```bash
python launcher.py --mode gui
```

At boot, choose an adventure. You can also resume your last saved session.
In the GUI command box, press `Tab` to cycle through currently available command options.
Use `Shift+Tab` to cycle backward.
GUI preferences are saved in player config for theme (`Light`/`Dark`).

## Commands During Play

### Interact

- `look`
- `choose <choice_id>`
- `talk <npc_id> [interaction]`
- `inspect <item_or_object_id | npc_id stats>`
- `goto <location_id>`
- `check vibes <npc_id> [description]` (shows favorability before/after)

### Player

- `inventory`
- `journal [list|read <page>|remove <page>|add <note text>]` (alias: `notes`)
- `calendar [month|week|day|changes] [weather|journal]`
- `stats [npc <npc_id>]`
- `check <intelligence|vibes|physique|luck> [description]`
- `name [new player name]`

### Game

- `save <slot>`
- `load <slot>`
- `saves` (or `list-saves`)
- `settings [autosave on|off]`
- `settings autosave-notify on|off`
- `settings calendar`
- `settings calendar timezone <iana_tz>`
- `settings calendar seed <int|randomize>`
- `settings calendar timetravel <YYYY-MM-DD|clear>`
- `help`

Tip: if you type `choose` with no arguments, the game previews currently available `choose <choice_id>` options.
Tip: typing `talk`, `choose`, `inspect`, or `goto` with no arguments shows an `Available now:` preview when options exist.
If no options exist, the engine returns a default message like `No one to talk to right now`.

## Save Files

- Player config: `.player/config/player.yaml`
- Save slots: `.player/saves/<creator>/<adventure>/<slot>.yaml`
- Journal pages: `.player/journal/<creator>/<adventure>.yaml`
- Shared save exchange folder: `.player/shared-saves/`

## Autosave Setting

In `.player/config/player.yaml`:

- `autosave_enabled: true|false`
- `autosave_notify_enabled: true|false`
- `autosave_slot: <slot_name>`
- `tui_color_enabled: true|false`
- `calendar_timezone: UTC|<IANA timezone>`
- `calendar_seed: <int>`
- `new_game_start_date: YYYY-MM-DD` (optional one-shot new game override)

Use in-game command `settings autosave on|off` to toggle autosave.
Use `settings autosave-notify on|off` to show/hide autosave messages.
Use `settings calendar ...` for timezone/seed/time-travel defaults.
When enabled, adventure-changing actions (like moving/choosing) update the autosave slot automatically.
When `tui_color_enabled` is `true`, TUI output uses color coding (People gold, Items blue, Location green, etc.).

TUI color coding default map:

- People/NPC lines: Gold
- Items lines: Blue
- Location/header lines: Green
- Objects lines: Magenta
- Choices and "Available now" lines: Cyan

## Calendar, Global Events, And Weather

- Calendar date defaults to the real date at adventure start using configured timezone (`UTC` default).
- Weather is deterministic from `(calendar_seed + date)`, so the same seed/date always gives the same forecast.
- Moon phase is shown in calendar day/week weather views.
- Time travel is new-game-only:
  - `settings calendar timetravel YYYY-MM-DD` sets the date for your next new session.
  - It does not modify your current character timeline.
- Global events come from `world/events/*.yaml`.
- Holidays come from `world/calendar/*.yaml`.
- Adventure timeline events can be authored in `story.yaml` under `events:`.
  - Preferred: `day_offset` (days from adventure start date).
  - Optional absolute override: `date: YYYY-MM-DD`.
- Month calendar day color priority:
  - `yellow`: adventure event on that day (highest priority)
  - `blue`: global event/holiday on that day
  - `green`: journal entry exists on that day

Calendar command examples:

```text
calendar month
calendar month weather
calendar week
calendar week weather
calendar day
calendar day weather
calendar day journal
calendar changes
```

## Adventure Text Styling (TUI)

When `tui_color_enabled: true`, story text supports inline style tags:

- Colors: `[green]...[/green]`, `[blue]...[/blue]`, `[gold]...[/gold]`, `[magenta]...[/magenta]`, `[cyan]...[/cyan]`
- Text styles: `[bold]...[/bold]`, `[italic]...[/italic]`

Example in a story node:

```yaml
text: "[bold][green]Standup starts now[/green][/bold]. [italic]Stay focused.[/italic]"
```

Notes:

- These tags are for TUI rendering; GUI currently shows them as plain text.
- Closing tags reset styling, so wrap only the parts you want styled.

## Stats And Checks

Stats are graded `1-6` (6 best, 1 worst):

- `Intelligence`: problem-solving, planning, technical reasoning.
- `Vibes`: social presence, empathy, communication.
- `Physique`: stamina, coordination, physically demanding tasks.
- `Luck`: chance-based outcomes and fortunate timing.

Check rules use 1d6:

- Roll `1` => `Critical Success`
- Else roll `<= stat` => `Success`
- Else roll `> stat` => `Failed`

Each check output shows:

- what the check is for,
- current stat value,
- roll result,
- outcome (`Critical Success`, `Success`, or `Failed`).

For `check vibes <npc_id> ...`:

- NPC may roll first to apply a temporary modifier to your vibes (`+1`, `0`, or `-1`).
- Then you roll once against your effective vibes (`<=` success, `>` fail, stat 6 always succeeds).
- Output shows favorability before and after.

## NPC Memory And Favorability

NPCs now track persistent relationship memory in the save state:

- `favorability` is `1-3`:
  - `1`: they do not like you
  - `2`: indifferent
  - `3`: friends
- NPC interaction effects can raise/lower favorability over time.
- NPCs can remember tagged events and respond differently on future interactions.

Starter NPC data is organized as:

- `profile`: identity and character details
- `stats`: Intelligence/Vibes/Physique/Luck
- `relationship`: includes `favorability_default`
- `dialogue`: interaction definitions and optional effects

Example effect:

```yaml
effects:
  favorability_delta: -1
  memory_tag: "player_was_dismissive"
```

## NPC Stat Unlocks (Adventure-Controlled)

NPC stats are hidden by default (`false`) until the adventure unlocks them.

- `stats npc <npc_id>` and `inspect <npc_id> stats` will stay locked until unlocked.
- Unlock from story content using either:
  - `choices[].unlock_npc_stats: [npc_id, ...]`
  - `nodes.<id>.unlock_npc_stats_on_enter: [npc_id, ...]`

Example:

```yaml
choices:
  - id: ask_it
    text: "Talk with Owen before touching tickets."
    next_node: with_it
    unlock_npc_stats:
      - it_owen
```

You can also unlock through NPC interaction logic with an intelligence-vs-NPC check:

```yaml
dialogue:
  interactions:
    profile_check:
      mode: manual
      unlock_stats_on_intelligence_check: true
```

Rule:

- You can attempt this intelligence unlock check against an NPC once.
- If that attempt fails, you must build that NPC's favorability to `3` (friends) before another unlock attempt can succeed.

### Partial visibility behavior

- If an NPC's full stats are still locked but you've revealed favorability, output will show:
  - `Some stats for <npc> are still locked.`
  - current favorability only
- Reveal favorability with a successful `check vibes <npc_id> ...`.
- View revealed favorability directly with:
  - `inspect <npc_id> favorability`
  - `inspect <npc_id> favo`
  - `inspect <npc_id> vibe`
  - `inspect <npc_id> vibes`

## Company Setting Rules

- Bullying, harassment, and aggressive actions are not allowed in adventure content.
- This project is set in a workplace context and should reflect professional behavior.
- Keep scenarios non-combat focused, even when stories are silly, lighthearted, or dramatic.
- Prefer discovery, communication, collaboration, and learning outcomes over violence or intimidation.

## Contributing

1. Create a branch for your change.
2. Add or update content under your designer folder in `adventures/<your_name>/...`.
3. Keep IDs stable and cross-references valid.
4. Run tests:

```bash
pytest -q
```

5. Commit with clear messages and open a pull request.

### Adding A New Adventure

1. Create `adventures/<creator>/<adventure_name>/manifest.yaml`.
2. Add story content file referenced by `content.story_file`.
3. Use existing world IDs or add shared entities under `world/`.
4. Launch the game and verify it appears in adventure selection.

## AI NPC Plugin Notes

- Default behavior uses `MockAIAdapter` (no API key needed).
- NPC interactions choose `manual`, `ai`, or `hybrid` mode in `world/npcs/*.yaml`.
- Replace adapter implementation in `engine/ai.py` and inject into `GameEngine` for real providers.

## Missing Outcome Logs

The engine records unhandled actions to per-adventure logs for content iteration:

- `.player/logs/%USERNAME%-<Adventure>-MissingAction.log`

Entries include UTC timestamp, reason, and original command to help authors add missing outcomes.


