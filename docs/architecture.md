# Architecture Notes

## Core flow

1. `AdventureScanner` discovers folders under `adventures/<creator>/<adventure_name>`.
2. `ContentLoader` reads shared world data and selected adventure story YAML.
3. `GameEngine` owns runtime state and exposes a shared API for all UIs.
4. `SaveManager` persists save slots and last-session pointers in `.player`.

## Shared API used by GUI and TUI

- `start(adventure_key)`
- `get_state()`
- `execute_command(command)`
- `save(slot)`
- `load(creator, adventure_id, slot)`
- `load_last_session()`

## Data boundaries

- Shared world is global and reusable.
- Story nodes and branching logic live inside each adventure folder.
- `.player` stores local runtime state and should not be used for source content.
