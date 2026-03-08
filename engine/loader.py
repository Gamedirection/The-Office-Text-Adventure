"""Content loader and validator for world/adventures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from engine.calendar import parse_iso_date
from engine.exceptions import ValidationError
from engine.scanner import AdventureDescriptor

ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


@dataclass
class LoadedAdventure:
    """Fully loaded adventure package."""

    descriptor: AdventureDescriptor
    story_nodes: dict[str, dict[str, Any]]
    events: list[dict[str, Any]]


class ContentLoader:
    """Loads world and adventure YAML, and validates cross references."""

    def __init__(self, world_root: str | Path = "world") -> None:
        self.world_root = Path(world_root)

    def load_world(self) -> dict[str, dict[str, dict[str, Any]]]:
        world = {
            "locations": self._load_entity_folder(self.world_root / "locations", "locations"),
            "items": self._load_entity_folder(self.world_root / "items", "items"),
            "npcs": self._load_entity_folder(self.world_root / "npcs", "npcs"),
            "objects": self._load_entity_folder(self.world_root / "objects", "objects"),
            "events": self._load_entity_folder(self.world_root / "events", "events"),
            "holidays": self._load_entity_folder(self.world_root / "calendar", "holidays"),
        }
        self._validate_calendar_entities(world)
        return world

    def load_adventure(self, descriptor: AdventureDescriptor, world: dict[str, Any]) -> LoadedAdventure:
        if not descriptor.valid or not descriptor.manifest:
            raise ValidationError(f"Adventure '{descriptor.key}' is invalid: {descriptor.error}")

        content = descriptor.manifest.get("content", {})
        story_rel = content.get("story_file")
        if not story_rel:
            raise ValidationError(f"Adventure '{descriptor.key}' missing content.story_file")

        story_path = descriptor.path / str(story_rel)
        if not story_path.exists():
            raise ValidationError(f"Adventure '{descriptor.key}' story file not found: {story_path}")

        story_data = yaml.safe_load(story_path.read_text(encoding="utf-8")) or {}
        nodes = story_data.get("nodes", {})
        events = story_data.get("events", [])
        if not isinstance(nodes, dict) or not nodes:
            raise ValidationError(f"Adventure '{descriptor.key}' has no story nodes")
        if not isinstance(events, list):
            raise ValidationError(f"Adventure '{descriptor.key}' expected 'events' to be a list")

        start_node = descriptor.manifest.get("start_node")
        if start_node not in nodes:
            raise ValidationError(
                f"Adventure '{descriptor.key}' start_node '{start_node}' does not exist"
            )

        self._validate_story_references(descriptor, nodes, world)
        self._validate_adventure_events(descriptor, events)
        return LoadedAdventure(descriptor=descriptor, story_nodes=nodes, events=events)

    def _load_entity_folder(self, folder: Path, list_key: str) -> dict[str, dict[str, Any]]:
        entities: dict[str, dict[str, Any]] = {}
        if not folder.exists():
            return entities

        for file in sorted(folder.glob("*.yaml")):
            payload = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
            rows = payload.get(list_key, [])
            if not isinstance(rows, list):
                raise ValidationError(f"{file}: expected '{list_key}' to be a list")
            for row in rows:
                entity_id = row.get("id")
                if not entity_id:
                    raise ValidationError(f"{file}: entity missing required 'id'")
                if entity_id in entities:
                    raise ValidationError(f"{file}: duplicate entity id '{entity_id}'")
                entities[entity_id] = row
        return entities

    def _validate_story_references(
        self,
        descriptor: AdventureDescriptor,
        nodes: dict[str, dict[str, Any]],
        world: dict[str, dict[str, dict[str, Any]]],
    ) -> None:
        for node_id, node in nodes.items():
            location_id = node.get("location_id")
            if location_id and location_id not in world["locations"]:
                raise ValidationError(
                    f"{descriptor.key} node '{node_id}' references unknown location '{location_id}'"
                )

            for npc_id in node.get("npcs", []):
                if npc_id not in world["npcs"]:
                    raise ValidationError(
                        f"{descriptor.key} node '{node_id}' references unknown npc '{npc_id}'"
                    )

            for item_id in node.get("items", []):
                if item_id not in world["items"]:
                    raise ValidationError(
                        f"{descriptor.key} node '{node_id}' references unknown item '{item_id}'"
                    )

            for obj_id in node.get("objects", []):
                if obj_id not in world["objects"]:
                    raise ValidationError(
                        f"{descriptor.key} node '{node_id}' references unknown object '{obj_id}'"
                    )

            for choice in node.get("choices", []):
                next_node = choice.get("next_node")
                if next_node and next_node not in nodes:
                    raise ValidationError(
                        f"{descriptor.key} node '{node_id}' choice references unknown next node '{next_node}'"
                    )

    def _validate_calendar_entities(self, world: dict[str, dict[str, dict[str, Any]]]) -> None:
        for event_id, event in world.get("events", {}).items():
            self._validate_simple_id(event_id, kind="event")
            start_raw = event.get("start_date")
            if not start_raw:
                raise ValidationError(f"event '{event_id}' missing required 'start_date'")
            start = parse_iso_date(str(start_raw), field_name=f"event '{event_id}' start_date")
            end_raw = event.get("end_date") or start_raw
            end = parse_iso_date(str(end_raw), field_name=f"event '{event_id}' end_date")
            if end < start:
                raise ValidationError(f"event '{event_id}' has end_date before start_date")

        for holiday_id, holiday in world.get("holidays", {}).items():
            self._validate_simple_id(holiday_id, kind="holiday")
            date_raw = holiday.get("date")
            if not date_raw:
                raise ValidationError(f"holiday '{holiday_id}' missing required 'date'")
            parse_iso_date(str(date_raw), field_name=f"holiday '{holiday_id}' date")

    def _validate_simple_id(self, entity_id: str, kind: str) -> None:
        if not ID_PATTERN.match(entity_id):
            raise ValidationError(
                f"{kind} id '{entity_id}' is invalid. Use lowercase letters, numbers, and underscores."
            )

    def _validate_adventure_events(
        self,
        descriptor: AdventureDescriptor,
        events: list[dict[str, Any]],
    ) -> None:
        seen: set[str] = set()
        for event in events:
            event_id = str(event.get("id", ""))
            if not event_id:
                raise ValidationError(f"{descriptor.key} adventure event missing required 'id'")
            self._validate_simple_id(event_id, kind="adventure event")
            if event_id in seen:
                raise ValidationError(f"{descriptor.key} duplicate adventure event id '{event_id}'")
            seen.add(event_id)

            if not event.get("name"):
                raise ValidationError(f"{descriptor.key} adventure event '{event_id}' missing 'name'")
            if not event.get("description"):
                raise ValidationError(
                    f"{descriptor.key} adventure event '{event_id}' missing 'description'"
                )

            absolute_date = event.get("date")
            day_offset = event.get("day_offset")
            if absolute_date:
                parse_iso_date(
                    str(absolute_date),
                    field_name=f"{descriptor.key} event '{event_id}' date",
                )
                continue

            if day_offset is None:
                raise ValidationError(
                    f"{descriptor.key} event '{event_id}' requires 'day_offset' when 'date' is not set"
                )
            try:
                offset = int(day_offset)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    f"{descriptor.key} event '{event_id}' has invalid day_offset '{day_offset}'"
                ) from exc
            if offset < 0:
                raise ValidationError(
                    f"{descriptor.key} event '{event_id}' day_offset must be >= 0"
                )
