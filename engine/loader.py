"""Content loader and validator for world/adventures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from engine.exceptions import ValidationError
from engine.scanner import AdventureDescriptor


@dataclass
class LoadedAdventure:
    """Fully loaded adventure package."""

    descriptor: AdventureDescriptor
    story_nodes: dict[str, dict[str, Any]]


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
        }
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
        if not isinstance(nodes, dict) or not nodes:
            raise ValidationError(f"Adventure '{descriptor.key}' has no story nodes")

        start_node = descriptor.manifest.get("start_node")
        if start_node not in nodes:
            raise ValidationError(
                f"Adventure '{descriptor.key}' start_node '{start_node}' does not exist"
            )

        self._validate_story_references(descriptor, nodes, world)
        return LoadedAdventure(descriptor=descriptor, story_nodes=nodes)

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
