from __future__ import annotations

from pathlib import Path

from engine.ai import AIAdapter
from engine.game_engine import GameEngine
from engine.scanner import AdventureScanner


class FailingAdapter(AIAdapter):
    def generate_reply(self, context: dict[str, object]) -> str:
        raise RuntimeError("provider unavailable")


class FixedAdapter(AIAdapter):
    def generate_reply(self, context: dict[str, object]) -> str:
        return "AI reply"


class CaptureAdapter(AIAdapter):
    def __init__(self) -> None:
        self.context: dict[str, object] = {}

    def generate_reply(self, context: dict[str, object]) -> str:
        self.context = context
        return "captured"


def _key_for_creator(creator: str) -> str:
    scanner = AdventureScanner("adventures")
    for descriptor in scanner.valid_adventures():
        if descriptor.creator.lower() == creator.lower():
            return descriptor.key
    raise AssertionError(f"No valid adventure found for creator '{creator}'")


def test_manual_and_ai_and_hybrid_modes(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"

    engine_ai = GameEngine(player_root=player_root, ai_adapter=FixedAdapter())
    engine_ai.start(_key_for_creator("jon"))
    ai_reply = engine_ai.execute_command("talk it_owen brainstorm")
    assert ai_reply == "AI reply"

    engine_manual = GameEngine(player_root=player_root)
    engine_manual.start(_key_for_creator("alex"))
    manual_reply = engine_manual.execute_command("talk manager_mina greet")
    assert "Morning team" in manual_reply

    engine_hybrid = GameEngine(player_root=player_root, ai_adapter=FailingAdapter())
    engine_hybrid.start(_key_for_creator("alex"))
    hybrid_reply = engine_hybrid.execute_command("talk manager_mina coaching")
    assert "Take a breath" in hybrid_reply


def test_ai_context_includes_profile_and_prompt_append(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    adapter = CaptureAdapter()
    engine = GameEngine(player_root=player_root, ai_adapter=adapter)
    engine.start(_key_for_creator("jon"))

    reply = engine.execute_command("talk it_owen brainstorm")
    assert reply == "captured"
    assert adapter.context.get("npc_name") == "Owen (IT)"
    assert adapter.context.get("npc_role") == "IT Support"

    profile = adapter.context.get("npc_profile")
    assert isinstance(profile, dict)
    assert profile.get("personality")
    assert profile.get("appearance")
    assert profile.get("tone")
    assert profile.get("backstory")
    assert profile.get("age") == 31

    prompt_append = str(adapter.context.get("prompt_append", ""))
    assert "Explain technical points in plain language" in prompt_append
    assert "Suggest a hypothesis and a quick validation step" in prompt_append
