"""Plain stdin/stdout TUI runner (Linux and Windows cmd friendly)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.game_engine import GameEngine

try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.completion import Completer, Completion

    HAS_PROMPT_TOOLKIT = True
except Exception:
    pt_prompt = None
    Completer = object  # type: ignore[assignment]
    Completion = object  # type: ignore[assignment]
    HAS_PROMPT_TOOLKIT = False


@dataclass(frozen=True)
class TUIColorPalette:
    reset: str = "\033[0m"
    bold: str = "\033[1m"
    italic: str = "\033[3m"
    green: str = "\033[32m"
    blue: str = "\033[34m"
    gold: str = "\033[33m"
    magenta: str = "\033[35m"
    cyan: str = "\033[36m"
    gray: str = "\033[90m"


def _is_tui_color_enabled(engine: GameEngine) -> bool:
    config = engine.saves.read_player_config()
    return bool(config.get("tui_color_enabled", True))


def _format_tui_output(message: str, color_enabled: bool) -> str:
    if not color_enabled:
        return message

    palette = TUIColorPalette()

    def apply_inline_tags(text: str) -> str:
        # Authoring tags for adventure text in TUI mode.
        tags = {
            "[bold]": palette.bold,
            "[/bold]": palette.reset,
            "[italic]": palette.italic,
            "[/italic]": palette.reset,
            "[green]": palette.green,
            "[/green]": palette.reset,
            "[blue]": palette.blue,
            "[/blue]": palette.reset,
            "[gold]": palette.gold,
            "[/gold]": palette.reset,
            "[yellow]": palette.gold,
            "[/yellow]": palette.reset,
            "[magenta]": palette.magenta,
            "[/magenta]": palette.reset,
            "[cyan]": palette.cyan,
            "[/cyan]": palette.reset,
        }
        rendered = text
        for tag, code in tags.items():
            rendered = rendered.replace(tag, code)
        return rendered

    formatted_lines: list[str] = []
    for raw_line in message.splitlines():
        line = apply_inline_tags(raw_line)
        stripped = line.strip()

        if stripped.startswith("== ") and stripped.endswith(" =="):
            line = f"{palette.bold}{palette.green}{line}{palette.reset}"
        elif stripped == "=== Interact ===":
            line = f"{palette.bold}{palette.green}{line}{palette.reset}"
        elif stripped == "=== Player ===":
            line = f"{palette.bold}{palette.blue}{line}{palette.reset}"
        elif stripped == "=== Game ===":
            line = f"{palette.bold}{palette.magenta}{line}{palette.reset}"
        elif stripped.startswith("NPCs here:") or stripped.startswith("People:"):
            line = f"{palette.gold}{line}{palette.reset}"
        elif stripped.startswith("Items here:") or stripped.startswith("Items:"):
            line = f"{palette.blue}{line}{palette.reset}"
        elif stripped.startswith("Objects here:") or stripped.startswith("Objects:"):
            line = f"{palette.magenta}{line}{palette.reset}"
        elif stripped.startswith("Choices:") or stripped.startswith("Available now:"):
            line = f"{palette.cyan}{line}{palette.reset}"
        elif stripped.startswith("Location:"):
            line = f"{palette.green}{line}{palette.reset}"
        elif stripped.startswith("[Autosave]"):
            line = f"{palette.gray}{line}{palette.reset}"

        formatted_lines.append(line)

    return "\n".join(formatted_lines)


def _print_tui(message: str, engine: GameEngine) -> None:
    print(_format_tui_output(message, _is_tui_color_enabled(engine)))


def _available_command_options(engine: GameEngine) -> list[str]:
    base = [
        "look",
        "choose",
        "talk",
        "inspect",
        "goto",
                "inventory",
        "journal list",
        "journal read 1",
        "journal add ",
        "journal remove 1",
        "calendar month",
        "calendar week",
        "calendar day",
        "calendar month weather",
        "calendar week weather",
        "calendar day weather",
        "calendar day journal",
        "calendar changes",
        "stats",
        "check intelligence ",
        "name ",
        "save ",
        "load ",
        "saves",
        "settings",
        "settings autosave on",
        "settings autosave off",
        "settings calendar",
        "settings calendar timezone UTC",
        "settings calendar seed randomize",
        "settings calendar timetravel 2026-03-07",
        "help",
        "quit",
    ]
    if not engine.adventure:
        return base

    node = engine.current_node()
    for choice in node.get("choices", []):
        choice_id = choice.get("id")
        if choice_id:
            base.append(f"choose {choice_id}")

    for npc_id in node.get("npcs", []):
        base.append(f"talk {npc_id} greet")
        base.append(f"inspect {npc_id} stats")

    for item_id in node.get("items", []):
        base.append(f"inspect {item_id}")
    for obj_id in node.get("objects", []):
        base.append(f"inspect {obj_id}")

    location_id = node.get("location_id")
    if location_id:
        connections = engine.world.get("locations", {}).get(location_id, {}).get("connections") or []
        for target in connections:
            base.append(f"goto {target}")

    deduped: list[str] = []
    seen = set()
    for cmd in base:
        if cmd not in seen:
            seen.add(cmd)
            deduped.append(cmd)
    return deduped


class _DynamicCommandCompleter(Completer):  # type: ignore[misc]
    def __init__(self, engine: GameEngine) -> None:
        self.engine = engine

    def get_completions(self, document: Any, complete_event: Any) -> Any:
        text = document.text_before_cursor or ""
        stripped = text.lstrip()
        start_pos = -len(stripped)
        lower = stripped.lower()
        for option in _available_command_options(self.engine):
            if option.lower().startswith(lower):
                yield Completion(option, start_position=start_pos)


def _read_command(engine: GameEngine, prompt_text: str = "\n> ") -> str:
    if HAS_PROMPT_TOOLKIT and pt_prompt is not None:
        completer = _DynamicCommandCompleter(engine)
        return pt_prompt(prompt_text, completer=completer, complete_while_typing=False).strip()
    return input(prompt_text).strip()


def _select_adventure(engine: GameEngine) -> str | None:
    adventures = engine.list_adventures()
    valid = [a for a in adventures if a.get("valid")]
    invalid = [a for a in adventures if not a.get("valid")]

    print("\n=== Office Text Adventure ===")
    print("Select an adventure:")
    for idx, adventure in enumerate(valid, start=1):
        print(f"{idx}. {adventure.get('name', adventure['adventure_name'])} ({adventure['key']})")
    print("R. Resume last session")
    print("Q. Quit")

    if invalid:
        print("\nIgnored invalid adventures:")
        for bad in invalid:
            print(f"- {bad['key']}: {bad.get('error')}")

    raw = input("\nChoice: ").strip().lower()
    if raw == "q":
        return None
    if raw == "r":
        message = engine.load_last_session()
        _print_tui(message, engine)
        if message.startswith("Loaded save slot"):
            return "__LOADED__"
        return _select_adventure(engine)

    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(valid):
            return str(valid[idx - 1]["key"])
    print("Invalid selection.")
    return _select_adventure(engine)


def run_tui(engine: GameEngine) -> None:
    selection = _select_adventure(engine)
    if selection is None:
        print("Goodbye.")
        return
    if selection != "__LOADED__":
        _print_tui(engine.start(selection), engine)
    else:
        _print_tui(engine.render_node(), engine)

    print("\nType 'help' for commands. Type 'quit' to exit.")
    while True:
        user_input = _read_command(engine)
        if user_input.lower() in {"quit", "exit"}:
            print("Session ended.")
            break

        if user_input.isdigit():
            node = engine.current_node()
            choices = node.get("choices", [])
            idx = int(user_input)
            if 1 <= idx <= len(choices):
                user_input = f"choose {choices[idx - 1]['id']}"
            else:
                print("Invalid numeric choice.")
                continue

        _print_tui(engine.execute_command(user_input), engine)

