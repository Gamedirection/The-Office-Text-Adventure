# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-03-07

### Added

- Global calendar subsystem with:
  - `calendar month|week|day`
  - `calendar ... weather`
  - `calendar day journal`
  - `calendar changes`
- Deterministic seeded weather and moon phase rendering by date.
- Calendar settings:
  - `settings calendar`
  - `settings calendar timezone <iana_tz>`
  - `settings calendar seed <int|randomize>`
  - `settings calendar timetravel <YYYY-MM-DD|clear>`
- New world content folders:
  - `world/events/*.yaml` (global events)
  - `world/calendar/*.yaml` (holidays)
- World change log recording for global flag/calendar mutations.
- Shared save exchange directory: `.player/shared-saves/`.
- Adventure timeline events in story files via `events[]` with `day_offset` or absolute `date`.

### Changed

- New sessions now initialize calendar state from real date + configured timezone.
- `new_game_start_date` is treated as one-shot override and consumed on next new game.
- TUI/GUI command completion lists now include calendar commands/settings.
- `calendar month` now color-tags day numbers by priority:
  - `yellow` adventure events, `blue` global events/holidays, `green` journal days.

### Fixed

- Save load path now normalizes missing/legacy calendar state safely.

## [0.2.0] - 2026-03-07

### Added

- NPC memory + relationship model with persistent favorability (`1-3`) per NPC.
- Rebased NPC content schema with `profile`, `stats`, `relationship`, and `dialogue`.
- Player naming command (`name [new player name]`) persisted to player config.
- Journal page deletion command (`journal remove <page>`).
- Missing-action logging to `.player/logs/%USERNAME%-<Adventure>-MissingAction.log`.
- In-game settings command for autosave and autosave-notification toggles.
- TUI color output mode and style-tag rendering (`[green]`, `[bold]`, `[italic]`, etc.).
- GUI Enter-to-run command submission and Tab/Shift+Tab cycling autocomplete.
- Optional favorability-only NPC visibility after successful vibe checks.

### Changed

- Command organization in help output now grouped as `Interact`, `Player`, and `Game`.
- Primary movement verb is `goto`; `move` remains a supported alias in command parsing.
- `talk`, `choose`, `inspect`, and `goto` now show contextual `Available now:` previews.
- Default no-option messaging added:
  - `No one to talk to right now`
  - `No place to move right now`
  - `No items to inspect right now`
  - `Nothing to choose right now`
- NPC stat locking flow now defaults to hidden and supports partial visibility wording:
  - `Some stats for <npc> are still locked.`

### Fixed

- Favorability can now be queried directly after reveal using:
  - `inspect <npc_id> favorability|favo|vibe|vibes`.
- Autosave notification can be disabled independently from autosave itself.

## [0.1.0] - 2026-03-07

### Added

- Initial scaffold for Office Text Adventure template.
- Shared world YAML structure for locations/items/npcs/objects.
- Adventure auto-discovery under `adventures/<creator>/<adventure_name>`.
- Python engine APIs for start/state/commands/save/load.
- PySide6 GUI and plain terminal TUI implementations.
- `.player` config/save state support with resume-last-session behavior.
- AI adapter contract with mock provider and NPC mode switching (manual/ai/hybrid).
- Starter adventures for Alex, Jon, and Dylon.
- Documentation and code snippets for onboarding and collaboration.
- Automated tests for discovery, validation, runtime, NPC behavior, and UI smoke checks.
- Migrated desktop GUI from Tkinter to PySide6 with Enter-to-run and light/dark theme toggle.
- `choose` preview behavior when no `choice_id` is provided.
- Player journal/notes system with persistent pages in `.player/journal`.
- Company setting conduct rules and non-combat storytelling guidance in README.
- Journal page removal (`journal remove <page>`).
- "Available now" command hints for talk/choose/inspect/move at each scene.
- Player/NPC stat system (Intelligence, Vibes, Physique, Luck) using 1-6 scale.
- D6 check mechanic with explicit Critical Success, Success, Failed outcomes.
- Autosave configuration (`autosave_enabled`, `autosave_slot`) in player config.

