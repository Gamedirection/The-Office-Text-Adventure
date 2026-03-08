"""Game state dataclasses and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GameState:
    """Serializable state for a running adventure session."""

    creator: str = ""
    adventure_id: str = ""
    current_node: str = ""
    inventory: list[str] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    last_output: str = ""

    def adventure_key(self) -> str:
        return f"{self.creator}/{self.adventure_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "creator": self.creator,
            "adventure_id": self.adventure_id,
            "current_node": self.current_node,
            "inventory": list(self.inventory),
            "flags": dict(self.flags),
            "last_output": self.last_output,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "GameState":
        return cls(
            creator=str(payload.get("creator", "")),
            adventure_id=str(payload.get("adventure_id", "")),
            current_node=str(payload.get("current_node", "")),
            inventory=list(payload.get("inventory", [])),
            flags=dict(payload.get("flags", {})),
            last_output=str(payload.get("last_output", "")),
        )
