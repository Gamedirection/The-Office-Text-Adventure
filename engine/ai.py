"""AI adapter interfaces for NPC dialog."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIAdapter(ABC):
    """Contract for AI providers used by NPC interactions."""

    @abstractmethod
    def generate_reply(self, context: dict[str, Any]) -> str:
        """Generate an NPC response from context."""


class MockAIAdapter(AIAdapter):
    """Local no-key adapter used for template development and tests."""

    def generate_reply(self, context: dict[str, Any]) -> str:
        npc_name = context.get("npc_name", "NPC")
        adventure = context.get("adventure_id", "unknown-adventure")
        player_action = context.get("player_action", "talk")
        return (
            f"[MOCK-AI] {npc_name} responds to '{player_action}' "
            f"in adventure '{adventure}'."
        )
