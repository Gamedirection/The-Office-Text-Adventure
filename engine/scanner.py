"""Adventure discovery scanner for adventures/<creator>/<adventure>."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_MANIFEST_KEYS = {"id", "name", "creator", "description", "start_node", "content"}


@dataclass
class AdventureDescriptor:
    """Metadata for one discovered adventure."""

    creator: str
    adventure_name: str
    path: Path
    manifest_path: Path
    valid: bool
    error: str | None = None
    manifest: dict[str, Any] | None = None

    @property
    def key(self) -> str:
        return f"{self.creator}/{self.adventure_name}"


class AdventureScanner:
    """Scans filesystem adventure folders and validates manifests."""

    def __init__(self, adventures_root: str | Path = "adventures") -> None:
        self.adventures_root = Path(adventures_root)

    def discover_adventures(self) -> list[AdventureDescriptor]:
        results: list[AdventureDescriptor] = []
        if not self.adventures_root.exists():
            return results

        for creator_dir in sorted(self.adventures_root.iterdir()):
            if not creator_dir.is_dir():
                continue
            for adv_dir in sorted(creator_dir.iterdir()):
                if not adv_dir.is_dir():
                    continue
                results.append(self._build_descriptor(creator_dir.name, adv_dir))
        return results

    def valid_adventures(self) -> list[AdventureDescriptor]:
        return [d for d in self.discover_adventures() if d.valid]

    def get_by_key(self, key: str) -> AdventureDescriptor | None:
        for descriptor in self.discover_adventures():
            if descriptor.key == key and descriptor.valid:
                return descriptor
        return None

    def _build_descriptor(self, creator: str, adv_dir: Path) -> AdventureDescriptor:
        manifest_path = adv_dir / "manifest.yaml"
        if not manifest_path.exists():
            return AdventureDescriptor(
                creator=creator,
                adventure_name=adv_dir.name,
                path=adv_dir,
                manifest_path=manifest_path,
                valid=False,
                error="Missing manifest.yaml",
            )

        try:
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            return AdventureDescriptor(
                creator=creator,
                adventure_name=adv_dir.name,
                path=adv_dir,
                manifest_path=manifest_path,
                valid=False,
                error=f"Manifest parse error: {exc}",
            )

        missing = sorted(REQUIRED_MANIFEST_KEYS - set(manifest.keys()))
        if missing:
            return AdventureDescriptor(
                creator=creator,
                adventure_name=adv_dir.name,
                path=adv_dir,
                manifest_path=manifest_path,
                valid=False,
                error=f"Missing manifest keys: {', '.join(missing)}",
                manifest=manifest,
            )

        return AdventureDescriptor(
            creator=creator,
            adventure_name=adv_dir.name,
            path=adv_dir,
            manifest_path=manifest_path,
            valid=True,
            manifest=manifest,
        )
