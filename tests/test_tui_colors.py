from __future__ import annotations

from pathlib import Path

import yaml

from engine.game_engine import GameEngine
from ui.tui.main import _available_command_options, _format_tui_output, _is_tui_color_enabled


def test_tui_color_toggle_from_player_config(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    config_dir = player_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "player.yaml").write_text(
        yaml.safe_dump({"tui_color_enabled": False}, sort_keys=False),
        encoding="utf-8",
    )

    engine = GameEngine(player_root=player_root)
    assert _is_tui_color_enabled(engine) is False


def test_tui_formatter_adds_ansi_when_enabled() -> None:
    sample = "== intro ==\nNPCs here: manager_mina\nItems here: keycard\nChoices:"
    formatted = _format_tui_output(sample, color_enabled=True)
    assert "\033[" in formatted

    plain = _format_tui_output(sample, color_enabled=False)
    assert plain == sample


def test_tui_formatter_colors_help_sections_and_inline_tags() -> None:
    sample = (
        "=== Interact ===\n"
        "=== Player ===\n"
        "=== Game ===\n"
        "[bold]Bold[/bold] [italic]Italic[/italic]"
    )
    formatted = _format_tui_output(sample, color_enabled=True)
    assert "\033[" in formatted
    assert "Bold" in formatted
    assert "Italic" in formatted


def test_tui_available_options_include_navigation_aliases(tmp_path: Path) -> None:
    engine = GameEngine(player_root=tmp_path / ".player")
    options = _available_command_options(engine)
    assert "goto" in options
