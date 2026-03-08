from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from engine.exceptions import ValidationError
from engine.loader import ContentLoader
from engine.scanner import AdventureScanner


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_loader_rejects_unknown_location_reference(tmp_path: Path) -> None:
    world = tmp_path / "world"
    _write_yaml(world / "locations" / "seed.yaml", {"locations": [{"id": "known_loc"}]})
    _write_yaml(world / "items" / "seed.yaml", {"items": []})
    _write_yaml(world / "npcs" / "seed.yaml", {"npcs": []})
    _write_yaml(world / "objects" / "seed.yaml", {"objects": []})
    _write_yaml(world / "events" / "seed.yaml", {"events": []})
    _write_yaml(world / "calendar" / "seed.yaml", {"holidays": []})

    adv = tmp_path / "adventures" / "sam" / "bad-ref"
    _write_yaml(
        adv / "manifest.yaml",
        {
            "id": "bad-ref",
            "name": "Bad Ref",
            "creator": "sam",
            "description": "invalid",
            "start_node": "intro",
            "content": {"story_file": "code/story.yaml"},
        },
    )
    _write_yaml(
        adv / "code" / "story.yaml",
        {
            "nodes": {
                "intro": {
                    "location_id": "unknown_loc",
                    "text": "Oops",
                    "choices": [],
                }
            }
        },
    )

    scanner = AdventureScanner(tmp_path / "adventures")
    descriptor = scanner.get_by_key("sam/bad-ref")
    assert descriptor is not None

    loader = ContentLoader(world_root=world)
    loaded_world = loader.load_world()
    with pytest.raises(ValidationError):
        loader.load_adventure(descriptor, loaded_world)


def test_loader_rejects_invalid_event_date(tmp_path: Path) -> None:
    world = tmp_path / "world"
    _write_yaml(world / "locations" / "seed.yaml", {"locations": [{"id": "known_loc"}]})
    _write_yaml(world / "items" / "seed.yaml", {"items": []})
    _write_yaml(world / "npcs" / "seed.yaml", {"npcs": []})
    _write_yaml(world / "objects" / "seed.yaml", {"objects": []})
    _write_yaml(
        world / "events" / "seed.yaml",
        {
            "events": [
                {
                    "id": "bad_event",
                    "name": "Bad",
                    "start_date": "2026-13-40",
                    "description": "bad date",
                }
            ]
        },
    )
    _write_yaml(world / "calendar" / "seed.yaml", {"holidays": []})

    loader = ContentLoader(world_root=world)
    with pytest.raises(ValidationError):
        loader.load_world()


def test_loader_rejects_adventure_event_without_day_or_date(tmp_path: Path) -> None:
    world = tmp_path / "world"
    _write_yaml(world / "locations" / "seed.yaml", {"locations": [{"id": "known_loc"}]})
    _write_yaml(world / "items" / "seed.yaml", {"items": []})
    _write_yaml(world / "npcs" / "seed.yaml", {"npcs": []})
    _write_yaml(world / "objects" / "seed.yaml", {"objects": []})
    _write_yaml(world / "events" / "seed.yaml", {"events": []})
    _write_yaml(world / "calendar" / "seed.yaml", {"holidays": []})

    adv = tmp_path / "adventures" / "sam" / "bad-event"
    _write_yaml(
        adv / "manifest.yaml",
        {
            "id": "bad-event",
            "name": "Bad Event",
            "creator": "sam",
            "description": "invalid",
            "start_node": "intro",
            "content": {"story_file": "code/story.yaml"},
        },
    )
    _write_yaml(
        adv / "code" / "story.yaml",
        {
            "events": [
                {
                    "id": "janet_new_car",
                    "name": "Janet got a new car",
                    "description": "missing day/date",
                }
            ],
            "nodes": {
                "intro": {
                    "location_id": "known_loc",
                    "text": "Hello",
                    "choices": [],
                }
            },
        },
    )

    scanner = AdventureScanner(tmp_path / "adventures")
    descriptor = scanner.get_by_key("sam/bad-event")
    assert descriptor is not None

    loader = ContentLoader(world_root=world)
    loaded_world = loader.load_world()
    with pytest.raises(ValidationError):
        loader.load_adventure(descriptor, loaded_world)
