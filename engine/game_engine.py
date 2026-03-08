"""Main game engine with shared API used by GUI and TUI."""

from __future__ import annotations

import calendar as pycalendar
from datetime import date, datetime, timedelta, timezone
import os
from pathlib import Path
import random
from typing import Any

from engine.ai import AIAdapter, MockAIAdapter
from engine.calendar import (
    date_range,
    deterministic_seed_from_text,
    events_for_day,
    parse_iso_date,
    timezone_for_name,
    today_for_timezone,
    to_utc_timestamp,
    validate_timezone,
    weather_for_date,
    week_start,
)
from engine.exceptions import EngineError, ValidationError
from engine.loader import ContentLoader, LoadedAdventure
from engine.save_manager import SaveManager
from engine.scanner import AdventureScanner
from engine.state import GameState

STAT_ALIASES = {
    "intelligence": "intelligence",
    "intellegance": "intelligence",
    "i": "intelligence",
    "vibes": "vibes",
    "v": "vibes",
    "physique": "physique",
    "p": "physique",
    "luck": "luck",
    "l": "luck",
}

STAT_LABELS = {
    "intelligence": "Intelligence",
    "vibes": "Vibes",
    "physique": "Physique",
    "luck": "Luck",
}

STAT_DESCRIPTIONS = {
    "intelligence": "Problem-solving, analysis, planning, and technical reasoning.",
    "vibes": "Social presence, empathy, communication, and team chemistry.",
    "physique": "Stamina, coordination, and ability to handle physical tasks.",
    "luck": "Chance-driven outcomes, fortunate timing, and random breaks.",
}

DEFAULT_PLAYER_STATS = {
    "intelligence": 3,
    "vibes": 3,
    "physique": 3,
    "luck": 3,
}


class GameEngine:
    """Coordinates loading, state changes, command execution, and save/load."""

    def __init__(
        self,
        world_root: str = "world",
        adventures_root: str = "adventures",
        player_root: str = ".player",
        ai_adapter: AIAdapter | None = None,
    ) -> None:
        self.scanner = AdventureScanner(adventures_root=adventures_root)
        self.loader = ContentLoader(world_root=world_root)
        self.saves = SaveManager(player_root=player_root)
        self.ai_adapter = ai_adapter or MockAIAdapter()

        self.world: dict[str, Any] = {}
        self.adventure: LoadedAdventure | None = None
        self.state = GameState()
        self.app_version = ""

    def list_adventures(self) -> list[dict[str, Any]]:
        adventures: list[dict[str, Any]] = []
        for descriptor in self.scanner.discover_adventures():
            row = {
                "key": descriptor.key,
                "creator": descriptor.creator,
                "adventure_name": descriptor.adventure_name,
                "valid": descriptor.valid,
                "error": descriptor.error,
            }
            if descriptor.manifest:
                row["name"] = descriptor.manifest.get("name", descriptor.adventure_name)
                row["description"] = descriptor.manifest.get("description", "")
            adventures.append(row)
        return adventures

    def start(self, adventure_key: str) -> str:
        descriptor = self.scanner.get_by_key(adventure_key)
        if not descriptor:
            raise ValidationError(f"Adventure '{adventure_key}' was not found or is invalid.")

        self.world = self.loader.load_world()
        self.adventure = self.loader.load_adventure(descriptor, self.world)

        self.state = GameState(
            creator=descriptor.creator,
            adventure_id=descriptor.adventure_name,
            current_node=str(descriptor.manifest["start_node"]),
            inventory=[],
            flags={
                "player_stats": self._load_player_stats(),
                "player_name": self._load_player_name(),
                "npc_memories": {},
                "npc_stats_unlocked": self._default_npc_stats_unlocks(),
                "calendar": self._initialize_calendar_state(),
            },
            last_output="Adventure started.",
        )
        return self.render_node()

    def get_state(self) -> dict[str, Any]:
        return {
            "adventure_key": self.state.adventure_key(),
            "current_node": self.state.current_node,
            "inventory": list(self.state.inventory),
            "flags": dict(self.state.flags),
            "last_output": self.state.last_output,
            "node": self.current_node() if self.adventure else {},
        }

    def execute_command(self, command: str) -> str:
        if not self.adventure:
            return "No adventure started. Start an adventure first."

        raw = (command or "").strip()
        if not raw:
            return "Enter a command. Try: help"
        parts = raw.split()
        action = parts[0].lower()
        args = parts[1:]

        handlers = {
            "help": self._cmd_help,
            "look": self._cmd_look,
            "inventory": self._cmd_inventory,
            "choose": self._cmd_choose,
            "talk": self._cmd_talk,
            "inspect": self._cmd_inspect,
            "save": self._cmd_save,
            "load": self._cmd_load,
            "saves": self._cmd_saves,
            "list-saves": self._cmd_saves,
            "goto": self._cmd_move,
            "move": self._cmd_move,
            "journal": self._cmd_journal,
            "notes": self._cmd_journal,
            "mailbox": self._cmd_mailbox,
            "stats": self._cmd_stats,
            "check": self._cmd_check,
            "calendar": self._cmd_calendar,
            "version": self._cmd_version,
            "name": self._cmd_name,
            "settings": self._cmd_settings,
        }
        handler = handlers.get(action)
        if not handler:
            message = f"Unknown command '{action}'. Try: help"
            self._log_missing_action(raw, reason="unknown_command")
            return message
        try:
            response = handler(args)
        except (ValidationError, EngineError, FileNotFoundError) as exc:
            return str(exc) or "Command failed."
        if response.startswith("No outcome configured for action:"):
            self._log_missing_action(raw, reason="no_outcome_configured")
        return response

    def save(self, slot: str) -> str:
        if not self.adventure:
            return "No active adventure to save."
        path = self.saves.save_state(self.state, slot)
        return f"Saved to {path}"

    def load(self, creator: str, adventure_id: str, slot: str) -> str:
        loaded_state = self.saves.load_state(creator, adventure_id, slot)
        self.world = self.loader.load_world()
        descriptor = self.scanner.get_by_key(f"{creator}/{adventure_id}")
        if not descriptor:
            raise ValidationError("Cannot load save: adventure no longer available.")
        self.adventure = self.loader.load_adventure(descriptor, self.world)
        self.state = loaded_state
        self._ensure_calendar_state()
        return self.render_node(prefix=f"Loaded save slot '{slot}'.")

    def load_last_session(self) -> str:
        loaded_state, message = self.saves.load_last_session()
        if not loaded_state:
            return message
        config = self.saves.read_player_config()
        slot = str(config.get("last_session", {}).get("slot", "autosave"))
        return self.load(loaded_state.creator, loaded_state.adventure_id, slot)

    def current_node(self) -> dict[str, Any]:
        if not self.adventure:
            raise EngineError("No active adventure.")
        return self.adventure.story_nodes[self.state.current_node]

    def render_node(self, prefix: str = "") -> str:
        node = self.current_node()
        self._apply_node_npc_stat_unlocks(node)
        text = node.get("text", "No scene text.")
        choices = node.get("choices", [])
        lines = []
        if prefix:
            lines.append(prefix)
        lines.append(f"\n== {self.state.current_node} ==")
        location_id = node.get("location_id")
        if location_id:
            location_name = self.world.get("locations", {}).get(location_id, {}).get("name", location_id)
            lines.append(f"Location: {location_name} ({location_id})")
        lines.append(text)
        if choices:
            lines.append("\nChoices:")
            for idx, choice in enumerate(choices, start=1):
                lines.append(f"{idx}. {choice.get('id')}: {choice.get('text')}")
        if node.get("npcs"):
            lines.append(f"\nNPCs here: {', '.join(node.get('npcs', []))}")
        if node.get("items"):
            lines.append(f"Items here: {', '.join(node.get('items', []))}")
        if node.get("objects"):
            lines.append(f"Objects here: {', '.join(node.get('objects', []))}")
        self.state.last_output = "\n".join(lines)
        return self.state.last_output

    def _cmd_help(self, _: list[str]) -> str:
        return (
            "=== Interact ===\n"
            "- look\n"
            "- choose <choice_id>\n"
            "- talk <npc_id> [interaction]\n"
            "- inspect <item_or_object_id | npc_id stats>\n"
            "- goto <location_id>\n"
            "- check vibes <npc_id> [description]\n"
            "\n=== Player ===\n"
            "- inventory\n"
            "- journal [list|read <page>|remove <page>|add <note text>]\n"
            "- mailbox read|sendto <playername|global> <message>|hide <#-#>|reveal <#-#>\n"
            "- calendar [month|week|day] [weather|journal]\n"
            "- stats [npc <npc_id>]\n"
            "- check <intelligence|vibes|physique|luck> [description]\n"
            "- name [new player name]\n"
            "\n=== Game ===\n"
            "- save <slot>\n"
            "- load <slot>\n"
            "- saves\n"
            "- settings [autosave on|off]\n"
            "- settings autosave-notify on|off\n"
            "- settings calendar\n"
            "- version\n"
            "- help"
        )

    def _cmd_look(self, _: list[str]) -> str:
        return self.render_node()

    def _cmd_inventory(self, _: list[str]) -> str:
        if not self.state.inventory:
            return "Inventory is empty."
        return f"Inventory: {', '.join(self.state.inventory)}"

    def _cmd_choose(self, args: list[str]) -> str:
        if not args:
            node = self.current_node()
            choices = node.get("choices", [])
            if not choices:
                return "Nothing to choose right now"
            lines = [
                "Usage: choose <choice_id>",
                "Available now:",
            ]
            for choice in choices:
                lines.append(f"- choose {choice.get('id')}: {choice.get('text')}")
            return "\n".join(lines)
        choice_id = args[0]
        node = self.current_node()
        choices = node.get("choices", [])
        choice = next((c for c in choices if c.get("id") == choice_id), None)
        if not choice:
            return f"Choice '{choice_id}' not found in this node."

        required_item = choice.get("requires_item")
        if required_item and required_item not in self.state.inventory:
            return f"You need item '{required_item}' to do that."

        for item in choice.get("add_items", []):
            if item not in self.state.inventory:
                self.state.inventory.append(item)

        for item in choice.get("remove_items", []):
            if item in self.state.inventory:
                self.state.inventory.remove(item)

        for key, value in (choice.get("set_flags") or {}).items():
            self.state.flags[key] = value
            self._record_world_change(
                action="set_flag",
                details={"flag": str(key), "value": value, "node": self.state.current_node},
            )
        self._apply_choice_npc_stat_unlocks(choice)

        check_cfg = choice.get("check") or {}
        if isinstance(check_cfg, dict) and check_cfg.get("stat"):
            check_description = str(check_cfg.get("description") or choice.get("text") or "Choice check")
            check_outcome = self._run_stat_check(
                stat_name=str(check_cfg.get("stat")),
                description=check_description,
                subject_stats=self._player_stats(),
            )
            if check_outcome["result"] == "critical" and check_cfg.get("on_critical"):
                self.state.current_node = str(check_cfg.get("on_critical"))
                return check_outcome["message"] + "\n\n" + self.render_node()
            if check_outcome["result"] == "success" and check_cfg.get("on_success"):
                self.state.current_node = str(check_cfg.get("on_success"))
                return check_outcome["message"] + "\n\n" + self.render_node()
            if check_outcome["result"] == "fail" and check_cfg.get("on_fail"):
                self.state.current_node = str(check_cfg.get("on_fail"))
                return check_outcome["message"] + "\n\n" + self.render_node()
            if check_outcome["result"] == "invalid":
                return check_outcome["message"]
            if check_outcome["result"] == "fail":
                return check_outcome["message"]

        next_node = choice.get("next_node")
        if next_node:
            self.state.current_node = next_node
            autosave_note = self._autosave_if_enabled()
            output = self.render_node()
            if autosave_note:
                return output + "\n" + autosave_note
            return output
        return "Choice executed."

    def _cmd_talk(self, args: list[str]) -> str:
        if not args:
            node = self.current_node()
            npcs = node.get("npcs", [])
            if not npcs:
                return "No one to talk to right now"
            lines = ["Usage: talk <npc_id> [interaction]", "Available now:"]
            for npc_id in npcs:
                lines.append(f"- talk {npc_id} greet")
            return "\n".join(lines)
        npc_id = args[0]
        interaction = args[1] if len(args) > 1 else "greet"
        node = self.current_node()

        if npc_id not in node.get("npcs", []):
            return f"NPC '{npc_id}' is not in this location."
        npc = self.world.get("npcs", {}).get(npc_id)
        if not npc:
            return f"NPC '{npc_id}' not found."

        dialogue = npc.get("dialogue") or {}
        interactions = dialogue.get("interactions") or npc.get("interactions") or {}
        interaction_cfg = interactions.get(interaction, {})
        mode = interaction_cfg.get("mode", "manual")
        manual = (
            interaction_cfg.get("manual_responses")
            or dialogue.get("manual_responses")
            or npc.get("manual_responses")
            or []
        )
        memory = self._npc_memory(npc_id, npc)

        if mode == "manual":
            response = self._resolve_manual_response(npc_id, npc, interaction_cfg, manual, memory)
            self._apply_npc_interaction_effects(npc_id, npc, interaction_cfg)
            unlock_note = self._attempt_npc_stat_unlock_check(npc_id, npc, interaction_cfg)
            if unlock_note:
                return f"{unlock_note}\n{response}"
            return response
        if mode == "ai":
            response = self._ai_reply(npc_id, interaction, npc, interaction_cfg)
            self._apply_npc_interaction_effects(npc_id, npc, interaction_cfg)
            response = self._decorate_with_memory_tone(response, memory)
            unlock_note = self._attempt_npc_stat_unlock_check(npc_id, npc, interaction_cfg)
            if unlock_note:
                return f"{unlock_note}\n{response}"
            return response
        if mode == "hybrid":
            try:
                response = self._ai_reply(npc_id, interaction, npc, interaction_cfg)
                self._apply_npc_interaction_effects(npc_id, npc, interaction_cfg)
                response = self._decorate_with_memory_tone(response, memory)
                unlock_note = self._attempt_npc_stat_unlock_check(npc_id, npc, interaction_cfg)
                if unlock_note:
                    return f"{unlock_note}\n{response}"
                return response
            except Exception:
                response = self._resolve_manual_response(npc_id, npc, interaction_cfg, manual, memory)
                self._apply_npc_interaction_effects(npc_id, npc, interaction_cfg)
                unlock_note = self._attempt_npc_stat_unlock_check(npc_id, npc, interaction_cfg)
                if unlock_note:
                    return f"{unlock_note}\n{response}"
                return response
        return f"Unsupported interaction mode '{mode}'."

    def _cmd_inspect(self, args: list[str]) -> str:
        if not args:
            node = self.current_node()
            targets = list(node.get("items", [])) + list(node.get("objects", []))
            npc_targets = list(node.get("npcs", []))
            if not targets and not npc_targets:
                return "No items to inspect right now"
            lines = ["Usage: inspect <item_or_object_id | npc_id stats>", "Available now:"]
            for target in targets:
                lines.append(f"- inspect {target}")
            for npc_id in npc_targets:
                lines.append(f"- inspect {npc_id} stats")
            return "\n".join(lines)

        if len(args) > 2:
            return f"No outcome configured for action: inspect {' '.join(args)}"

        if len(args) >= 2 and args[1].lower() == "stats":
            npc_id = args[0]
            node = self.current_node()
            if npc_id not in node.get("npcs", []):
                return f"NPC '{npc_id}' is not in this location."
            npc = self.world.get("npcs", {}).get(npc_id)
            if not npc:
                return f"NPC '{npc_id}' not found."
            if not self._is_npc_stats_unlocked(npc_id):
                if self._is_npc_favorability_visible(npc_id, npc):
                    memory = self._npc_memory(npc_id, npc)
                    return (
                        f"Some stats for {self._npc_name(npc, npc_id)} are still locked.\n"
                        f"- Favorability: {memory.get('favorability')} "
                        "(other stats remain hidden)"
                    )
                return (
                    f"Stats for '{self._npc_name(npc, npc_id)}' are locked. "
                    "Progress this adventure to unlock them."
                )
            stats = self._normalize_stats(npc.get("stats", {}), fallback=DEFAULT_PLAYER_STATS)
            memory = self._npc_memory(npc_id, npc)
            block = self._format_stats_block(f"{self._npc_name(npc, npc_id)} stats", stats)
            return (
                f"{block}\n"
                f"- Favorability: {memory.get('favorability')} "
                "(1=dislike, 2=indifferent, 3=friends)"
            )

        if len(args) >= 2 and args[1].lower() in {"favorability", "favo", "vibe", "vibes"}:
            npc_id = args[0]
            node = self.current_node()
            if npc_id not in node.get("npcs", []):
                return f"NPC '{npc_id}' is not in this location."
            npc = self.world.get("npcs", {}).get(npc_id)
            if not npc:
                return f"NPC '{npc_id}' not found."
            if not self._is_npc_favorability_visible(npc_id, npc):
                return (
                    f"Favorability for '{self._npc_name(npc, npc_id)}' is hidden.\n"
                    "Pass a vibe check with this NPC to reveal it."
                )
            memory = self._npc_memory(npc_id, npc)
            return (
                f"Favorability for '{self._npc_name(npc, npc_id)}': {memory.get('favorability')} "
                "(1=dislike, 2=indifferent, 3=friends)"
            )

        if len(args) == 2:
            return f"No outcome configured for action: inspect {' '.join(args)}"

        target = args[0]
        node = self.current_node()
        if target in self.world.get("npcs", {}):
            npc = self.world["npcs"][target]
            if target not in node.get("npcs", []):
                return (
                    f"NPC '{target}' is not visible here.\n"
                    f"{self._npc_stats_unlock_help(target, npc)}"
                )
            if self._is_npc_stats_unlocked(target):
                return (
                    f"Use `inspect {target} stats` to view full NPC stats.\n"
                    f"Current favorability: {self._npc_memory(target, npc).get('favorability', 2)}"
                )
            return self._npc_stats_unlock_help(target, npc)
        if target in node.get("items", []):
            item = self.world["items"].get(target, {})
            return item.get("description", f"No description for item '{target}'.")
        if target in node.get("objects", []):
            obj = self.world["objects"].get(target, {})
            return obj.get("description", f"No description for object '{target}'.")
        return f"'{target}' is not visible here."

    def _cmd_save(self, args: list[str]) -> str:
        if not args:
            return "Usage: save <slot>"
        return self.save(args[0])

    def _cmd_load(self, args: list[str]) -> str:
        if not args:
            return "Usage: load <slot>"
        slot = args[0]
        slots = self.saves.list_slots(self.state.creator, self.state.adventure_id)
        if slot not in slots:
            return f"Save slot '{slot}' not found for this adventure."
        return self.load(self.state.creator, self.state.adventure_id, slot)

    def _cmd_saves(self, _: list[str]) -> str:
        slots = self.saves.list_slots(self.state.creator, self.state.adventure_id)
        if not slots:
            return "No save slots found for this adventure."
        return "Save slots:\n- " + "\n- ".join(slots)

    def _cmd_move(self, args: list[str]) -> str:
        if not args:
            node = self.current_node()
            current_location = node.get("location_id")
            connections = []
            if current_location:
                connections = (
                    self.world.get("locations", {}).get(current_location, {}).get("connections") or []
                )
            if not connections:
                return "No place to move right now"
            lines = ["Usage: goto <location_id>", "Available now:"]
            for location_id in connections:
                lines.append(f"- goto {location_id}")
            return "\n".join(lines)
        if not self.adventure:
            return "No adventure started. Start an adventure first."

        target_location = args[0]
        if target_location not in self.world.get("locations", {}):
            return f"Unknown location '{target_location}'."

        current = self.current_node()
        current_location = current.get("location_id")
        if not current_location:
            return "Current story node has no location; cannot move from here."

        loc_data = self.world["locations"].get(current_location, {})
        connections = loc_data.get("connections") or []
        if target_location != current_location and target_location not in connections:
            if connections:
                return (
                    f"You cannot move directly to '{target_location}' from '{current_location}'. "
                    f"Connected locations: {', '.join(connections)}"
                )
            return f"Location '{current_location}' has no configured connections."

        if target_location == current_location:
            return f"You are already in '{target_location}'."

        candidate_nodes = [
            (node_id, node)
            for node_id, node in self.adventure.story_nodes.items()
            if node.get("location_id") == target_location
        ]
        if not candidate_nodes:
            return (
                f"'{target_location}' exists in the shared world, but this adventure has no scene there."
            )

        next_node_id = sorted(candidate_nodes, key=lambda row: row[0])[0][0]
        self.state.current_node = next_node_id
        autosave_note = self._autosave_if_enabled()
        output = self.render_node(prefix=f"Moved to {target_location}.")
        if autosave_note:
            return output + "\n" + autosave_note
        return output

    def _cmd_journal(self, args: list[str]) -> str:
        if not args:
            return (
                "Usage: journal [list|read <page>|remove <page>|add <note text>]\n"
                "Examples:\n"
                "- journal list\n"
                "- journal read 2\n"
                "- journal remove 2\n"
                "- journal add Check the sprint board before standup"
            )

        action = args[0].lower()
        if action == "list":
            pages = self.saves.list_journal_pages(self.state.creator, self.state.adventure_id)
            if not pages:
                return "Journal is empty."
            lines = ["Journal pages:"]
            for page in pages:
                text = str(page.get("text", "")).strip()
                preview = text if len(text) <= 70 else text[:67] + "..."
                lines.append(f"- {page.get('page')}: {preview}")
            return "\n".join(lines)

        if action == "read":
            if len(args) < 2 or not args[1].isdigit():
                return "Usage: journal read <page>"
            target_page = int(args[1])
            pages = self.saves.list_journal_pages(self.state.creator, self.state.adventure_id)
            page = next((p for p in pages if int(p.get("page", 0)) == target_page), None)
            if not page:
                return f"Journal page {target_page} not found."
            return (
                f"Journal Page {page.get('page')}\n"
                f"Created: {page.get('created_at')}\n"
                f"Location: {page.get('location_id')} | Node: {page.get('node_id')}\n"
                f"\n{page.get('text', '')}"
            )

        if action == "add":
            note_text = " ".join(args[1:]).strip()
            if not note_text:
                return "Usage: journal add <note text>"
            node = self.current_node()
            page_number = self.saves.append_journal_page(
                creator=self.state.creator,
                adventure_id=self.state.adventure_id,
                node_id=self.state.current_node,
                location_id=str(node.get("location_id", "")),
                text=note_text,
            )
            return f"Added journal page {page_number}."

        if action == "remove":
            if len(args) < 2 or not args[1].isdigit():
                return "Usage: journal remove <page>"
            removed = self.saves.remove_journal_page(
                self.state.creator,
                self.state.adventure_id,
                int(args[1]),
            )
            if not removed:
                return f"Journal page {args[1]} not found."
            return f"Removed journal page {args[1]}."

        return "Unknown journal command. Use: journal [list|read <page>|remove <page>|add <note text>]"

    def _cmd_mailbox(self, args: list[str]) -> str:
        if not args:
            return (
                "Usage: mailbox read | mailbox sendto <playername|global> <message> | "
                "mailbox hide <#-#> | mailbox reveal <#-#>"
            )
        action = args[0].lower()
        hidden_ids = self.state.flags.setdefault("mailbox_hidden_ids", [])
        if not isinstance(hidden_ids, list):
            hidden_ids = []
            self.state.flags["mailbox_hidden_ids"] = hidden_ids
        hidden_set = {int(x) for x in hidden_ids if str(x).isdigit()}

        if action == "read":
            player_name = self._player_name().strip().lower()
            messages = self.saves.read_global_mailbox()
            visible: list[dict[str, Any]] = []
            for message in messages:
                message_id = int(message.get("id", 0))
                recipient = str(message.get("recipient", "")).strip()
                recipient_key = recipient.lower()
                sender = str(message.get("sender", "")).strip().lower()
                sender_is_current = sender == player_name
                is_for_player = recipient_key in {"global", player_name}
                if not sender_is_current and not is_for_player:
                    continue
                if message_id in hidden_set:
                    continue
                visible.append(message)

            if not visible:
                return "Mailbox is empty."

            lines = [f"Mailbox for {self._player_name()}:"]
            for message in visible:
                message_id = int(message.get("id", 0))
                sender = str(message.get("sender", "Unknown"))
                recipient = str(message.get("recipient", "global"))
                text = str(message.get("text", "")).strip()
                sender_is_current = sender.strip().lower() == self._player_name().strip().lower()
                if sender_is_current:
                    lines.append(
                        f"[pink]> #{message_id} [{recipient}] from {sender}: {text}[/pink]"
                    )
                else:
                    tag = "blue" if recipient.lower() == "global" else "green"
                    lines.append(
                        f"[{tag}]#{message_id} [{recipient}] from {sender}: {text}[/{tag}]"
                    )
            return "\n".join(lines)

        if action == "sendto":
            if len(args) < 3:
                return "Usage: mailbox sendto <playername|global> <message>"
            recipient = args[1].strip()
            if not recipient:
                return "Usage: mailbox sendto <playername|global> <message>"
            text = " ".join(args[2:]).strip()
            if not text:
                return "Usage: mailbox sendto <playername|global> <message>"
            recipient_value = "global" if recipient.lower() == "global" else recipient
            message_id = self.saves.append_global_mailbox_message(
                sender=self._player_name(),
                recipient=recipient_value,
                text=text,
            )
            return f"Mailbox message #{message_id} sent to {recipient_value}."

        if action in {"hide", "reveal"}:
            if len(args) != 2:
                return f"Usage: mailbox {action} <#-#>"
            id_values = self._parse_message_id_range(args[1])
            if not id_values:
                return f"Usage: mailbox {action} <#-#>"
            if action == "hide":
                hidden_set.update(id_values)
                self.state.flags["mailbox_hidden_ids"] = sorted(hidden_set)
                return f"Hid mailbox messages: {', '.join(str(v) for v in sorted(id_values))}"
            hidden_set.difference_update(id_values)
            self.state.flags["mailbox_hidden_ids"] = sorted(hidden_set)
            return f"Revealed mailbox messages: {', '.join(str(v) for v in sorted(id_values))}"

        return "Unknown mailbox command. Use: mailbox read|sendto|hide|reveal"

    def _cmd_stats(self, args: list[str]) -> str:
        if args and args[0].lower() == "npc":
            if len(args) < 2:
                return "Usage: stats npc <npc_id>"
            npc_id = args[1]
            npc = self.world.get("npcs", {}).get(npc_id)
            if not npc:
                return f"NPC '{npc_id}' not found."
            if not self._is_npc_stats_unlocked(npc_id):
                if self._is_npc_favorability_visible(npc_id, npc):
                    memory = self._npc_memory(npc_id, npc)
                    return (
                        f"Some stats for {self._npc_name(npc, npc_id)} are still locked.\n"
                        f"- Favorability: {memory.get('favorability')} "
                        "(other stats remain hidden)"
                    )
                return (
                    f"Stats for '{self._npc_name(npc, npc_id)}' are locked. "
                    "Progress this adventure to unlock them."
                )
            stats = self._normalize_stats(npc.get("stats", {}), fallback=DEFAULT_PLAYER_STATS)
            memory = self._npc_memory(npc_id, npc)
            block = self._format_stats_block(f"{self._npc_name(npc, npc_id)} stats", stats)
            return (
                f"{block}\n"
                f"- Favorability: {memory.get('favorability')} "
                "(1=dislike, 2=indifferent, 3=friends)"
            )

        stats = self._player_stats()
        lines = [self._format_stats_block("Player stats", stats)]
        lines.append(f"- Player Name: {self._player_name()}")
        lines.append(
            "\nD6 Check Rule: roll 1d6. Roll of 1 = Critical Success. "
            "Otherwise, roll <= stat = Success, roll > stat = Failed."
        )
        return "\n".join(lines)

    def _cmd_check(self, args: list[str]) -> str:
        if not args:
            return "Usage: check <intelligence|vibes|physique|luck> [description]"
        stat_name = args[0]
        normalized = STAT_ALIASES.get(stat_name.lower())
        if normalized == "vibes" and len(args) >= 2 and args[1] in self.world.get("npcs", {}):
            npc_id = args[1]
            description = " ".join(args[2:]).strip() or f"Vibe check with {npc_id}"
            return self._run_npc_vibe_check(npc_id, description)
        description = " ".join(args[1:]).strip() or f"Check for {stat_name}"
        outcome = self._run_stat_check(stat_name, description, self._player_stats())
        return outcome["message"]

    def _cmd_calendar(self, args: list[str]) -> str:
        state = self._calendar_state()
        target = parse_iso_date(state["current_date"], field_name="calendar.current_date")
        seed = int(state["seed"])

        if not args:
            return (
                "Usage: calendar [month|week|day|changes] [weather|journal]\n"
                "Examples:\n"
                "- calendar month\n"
                "- calendar month weather\n"
                "- calendar week\n"
                "- calendar week weather\n"
                "- calendar day\n"
                "- calendar day weather\n"
                "- calendar day journal\n"
                "- calendar changes"
            )

        section = args[0].lower()
        mode = args[1].lower() if len(args) > 1 else ""

        if section == "changes":
            entries = state.get("world_change_log", [])
            if not isinstance(entries, list) or not entries:
                return "No recorded global world changes yet."
            lines = ["Global world change log:"]
            for entry in entries[-20:]:
                if not isinstance(entry, dict):
                    continue
                when = str(entry.get("timestamp", ""))
                action = str(entry.get("action", "unknown"))
                details = entry.get("details", {})
                lines.append(f"- {when} | {action} | {details}")
            return "\n".join(lines)

        if section == "month":
            if mode == "weather":
                return self._calendar_month_weather(seed, target)
            return self._calendar_month_summary(target)

        if section == "week":
            if mode == "weather":
                return self._calendar_week_weather(seed, target)
            return self._calendar_week_summary(target)

        if section == "day":
            if mode == "weather":
                return self._calendar_day_weather(seed, target)
            if mode == "journal":
                return self._calendar_day_journal(target)
            return self._calendar_day_summary(seed, target)

        return "Unknown calendar command. Use: calendar [month|week|day|changes] [weather|journal]"

    def _cmd_name(self, args: list[str]) -> str:
        if not args:
            return f"Player name: {self._player_name()}"
        new_name = " ".join(args).strip()
        if not new_name:
            return "Usage: name [new player name]"
        self.state.flags["player_name"] = new_name
        config = self.saves.read_player_config()
        config["player_name"] = new_name
        self.saves.write_player_config(config)
        return f"Player name set to: {new_name}"

    def _cmd_version(self, _: list[str]) -> str:
        version = str(getattr(self, "app_version", "") or "").strip()
        if version:
            return f"Version: {version}"
        return "Version: unknown"

    def _cmd_settings(self, args: list[str]) -> str:
        config = self.saves.read_player_config()
        if not args:
            autosave = "on" if bool(config.get("autosave_enabled", False)) else "off"
            autosave_notify = "on" if bool(config.get("autosave_notify_enabled", True)) else "off"
            slot = str(config.get("autosave_slot", "autosave"))
            return (
                "Settings:\n"
                f"- autosave: {autosave}\n"
                f"- autosave-notify: {autosave_notify}\n"
                f"- autosave_slot: {slot}\n"
                "Usage: settings autosave on|off | settings autosave-notify on|off | settings calendar"
            )

        if len(args) == 2 and args[0].lower() == "autosave":
            value = args[1].lower()
            if value not in {"on", "off"}:
                return "Usage: settings autosave on|off"
            enabled = value == "on"
            config["autosave_enabled"] = enabled
            self.saves.write_player_config(config)
            state = "enabled" if enabled else "disabled"
            return f"Autosave {state}."

        if len(args) == 2 and args[0].lower() == "autosave-notify":
            value = args[1].lower()
            if value not in {"on", "off"}:
                return "Usage: settings autosave-notify on|off"
            enabled = value == "on"
            config["autosave_notify_enabled"] = enabled
            self.saves.write_player_config(config)
            state = "enabled" if enabled else "disabled"
            return f"Autosave notification {state}."

        if args[0].lower() == "calendar":
            calendar_state = self._calendar_state()
            if len(args) == 1:
                pending = str(config.get("new_game_start_date", "none"))
                return (
                    "Calendar Settings:\n"
                    f"- timezone: {calendar_state['timezone']}\n"
                    f"- current_date: {calendar_state['current_date']}\n"
                    f"- seed: {calendar_state['seed']}\n"
                    f"- next_new_game_date_override: {pending}\n"
                    "settings calendar timezone <iana_tz>\n"
                    "settings calendar seed <view|int|randomize>\n"
                    "settings calendar timetravel <YYYY-MM-DD|clear|help>"
                )

            sub = args[1].lower() if len(args) > 1 else ""

            if sub == "timezone":
                if len(args) == 2:
                    return f"Calendar timezone: {calendar_state['timezone']}"
                if len(args) != 3:
                    return "Usage: settings calendar timezone <iana_tz>"
                tz_name = args[2]
                try:
                    validate_timezone(tz_name)
                except ValidationError as exc:
                    return str(exc)
                config["calendar_timezone"] = tz_name
                self.saves.write_player_config(config)
                calendar_state["timezone"] = tz_name
                self._record_world_change("calendar_timezone_updated", {"timezone": tz_name})
                return (
                    f"Calendar timezone set to {tz_name}. "
                    "Current character date remains unchanged."
                )

            if sub == "seed":
                if len(args) == 2:
                    return "Usage: settings calendar seed <view|int|randomize>"
                if len(args) != 3:
                    return "Usage: settings calendar seed <view|int|randomize>"
                raw = args[2].lower()
                if raw == "view":
                    return f"Calendar seed: {calendar_state['seed']}"
                if raw == "randomize":
                    new_seed = random.randint(1, 2_147_483_647)
                else:
                    try:
                        new_seed = int(raw)
                    except ValueError:
                        return "Usage: settings calendar seed <view|int|randomize>"
                config["calendar_seed"] = int(new_seed)
                self.saves.write_player_config(config)
                calendar_state["seed"] = int(new_seed)
                self._record_world_change("calendar_seed_updated", {"seed": int(new_seed)})
                return f"Calendar seed set to {new_seed}."

            if sub == "timetravel":
                if len(args) == 2:
                    return "Usage: settings calendar timetravel <YYYY-MM-DD|clear|help>"
                if len(args) != 3:
                    return "Usage: settings calendar timetravel <YYYY-MM-DD|clear|help>"
                target = args[2].lower()
                if target == "help":
                    pending = str(config.get("new_game_start_date", "none"))
                    return (
                        "Time travel is new-game-only.\n"
                        "Use `settings calendar timetravel YYYY-MM-DD` to set the next new session start date.\n"
                        "Use `settings calendar timetravel clear` to remove it.\n"
                        f"Current pending override: {pending}"
                    )
                if target == "clear":
                    config.pop("new_game_start_date", None)
                    self.saves.write_player_config(config)
                    return "New-game time travel override cleared."
                try:
                    parse_iso_date(args[2], field_name="timetravel date")
                except ValidationError as exc:
                    return str(exc)
                config["new_game_start_date"] = args[2]
                self.saves.write_player_config(config)
                return (
                    f"Time travel date for next new game set to {args[2]}. "
                    "This does not change your current character timeline."
                )

            return (
                "Unknown calendar settings command. "
                "Usage: settings calendar | settings calendar timezone <iana_tz> | "
                "settings calendar seed <view|int|randomize> | "
                "settings calendar timetravel <YYYY-MM-DD|clear|help>"
            )

        return (
            "Unknown settings command. Usage: settings autosave on|off | "
            "settings autosave-notify on|off | settings calendar"
        )

    def _ai_reply(
        self,
        npc_id: str,
        interaction: str,
        npc: dict[str, Any],
        interaction_cfg: dict[str, Any],
    ) -> str:
        npc_prompt_append = str(npc.get("ai_prompt_append", "")).strip()
        interaction_prompt_append = str(interaction_cfg.get("ai_prompt_append", "")).strip()
        prompt_parts = [part for part in [npc_prompt_append, interaction_prompt_append] if part]

        node = self.current_node()
        context = {
            "npc_id": npc_id,
            "npc_name": self._npc_name(npc, npc_id),
            "npc_role": self._npc_role(npc),
            "npc_stats": self._normalize_stats(npc.get("stats", {}), fallback=DEFAULT_PLAYER_STATS),
            "npc_profile": {
                "personality": self._npc_profile_field(npc, "personality"),
                "age": self._npc_profile_field(npc, "age"),
                "appearance": self._npc_profile_field(npc, "appearance"),
                "tone": self._npc_profile_field(npc, "tone"),
                "backstory": self._npc_profile_field(npc, "backstory"),
                "extra_context": self._npc_profile_field(npc, "extra_context", default={}),
            },
            "npc_memory": self._npc_memory(npc_id, npc),
            "interaction": interaction,
            "node_id": self.state.current_node,
            "node_text": node.get("text", ""),
            "location_id": node.get("location_id", ""),
            "adventure_id": self.state.adventure_id,
            "player_name": self._player_name(),
            "player_action": f"talk {npc_id} {interaction}",
            "prompt_append": "\n".join(prompt_parts),
        }
        return self.ai_adapter.generate_reply(context)

    def _load_player_stats(self) -> dict[str, int]:
        config = self.saves.read_player_config()
        configured = config.get("player_stats", {})
        return self._normalize_stats(configured, fallback=DEFAULT_PLAYER_STATS)

    def _load_player_name(self) -> str:
        config = self.saves.read_player_config()
        return str(config.get("player_name", "Player"))

    def _default_calendar_seed(self) -> int:
        username = os.environ.get("USERNAME", "player")
        return deterministic_seed_from_text(username)

    def _initialize_calendar_state(self) -> dict[str, Any]:
        config = self.saves.read_player_config()
        timezone_name = str(config.get("calendar_timezone", "UTC"))
        try:
            validate_timezone(timezone_name)
        except ValidationError:
            timezone_name = "UTC"

        seed = config.get("calendar_seed")
        if seed is None:
            seed = self._default_calendar_seed()
            config["calendar_seed"] = int(seed)
        try:
            seed_int = int(seed)
        except (TypeError, ValueError):
            seed_int = self._default_calendar_seed()
            config["calendar_seed"] = int(seed_int)

        override_date = config.get("new_game_start_date")
        if override_date:
            try:
                start_date = parse_iso_date(str(override_date), field_name="new_game_start_date")
                config.pop("new_game_start_date", None)
                self.saves.write_player_config(config)
            except ValidationError:
                start_date = today_for_timezone(timezone_name)
        else:
            self.saves.write_player_config(config)
            start_date = today_for_timezone(timezone_name)

        return {
            "current_date": start_date.isoformat(),
            "adventure_start_date": start_date.isoformat(),
            "timezone": timezone_name,
            "seed": int(seed_int),
            "world_change_log": [],
        }

    def _ensure_calendar_state(self) -> None:
        calendar_state = self.state.flags.get("calendar")
        if not isinstance(calendar_state, dict):
            self.state.flags["calendar"] = self._initialize_calendar_state()
            return
        calendar_state.setdefault("current_date", today_for_timezone("UTC").isoformat())
        calendar_state.setdefault("adventure_start_date", calendar_state["current_date"])
        calendar_state.setdefault("timezone", "UTC")
        calendar_state.setdefault("seed", self._default_calendar_seed())
        calendar_state.setdefault("world_change_log", [])
        try:
            validate_timezone(str(calendar_state["timezone"]))
        except ValidationError:
            calendar_state["timezone"] = "UTC"
        calendar_state["seed"] = int(calendar_state["seed"])
        try:
            parse_iso_date(str(calendar_state["current_date"]), field_name="calendar.current_date")
        except ValidationError:
            calendar_state["current_date"] = today_for_timezone(str(calendar_state["timezone"])).isoformat()
        try:
            parse_iso_date(
                str(calendar_state["adventure_start_date"]),
                field_name="calendar.adventure_start_date",
            )
        except ValidationError:
            calendar_state["adventure_start_date"] = calendar_state["current_date"]

    def _calendar_state(self) -> dict[str, Any]:
        self._ensure_calendar_state()
        calendar_state = self.state.flags.get("calendar")
        if isinstance(calendar_state, dict):
            return calendar_state
        fallback = self._initialize_calendar_state()
        self.state.flags["calendar"] = fallback
        return fallback

    def _record_world_change(self, action: str, details: dict[str, Any]) -> None:
        calendar_state = self._calendar_state()
        log = calendar_state.setdefault("world_change_log", [])
        if not isinstance(log, list):
            log = []
            calendar_state["world_change_log"] = log
        log.append(
            {
                "timestamp": to_utc_timestamp(),
                "action": action,
                "details": details,
            }
        )

    def _calendar_month_summary(self, target: date) -> str:
        cal = pycalendar.Calendar(firstweekday=0)
        matrix = cal.monthdayscalendar(target.year, target.month)
        lines = [f"Calendar Month: {target.strftime('%B %Y')}"]
        lines.append("Mo Tu We Th Fr Sa Su")
        for week in matrix:
            tokens: list[str] = []
            for day in week:
                if day == 0:
                    tokens.append("  ")
                    continue
                day_date = date(target.year, target.month, day)
                tag = self._calendar_day_priority_color_tag(day_date)
                rendered = f"{day:2d}"
                if tag:
                    rendered = f"[{tag}]{rendered}[/{tag}]"
                tokens.append(rendered)
            lines.append(" ".join(tokens))
        lines.append("Legend: [yellow]Adventure[/yellow], [blue]Global[/blue], [green]Journal[/green]")
        return "\n".join(lines)

    def _calendar_month_weather(self, seed: int, target: date) -> str:
        cal = pycalendar.Calendar(firstweekday=0)
        matrix = cal.monthdayscalendar(target.year, target.month)
        lines = [f"Calendar Month Weather (emoji): {target.strftime('%B %Y')}"]
        lines.append("Mo Tu We Th Fr Sa Su")
        for week in matrix:
            tokens: list[str] = []
            for day in week:
                if day == 0:
                    tokens.append("  ")
                    continue
                day_date = date(target.year, target.month, day)
                tokens.append(weather_for_date(seed, day_date).emoji)
            lines.append(" ".join(tokens))
        return "\n".join(lines)

    def _calendar_week_summary(self, target: date) -> str:
        start = week_start(target)
        days = date_range(start, 7)
        lines = [f"Calendar Week: {start.isoformat()} to {(start + timedelta(days=6)).isoformat()}"]
        for day in days:
            combined = self._all_events_for_day(day)
            if combined:
                descriptions = "; ".join(self._format_event_for_output(row) for row in combined)
                lines.append(f"- {day.isoformat()} ({day.strftime('%a')}): {descriptions}")
            else:
                lines.append(f"- {day.isoformat()} ({day.strftime('%a')}): no events")
        return "\n".join(lines)

    def _calendar_week_weather(self, seed: int, target: date) -> str:
        start = week_start(target)
        lines = [f"Week Weather: {start.isoformat()} to {(start + timedelta(days=6)).isoformat()}"]
        for day in date_range(start, 7):
            weather = weather_for_date(seed, day)
            lines.append(
                f"- {day.isoformat()} ({day.strftime('%a')}): {weather.emoji} {weather.weather_type} | Moon: {weather.moon_phase}"
            )
        return "\n".join(lines)

    def _calendar_day_summary(self, seed: int, target: date) -> str:
        weather = weather_for_date(seed, target)
        lines = [f"Calendar Day: {target.isoformat()} ({target.strftime('%A')})"]
        lines.append(f"- Forecast: {weather.emoji} {weather.weather_type}")
        lines.append(f"- Moon Phase: {weather.moon_phase}")
        events = events_for_day(self.world, target)
        adventure_events = self._adventure_events_for_day(target)
        events = adventure_events + events
        if not events:
            lines.append("- Events: none")
        else:
            lines.append("- Events:")
            for event in events:
                lines.append(f"  - {self._format_event_for_output(event)}")
        return "\n".join(lines)

    def _calendar_day_weather(self, seed: int, target: date) -> str:
        weather = weather_for_date(seed, target)
        return (
            f"Day Weather: {target.isoformat()} ({target.strftime('%A')})\n"
            f"- Forecast: {weather.emoji} {weather.weather_type}\n"
            f"- Moon Phase: {weather.moon_phase}"
        )

    def _calendar_day_journal(self, target: date) -> str:
        state = self._calendar_state()
        timezone_name = str(state.get("timezone", "UTC"))
        tz = timezone_for_name(timezone_name)
        pages = self.saves.list_journal_pages(self.state.creator, self.state.adventure_id)
        filtered: list[dict[str, Any]] = []
        for page in pages:
            created_raw = page.get("created_at")
            if not created_raw:
                continue
            try:
                created_dt = datetime.fromisoformat(str(created_raw))
            except ValueError:
                continue
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            local_date = created_dt.astimezone(tz).date()
            if local_date == target:
                filtered.append(page)

        if not filtered:
            return f"No journal entries on {target.isoformat()}."

        lines = [f"Journal entries for {target.isoformat()}:"]
        for page in filtered:
            lines.append(f"- Page {page.get('page')}: {page.get('text', '')}")
        return "\n".join(lines)

    def _adventure_events_for_day(self, target: date) -> list[dict[str, Any]]:
        if not self.adventure:
            return []
        calendar_state = self._calendar_state()
        start_date = parse_iso_date(
            str(calendar_state.get("adventure_start_date")),
            field_name="calendar.adventure_start_date",
        )
        day_events: list[dict[str, Any]] = []
        for event in self.adventure.events:
            if not isinstance(event, dict):
                continue
            absolute = event.get("date")
            if absolute:
                event_date = parse_iso_date(str(absolute), field_name="adventure event date")
            else:
                offset = int(event.get("day_offset", 0))
                event_date = start_date + timedelta(days=offset)
            if event_date == target:
                row = dict(event)
                row["source"] = "adventure"
                day_events.append(row)
        return day_events

    def _all_events_for_day(self, target: date) -> list[dict[str, Any]]:
        global_events: list[dict[str, Any]] = []
        for row in events_for_day(self.world, target):
            if not isinstance(row, dict):
                continue
            cloned = dict(row)
            cloned.setdefault("source", "global")
            if cloned.get("type") == "holiday":
                cloned["source"] = "holiday"
            global_events.append(cloned)
        return self._adventure_events_for_day(target) + global_events

    def _journal_dates(self) -> set[date]:
        state = self._calendar_state()
        timezone_name = str(state.get("timezone", "UTC"))
        tz = timezone_for_name(timezone_name)
        pages = self.saves.list_journal_pages(self.state.creator, self.state.adventure_id)
        result: set[date] = set()
        for page in pages:
            created_raw = page.get("created_at")
            if not created_raw:
                continue
            try:
                created_dt = datetime.fromisoformat(str(created_raw))
            except ValueError:
                continue
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            result.add(created_dt.astimezone(tz).date())
        return result

    def _calendar_day_priority_color_tag(self, target: date) -> str:
        if self._adventure_events_for_day(target):
            return "yellow"
        if events_for_day(self.world, target):
            return "blue"
        if target in self._journal_dates():
            return "green"
        return ""

    def _event_color_tag(self, event: dict[str, Any]) -> str:
        source = str(event.get("source", "global")).lower()
        if source == "adventure":
            return "yellow"
        if source in {"global", "holiday"}:
            return "blue"
        return ""

    def _format_event_for_output(self, event: dict[str, Any]) -> str:
        name = str(event.get("name", "Event"))
        description = str(event.get("description", "")).strip()
        tag = self._event_color_tag(event)
        if tag:
            name = f"[{tag}]{name}[/{tag}]"
        if description:
            return f"{name}: {description}"
        return name

    def _parse_message_id_range(self, raw: str) -> set[int]:
        token = str(raw).strip()
        if not token:
            return set()
        if "-" not in token:
            if token.isdigit():
                return {int(token)}
            return set()
        start_raw, end_raw = token.split("-", 1)
        if not start_raw.isdigit() or not end_raw.isdigit():
            return set()
        start = int(start_raw)
        end = int(end_raw)
        if start <= 0 or end <= 0:
            return set()
        if end < start:
            start, end = end, start
        return set(range(start, end + 1))

    def _default_npc_stats_unlocks(self) -> dict[str, bool]:
        return {npc_id: False for npc_id in self.world.get("npcs", {}).keys()}

    def _npc_stats_unlocks(self) -> dict[str, bool]:
        unlocks = self.state.flags.get("npc_stats_unlocked")
        if not isinstance(unlocks, dict):
            unlocks = self._default_npc_stats_unlocks()
            self.state.flags["npc_stats_unlocked"] = unlocks
        for npc_id in self.world.get("npcs", {}).keys():
            unlocks.setdefault(npc_id, False)
        return unlocks

    def _is_npc_stats_unlocked(self, npc_id: str) -> bool:
        return bool(self._npc_stats_unlocks().get(npc_id, False))

    def _set_npc_stats_unlock(self, npc_id: str, unlocked: bool) -> None:
        unlocks = self._npc_stats_unlocks()
        if npc_id in self.world.get("npcs", {}):
            unlocks[npc_id] = bool(unlocked)

    def _apply_node_npc_stat_unlocks(self, node: dict[str, Any]) -> None:
        unlock_list = node.get("unlock_npc_stats_on_enter", [])
        if isinstance(unlock_list, list):
            for npc_id in unlock_list:
                self._set_npc_stats_unlock(str(npc_id), True)

    def _apply_choice_npc_stat_unlocks(self, choice: dict[str, Any]) -> None:
        unlock_list = choice.get("unlock_npc_stats", [])
        if isinstance(unlock_list, list):
            for npc_id in unlock_list:
                self._set_npc_stats_unlock(str(npc_id), True)

        lock_list = choice.get("lock_npc_stats", [])
        if isinstance(lock_list, list):
            for npc_id in lock_list:
                self._set_npc_stats_unlock(str(npc_id), False)

    def _player_name(self) -> str:
        return str(self.state.flags.get("player_name", "Player"))

    def _player_stats(self) -> dict[str, int]:
        return self._normalize_stats(self.state.flags.get("player_stats", {}), fallback=DEFAULT_PLAYER_STATS)

    def _npc_name(self, npc: dict[str, Any], fallback_id: str) -> str:
        profile = npc.get("profile") or {}
        return str(profile.get("name") or npc.get("name") or fallback_id)

    def _npc_role(self, npc: dict[str, Any]) -> str:
        profile = npc.get("profile") or {}
        return str(profile.get("role") or npc.get("role") or "")

    def _npc_profile_field(self, npc: dict[str, Any], field: str, default: Any = "") -> Any:
        profile = npc.get("profile") or {}
        return profile.get(field, npc.get(field, default))

    def _npc_memory(self, npc_id: str, npc: dict[str, Any]) -> dict[str, Any]:
        memories = self.state.flags.setdefault("npc_memories", {})
        existing = memories.get(npc_id)
        if isinstance(existing, dict):
            return existing

        relationship = npc.get("relationship") or {}
        default_favorability = relationship.get("favorability_default", 2)
        try:
            favorability = int(default_favorability)
        except (TypeError, ValueError):
            favorability = 2
        memory = {
            "favorability": max(1, min(3, favorability)),
            "events": [],
            "favorability_visible": False,
        }
        memories[npc_id] = memory
        return memory

    def _is_npc_favorability_visible(self, npc_id: str, npc: dict[str, Any]) -> bool:
        memory = self._npc_memory(npc_id, npc)
        return bool(memory.get("favorability_visible", False))

    def _apply_npc_interaction_effects(
        self,
        npc_id: str,
        npc: dict[str, Any],
        interaction_cfg: dict[str, Any],
    ) -> None:
        effects = interaction_cfg.get("effects") or {}
        if not isinstance(effects, dict):
            return

        memory = self._npc_memory(npc_id, npc)
        delta = effects.get("favorability_delta", 0)
        try:
            delta_value = int(delta)
        except (TypeError, ValueError):
            delta_value = 0
        memory["favorability"] = max(1, min(3, int(memory.get("favorability", 2)) + delta_value))

        memory_tag = effects.get("memory_tag")
        if memory_tag:
            events = memory.setdefault("events", [])
            events.append(str(memory_tag))

    def _resolve_manual_response(
        self,
        npc_id: str,
        npc: dict[str, Any],
        interaction_cfg: dict[str, Any],
        manual: list[Any],
        memory: dict[str, Any],
    ) -> str:
        favorability = int(memory.get("favorability", 2))
        if favorability <= 1:
            low = interaction_cfg.get("low_favorability_responses") or []
            if low:
                return str(low[0])
        if favorability >= 3:
            high = interaction_cfg.get("high_favorability_responses") or []
            if high:
                return str(high[0])
        if manual:
            return str(manual[0])
        return f"{npc_id} has nothing to say."

    def _attempt_npc_stat_unlock_check(
        self,
        npc_id: str,
        npc: dict[str, Any],
        interaction_cfg: dict[str, Any],
    ) -> str:
        if self._is_npc_stats_unlocked(npc_id):
            return ""
        if not bool(interaction_cfg.get("unlock_stats_on_intelligence_check", False)):
            return ""

        memory = self._npc_memory(npc_id, npc)
        favorability = int(memory.get("favorability", 2))
        attempted_once = bool(memory.get("intelligence_unlock_attempted", False))

        if attempted_once and favorability < 3:
            return (
                f"NPC Intelligence Check ({self._npc_name(npc, npc_id)}): already attempted. "
                "Raise favorability to 3 to unlock stats."
            )

        player_int = self._player_stats().get("intelligence", 1)
        npc_int = self._normalize_stats(npc.get("stats", {}), fallback=DEFAULT_PLAYER_STATS).get(
            "intelligence", 1
        )
        player_roll = random.randint(1, 6)
        npc_roll = random.randint(1, 6)
        memory["intelligence_unlock_attempted"] = True

        if player_roll == 1:
            result = "Critical Success"
            unlocked = True
        else:
            player_score = player_int - player_roll
            npc_score = npc_int - npc_roll
            unlocked = player_score >= npc_score
            result = "Success" if unlocked else "Failed"

        if unlocked:
            self._set_npc_stats_unlock(npc_id, True)

        status = "UNLOCKED" if unlocked else "LOCKED"
        return (
            f"NPC Intelligence Check ({self._npc_name(npc, npc_id)}): "
            f"Player INT {player_int} (roll {player_roll}) vs "
            f"NPC INT {npc_int} (roll {npc_roll}) -> {result}. "
            f"Stats: {status}"
        )

    def _decorate_with_memory_tone(self, response: str, memory: dict[str, Any]) -> str:
        favorability = int(memory.get("favorability", 2))
        if favorability <= 1:
            return f"(Tense tone) {response}"
        if favorability >= 3:
            return f"(Friendly tone) {response}"
        return response

    def _run_npc_vibe_check(self, npc_id: str, description: str) -> str:
        node = self.current_node()
        if npc_id not in node.get("npcs", []):
            return f"NPC '{npc_id}' is not in this location."
        npc = self.world.get("npcs", {}).get(npc_id)
        if not npc:
            return f"NPC '{npc_id}' not found."

        memory = self._npc_memory(npc_id, npc)
        before = int(memory.get("favorability", 2))
        player_vibes = self._player_stats().get("vibes", 1)
        npc_vibes = self._normalize_stats(npc.get("stats", {}), fallback=DEFAULT_PLAYER_STATS).get("vibes", 1)
        npc_roll = random.randint(1, 6)
        npc_success = npc_roll <= npc_vibes

        modifier = 0
        modifier_reason = "none"
        if npc_vibes >= 4 and npc_success:
            modifier = 1
            modifier_reason = "NPC support boost"
        elif npc_vibes <= 2 and not npc_success:
            modifier = -1
            modifier_reason = "NPC bad mood penalty"

        effective_vibes = max(1, min(6, player_vibes + modifier))
        player_roll = random.randint(1, 6)

        if player_roll == 1:
            outcome = "Critical Success"
            delta = 1
        elif effective_vibes >= 6:
            outcome = "Success"
            delta = 1
        elif player_roll <= effective_vibes:
            outcome = "Success"
            delta = 1
        else:
            outcome = "Failed"
            delta = -1

        after = max(1, min(3, before + delta))
        memory["favorability"] = after
        if outcome in {"Critical Success", "Success"}:
            memory["favorability_visible"] = True
        return (
            f"Vibe Check: {description}\n"
            f"NPC modifier roll: Vibes {npc_vibes} (roll {npc_roll}) -> "
            f"{'success' if npc_success else 'fail'}, modifier {modifier:+d} ({modifier_reason})\n"
            f"Player Vibes: base {player_vibes}, effective {effective_vibes}, roll {player_roll} -> {outcome}\n"
            f"Favorability: {before} -> {after}"
        )

    def _npc_stats_unlock_help(self, npc_id: str, npc: dict[str, Any]) -> str:
        name = self._npc_name(npc, npc_id)
        return (
            f"Stats for '{name}' are locked.\n"
            "Unlock options:\n"
            "- Progress adventure unlock conditions (node/choice unlock keys).\n"
            "- Use a talk interaction configured with intelligence unlock logic.\n"
            "- If your first intelligence unlock attempt fails, raise favorability to 3 and try again."
        )

    def _normalize_stats(self, raw_stats: Any, fallback: dict[str, int]) -> dict[str, int]:
        base = dict(fallback)
        if isinstance(raw_stats, dict):
            for key, value in raw_stats.items():
                normalized = STAT_ALIASES.get(str(key).lower())
                if not normalized:
                    continue
                try:
                    number = int(value)
                except (TypeError, ValueError):
                    continue
                base[normalized] = min(6, max(1, number))
        return base

    def _run_stat_check(
        self,
        stat_name: str,
        description: str,
        subject_stats: dict[str, int],
    ) -> dict[str, str]:
        normalized = STAT_ALIASES.get(stat_name.lower())
        if not normalized:
            allowed = ", ".join(STAT_LABELS.keys())
            return {
                "result": "invalid",
                "message": f"Unknown stat '{stat_name}'. Use one of: {allowed}",
            }

        stat_value = subject_stats[normalized]
        roll = random.randint(1, 6)
        if roll == 1:
            outcome = "Critical Success"
            result_key = "critical"
        elif roll <= stat_value:
            outcome = "Success"
            result_key = "success"
        else:
            outcome = "Failed"
            result_key = "fail"

        message = (
            f"Check: {description}\n"
            f"Stat: {STAT_LABELS[normalized]} ({stat_value}) | D6 Roll: {roll}\n"
            f"Outcome: {outcome}"
        )
        return {"result": result_key, "message": message}

    def _autosave_if_enabled(self) -> str:
        config = self.saves.read_player_config()
        if not bool(config.get("autosave_enabled", False)):
            return ""
        slot = str(config.get("autosave_slot", "autosave"))
        self.saves.save_state(self.state, slot)
        if not bool(config.get("autosave_notify_enabled", True)):
            return ""
        return f"[Autosave] Saved to slot '{slot}'."

    def _format_stats_block(self, title: str, stats: dict[str, int]) -> str:
        lines = [f"{title} (1-6, 6 best):"]
        for key in ["intelligence", "vibes", "physique", "luck"]:
            lines.append(f"- {STAT_LABELS[key]}: {stats[key]} -> {STAT_DESCRIPTIONS[key]}")
        return "\n".join(lines)

    def _log_missing_action(self, command: str, reason: str) -> None:
        username = os.environ.get("USERNAME", "player")
        adventure = self.state.adventure_id or "no-adventure"
        log_dir: Path = self.saves.player_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{username}-{adventure}-MissingAction.log"
        timestamp = datetime.now(timezone.utc).isoformat()
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{timestamp} | reason={reason} | command={command}\n")
