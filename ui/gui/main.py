"""PySide6 GUI for the Office Text Adventure template."""

from __future__ import annotations

import html
import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from engine.game_engine import GameEngine


class AdventureGUI(QMainWindow):
    """Simple PySide6 shell that uses the same engine API as the TUI."""

    def __init__(self, engine: GameEngine) -> None:
        super().__init__()
        self.engine = engine
        self._adventure_map: dict[str, str] = {}
        self._tab_cycle_prefix = ""
        self._tab_cycle_matches: list[str] = []
        self._tab_cycle_index = -1

        self._config = self.engine.saves.read_player_config()
        self._gui_theme = str(self._config.get("gui_theme", "Light"))

        version = getattr(self.engine, "app_version", "").strip()
        title = "Office Text Adventure"
        if version:
            title = f"Office Text Adventure v{version}"
        self.setWindowTitle(title)
        self.resize(980, 700)

        self._build_layout()
        self._populate_adventures()
        self._sync_settings_from_config()
        self._apply_theme(self._gui_theme)

    def _build_layout(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        top = QHBoxLayout()
        layout.addLayout(top)

        top.addWidget(QLabel("Adventure:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(420)
        top.addWidget(self.combo)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self._start_adventure)
        top.addWidget(self.start_button)

        self.resume_button = QPushButton("Resume Last")
        self.resume_button.clicked.connect(self._resume_last)
        top.addWidget(self.resume_button)

        top.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        top.addWidget(self.theme_combo)
        top.addStretch(1)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFrameShape(QFrame.StyledPanel)
        layout.addWidget(self.output, stretch=1)

        bottom = QHBoxLayout()
        layout.addLayout(bottom)

        self.command_entry = QLineEdit()
        self.command_entry.installEventFilter(self)
        self.command_entry.returnPressed.connect(self._run_command)
        bottom.addWidget(self.command_entry, stretch=1)

        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self._run_command)
        bottom.addWidget(self.run_button)

    def _sync_settings_from_config(self) -> None:
        if self._gui_theme not in {"Light", "Dark"}:
            self._gui_theme = "Light"
        self.theme_combo.setCurrentText(self._gui_theme)

    def _write_config(self) -> None:
        self.engine.saves.write_player_config(self._config)

    def _populate_adventures(self) -> None:
        adventures = [a for a in self.engine.list_adventures() if a.get("valid")]
        labels = [f"{a.get('name', a['adventure_name'])} ({a['key']})" for a in adventures]
        self._adventure_map = dict(zip(labels, [a["key"] for a in adventures]))
        self.combo.clear()
        self.combo.addItems(labels)

    def _append_output(self, message: str) -> None:
        html_block = self._format_gui_output_html(message)
        self.output.insertHtml(html_block + "<br><br>")
        self.output.moveCursor(QTextCursor.End)

    def _start_adventure(self) -> None:
        label = self.combo.currentText()
        key = self._adventure_map.get(label)
        if not key:
            self._append_output("Select a valid adventure first.")
            return
        self._append_output(self.engine.start(key))

    def _resume_last(self) -> None:
        self._append_output(self.engine.load_last_session())

    def _run_command(self) -> None:
        command = self.command_entry.text().strip()
        self.command_entry.clear()
        self._reset_tab_cycle()
        if not command:
            return
        self._append_output(f"> {command}")
        self._append_output(self.engine.execute_command(command))

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if watched is self.command_entry and event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_Tab:
                reverse = bool(key_event.modifiers() & Qt.ShiftModifier)
                self._cycle_command_completion(reverse=reverse)
                return True
        return super().eventFilter(watched, event)

    def _cycle_command_completion(self, reverse: bool = False) -> None:
        raw = self.command_entry.text()
        prefix = raw.strip()
        options = self._available_command_options()

        if not prefix:
            matches = options
        else:
            lower = prefix.lower()
            matches = [opt for opt in options if opt.lower().startswith(lower)]

        if not matches:
            return

        if prefix != self._tab_cycle_prefix or matches != self._tab_cycle_matches:
            self._tab_cycle_prefix = prefix
            self._tab_cycle_matches = matches
            self._tab_cycle_index = len(matches) - 1 if reverse else 0
        else:
            if reverse:
                self._tab_cycle_index = (self._tab_cycle_index - 1) % len(matches)
            else:
                self._tab_cycle_index = (self._tab_cycle_index + 1) % len(matches)

        self.command_entry.setText(matches[self._tab_cycle_index])
        self.command_entry.setCursorPosition(len(self.command_entry.text()))

    def _reset_tab_cycle(self) -> None:
        self._tab_cycle_prefix = ""
        self._tab_cycle_matches = []
        self._tab_cycle_index = -1

    def _available_command_options(self) -> list[str]:
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
            "mailbox read",
            "mailbox sendto global ",
            "mailbox sendto Alex ",
            "mailbox hide 1-3",
            "mailbox reveal 1-3",
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
            "settings calendar timezone",
            "settings calendar timezone UTC",
            "settings calendar seed view",
            "settings calendar seed randomize",
            "settings calendar timetravel help",
            "settings calendar timetravel 2026-03-07",
            "version",
            "help",
        ]
        if not self.engine.adventure:
            return base

        node = self.engine.current_node()
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
            connections = self.engine.world.get("locations", {}).get(location_id, {}).get("connections") or []
            for target in connections:
                base.append(f"goto {target}")

        deduped: list[str] = []
        seen = set()
        for cmd in base:
            if cmd not in seen:
                seen.add(cmd)
                deduped.append(cmd)
        return deduped

    def _on_theme_changed(self, theme_name: str) -> None:
        self._config["gui_theme"] = theme_name
        self._write_config()
        self._apply_theme(theme_name)

    def _apply_theme(self, theme_name: str) -> None:
        # Use TUI-inspired accents: people=gold, items=blue, location=green, objects=magenta.
        if theme_name.lower() == "dark":
            bg = "#1f1f1f"
            fg = "#f2f2f2"
            panel = "#2b2b2b"
            button = "#333333"
            border = "#666666"
        else:
            bg = "#f3f4f6"
            fg = "#151515"
            panel = "#ffffff"
            button = "#e5e7eb"
            border = "#9ca3af"

        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {bg};
                color: {fg};
            }}
            QTextEdit, QLineEdit, QComboBox, QGroupBox {{
                background-color: {panel};
                color: {fg};
                border: 1px solid {border};
                padding: 4px;
            }}
            QPushButton {{
                background-color: {button};
                color: {fg};
                border: 1px solid {border};
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background-color: {panel};
            }}
            """
        )

    def _format_gui_output_html(self, message: str) -> str:
        lines: list[str] = []
        for raw_line in message.splitlines():
            escaped = html.escape(raw_line)
            escaped = self._apply_inline_style_tags_html(escaped)
            stripped = raw_line.strip()

            color = ""
            weight = ""
            style = ""
            if stripped.startswith("== ") and stripped.endswith(" =="):
                color = "#16a34a"  # location green
                weight = "font-weight:700;"
            elif stripped == "=== Interact ===":
                color = "#16a34a"
                weight = "font-weight:700;"
            elif stripped == "=== Player ===":
                color = "#2563eb"  # items blue accent
                weight = "font-weight:700;"
            elif stripped == "=== Game ===":
                color = "#a855f7"  # objects magenta
                weight = "font-weight:700;"
            elif stripped.startswith("NPCs here:") or stripped.startswith("People:"):
                color = "#ca8a04"  # people gold
            elif stripped.startswith("Items here:") or stripped.startswith("Items:"):
                color = "#2563eb"
            elif stripped.startswith("Objects here:") or stripped.startswith("Objects:"):
                color = "#a855f7"
            elif stripped.startswith("Location:"):
                color = "#16a34a"
            elif stripped.startswith("Choices:") or stripped.startswith("Available now:"):
                color = "#0891b2"  # cyan
            elif stripped.startswith("[Autosave]"):
                color = "#6b7280"

            if color or weight or style:
                lines.append(f'<span style="color:{color};{weight}{style}">{escaped}</span>')
            else:
                lines.append(escaped)

        return "<br>".join(lines)

    def _apply_inline_style_tags_html(self, text: str) -> str:
        # TUI tags are also rendered in GUI for consistent authoring behavior.
        replacements = {
            "[bold]": '<span style="font-weight:700;">',
            "[/bold]": "</span>",
            "[italic]": '<span style="font-style:italic;">',
            "[/italic]": "</span>",
            "[green]": '<span style="color:#16a34a;">',
            "[/green]": "</span>",
            "[blue]": '<span style="color:#2563eb;">',
            "[/blue]": "</span>",
            "[gold]": '<span style="color:#ca8a04;">',
            "[/gold]": "</span>",
            "[yellow]": '<span style="color:#ca8a04;">',
            "[/yellow]": "</span>",
            "[pink]": '<span style="color:#ec4899;">',
            "[/pink]": "</span>",
            "[magenta]": '<span style="color:#a855f7;">',
            "[/magenta]": "</span>",
            "[cyan]": '<span style="color:#0891b2;">',
            "[/cyan]": "</span>",
        }
        rendered = text
        for marker, repl in replacements.items():
            rendered = rendered.replace(html.escape(marker), repl)
        return rendered


def run_gui(engine: GameEngine) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = AdventureGUI(engine)
    window.show()
    app.exec()

