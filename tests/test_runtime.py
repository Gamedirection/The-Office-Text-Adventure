from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from engine.game_engine import GameEngine
from engine.scanner import AdventureScanner


def _key_for_creator(creator: str) -> str:
    scanner = AdventureScanner("adventures")
    for descriptor in scanner.valid_adventures():
        if descriptor.creator.lower() == creator.lower():
            return descriptor.key
    raise AssertionError(f"No valid adventure found for creator '{creator}'")


def test_runtime_start_choose_save_load(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)

    output = engine.start(_key_for_creator("alex"))
    assert "Standup starts" in output

    choose_output = engine.execute_command("choose prep_board")
    assert "You find a deploy checklist" in choose_output

    save_output = engine.execute_command("save slot1")
    assert "Saved to" in save_output

    load_output = engine.execute_command("load slot1")
    assert "Loaded save slot 'slot1'" in load_output

    inv = engine.execute_command("inventory")
    assert "deploy_checklist" in inv

    help_output = engine.execute_command("help")
    assert "=== Interact ===" in help_output
    assert "=== Player ===" in help_output
    assert "=== Game ===" in help_output
    assert "inspect <item_or_object_id | npc_id stats>" in help_output


def test_runtime_list_saves_and_move(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)
    engine.start(_key_for_creator("alex"))

    no_saves = engine.execute_command("saves")
    assert "No save slots found" in no_saves

    engine.execute_command("save slotA")
    listed = engine.execute_command("list-saves")
    assert "slotA" in listed

    move_ok = engine.execute_command("move meeting_room")
    assert "Moved to meeting_room" in move_ok
    assert "meeting_start" in move_ok

    move_fail = engine.execute_command("move lobby")
    assert "cannot move directly" in move_fail


def test_choose_preview_and_journal_commands(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)
    engine.start(_key_for_creator("dylon"))

    choose_preview = engine.execute_command("choose")
    assert "Usage: choose <choice_id>" in choose_preview
    assert "choose review_plan" in choose_preview
    assert "choose fast_track" in choose_preview

    empty_journal = engine.execute_command("journal list")
    assert "Journal is empty." in empty_journal

    added = engine.execute_command("journal add Check dependencies before release window.")
    assert "Added journal page 1." in added

    listed = engine.execute_command("journal list")
    assert "1: Check dependencies before release window." in listed

    read_page = engine.execute_command("journal read 1")
    assert "Journal Page 1" in read_page
    assert "Check dependencies before release window." in read_page

    removed = engine.execute_command("journal remove 1")
    assert "Removed journal page 1." in removed

    missing = engine.execute_command("journal read 1")
    assert "not found" in missing


def test_default_no_option_messages(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)
    engine.start(_key_for_creator("alex"))
    engine.execute_command("choose prep_board")
    engine.execute_command("choose join_late")
    engine.execute_command("choose present_risk")

    assert engine.execute_command("choose") == "Nothing to choose right now"
    assert engine.execute_command("talk") == "No one to talk to right now"
    assert engine.execute_command("inspect") == "No items to inspect right now"

    # Force no movement options at this location to verify fallback messaging.
    node = engine.current_node()
    location_id = node.get("location_id")
    if location_id:
        engine.world["locations"][location_id]["connections"] = []
    assert engine.execute_command("move") == "No place to move right now"


def test_stats_and_check_commands(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)
    engine.start(_key_for_creator("jon"))

    stats_output = engine.execute_command("stats")
    assert "Player stats (1-6, 6 best):" in stats_output
    assert "Intelligence" in stats_output
    assert "Vibes" in stats_output
    assert "Physique" in stats_output
    assert "Luck" in stats_output

    locked_stats = engine.execute_command("stats npc it_owen")
    assert "are locked" in locked_stats

    # Explicitly unlock in test state to verify formatting/output behavior.
    engine.state.flags.setdefault("npc_stats_unlocked", {})["it_owen"] = True
    npc_stats_output = engine.execute_command("stats npc it_owen")
    assert "Owen (IT) stats" in npc_stats_output
    assert "Intelligence: 5" in npc_stats_output

    npc_inspect_stats = engine.execute_command("inspect it_owen stats")
    assert "Owen (IT) stats" in npc_inspect_stats
    assert "Vibes: 3" in npc_inspect_stats

    with patch("engine.game_engine.random.randint", return_value=1):
        critical = engine.execute_command("check vibes Try to calm a tense outage room")
    assert "Outcome: Critical Success" in critical
    assert "Stat: Vibes" in critical

    with patch("engine.game_engine.random.randint", return_value=6):
        failed = engine.execute_command("check physique Carry heavy equipment quickly")
    assert "Outcome: Failed" in failed

    with patch("engine.game_engine.random.randint", return_value=2):
        shorthand = engine.execute_command("check i Solve a debugging puzzle")
    assert "Stat: Intelligence" in shorthand


def test_player_name_and_npc_favorability_memory(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)
    engine.start(_key_for_creator("alex"))

    set_name = engine.execute_command("name Sam")
    assert "Player name set to: Sam" in set_name
    show_name = engine.execute_command("name")
    assert "Player name: Sam" in show_name

    dismissive = engine.execute_command("talk manager_mina dismissive")
    assert "dismissive" in dismissive
    low_response = engine.execute_command("talk manager_mina greet")
    assert "direct updates only" in low_response

    engine.state.flags.setdefault("npc_stats_unlocked", {})["manager_mina"] = True
    npc_stats = engine.execute_command("stats npc manager_mina")
    assert "Favorability: 1" in npc_stats


def test_available_now_hint_and_autosave(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    config_dir = player_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "player.yaml").write_text(
        yaml.safe_dump(
            {
                "autosave_enabled": True,
                "autosave_slot": "auto1",
                "player_stats": {
                    "intelligence": 3,
                    "vibes": 3,
                    "physique": 3,
                    "luck": 3,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    engine = GameEngine(player_root=player_root)
    output = engine.start(_key_for_creator("alex"))
    assert "Available now:" not in output

    choose_help = engine.execute_command("choose")
    assert "Available now:" in choose_help
    talk_help = engine.execute_command("talk")
    assert "Available now:" in talk_help
    inspect_help = engine.execute_command("inspect")
    assert "Available now:" in inspect_help
    move_help = engine.execute_command("move")
    assert "Available now:" in move_help

    moved = engine.execute_command("move meeting_room")
    assert "[Autosave] Saved to slot 'auto1'." in moved

    slots = engine.execute_command("saves")
    assert "auto1" in slots

    disabled = engine.execute_command("settings autosave off")
    assert "Autosave disabled." in disabled
    disabled_cfg = engine.saves.read_player_config()
    assert disabled_cfg.get("autosave_enabled") is False

    enabled = engine.execute_command("settings autosave on")
    assert "Autosave enabled." in enabled
    enabled_cfg = engine.saves.read_player_config()
    assert enabled_cfg.get("autosave_enabled") is True

    notify_off = engine.execute_command("settings autosave-notify off")
    assert "Autosave notification disabled." in notify_off
    notify_off_cfg = engine.saves.read_player_config()
    assert notify_off_cfg.get("autosave_notify_enabled") is False

    moved_silent = engine.execute_command("goto meeting_room")
    assert "[Autosave]" not in moved_silent

    notify_on = engine.execute_command("settings autosave-notify on")
    assert "Autosave notification enabled." in notify_on
    notify_on_cfg = engine.saves.read_player_config()
    assert notify_on_cfg.get("autosave_notify_enabled") is True


def test_missing_action_log_written_for_unconfigured_inspect(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USERNAME", "TestUser")
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)
    engine.start(_key_for_creator("alex"))

    response = engine.execute_command("inspect sprint_board progress")
    assert response == "No outcome configured for action: inspect sprint_board progress"

    log_path = player_root / "logs" / f"TestUser-{engine.state.adventure_id}-MissingAction.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "reason=no_outcome_configured" in content
    assert "command=inspect sprint_board progress" in content


def test_npc_stats_unlock_via_intelligence_check_interaction(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)
    engine.start(_key_for_creator("jon"))

    locked = engine.execute_command("stats npc it_owen")
    assert "are locked" in locked

    with patch("engine.game_engine.random.randint", side_effect=[1, 6]):
        check_output = engine.execute_command("talk it_owen profile_check")
    assert "NPC Intelligence Check (Owen (IT))" in check_output
    assert "Stats: UNLOCKED" in check_output

    unlocked = engine.execute_command("stats npc it_owen")
    assert "Owen (IT) stats" in unlocked


def test_npc_unlock_check_single_attempt_then_favorability_gate(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)
    engine.start(_key_for_creator("jon"))

    # First attempt fails.
    with patch("engine.game_engine.random.randint", side_effect=[6, 1]):
        first = engine.execute_command("talk it_owen profile_check")
    assert "Stats: LOCKED" in first

    # Second attempt blocked until favorability reaches 3.
    with patch("engine.game_engine.random.randint", side_effect=[1, 1]):
        blocked = engine.execute_command("talk it_owen profile_check")
    assert "already attempted" in blocked
    assert "favorability to 3" in blocked

    # Raise favorability manually in test and retry.
    memory = engine.state.flags.setdefault("npc_memories", {}).setdefault("it_owen", {})
    memory["favorability"] = 3
    with patch("engine.game_engine.random.randint", side_effect=[2, 6]):
        retry = engine.execute_command("talk it_owen profile_check")
    assert "Stats: UNLOCKED" in retry


def test_inspect_npc_help_and_vibe_check_shows_favorability(tmp_path: Path) -> None:
    player_root = tmp_path / ".player"
    engine = GameEngine(player_root=player_root)
    engine.start(_key_for_creator("jon"))

    inspect_msg = engine.execute_command("inspect qa_riley")
    assert "not visible here" in inspect_msg
    assert "Unlock options:" in inspect_msg

    hidden = engine.execute_command("inspect it_owen favorability")
    assert "is hidden" in hidden

    with patch("engine.game_engine.random.randint", side_effect=[6, 1]):
        vibe = engine.execute_command("check vibes it_owen Build trust during triage")
    assert "Vibe Check: Build trust during triage" in vibe
    assert "Favorability: 2 -> 3" in vibe

    visible = engine.execute_command("inspect it_owen favorability")
    assert "Favorability for 'Owen (IT)': 3" in visible

    locked_stats_with_favorability = engine.execute_command("stats npc it_owen")
    assert "are locked" in locked_stats_with_favorability
    assert "Favorability: 3" in locked_stats_with_favorability
