from __future__ import annotations

import os

import pytest

from engine.game_engine import GameEngine


def test_tui_module_imports() -> None:
    from ui.tui.main import run_tui  # noqa: F401


def test_pyside6_gui_smoke(tmp_path) -> None:
    widgets = pytest.importorskip("PySide6.QtWidgets")
    from ui.gui.main import AdventureGUI

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    _app = widgets.QApplication.instance() or widgets.QApplication([])
    engine = GameEngine(player_root=tmp_path / ".player")
    window = AdventureGUI(engine)

    try:
        assert window.combo is not None
        assert window.run_button is not None
        window._start_adventure()
        window.command_entry.setText("cho")
        window._cycle_command_completion()
        assert window.command_entry.text().startswith("cho")
        window._on_theme_changed("Dark")
        config = engine.saves.read_player_config()
        assert config.get("gui_theme") == "Dark"
    finally:
        window.close()
