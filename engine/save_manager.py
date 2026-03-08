"""Save/config handling for .player folder."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from engine.state import GameState


class SaveManager:
    """Reads and writes player config and save slots."""

    def __init__(self, player_root: str | Path = ".player") -> None:
        self.player_root = Path(player_root)
        self.config_path = self.player_root / "config" / "player.yaml"
        self.saves_root = self.player_root / "saves"
        self.journal_root = self.player_root / "journal"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.saves_root.mkdir(parents=True, exist_ok=True)
        self.journal_root.mkdir(parents=True, exist_ok=True)

    def read_player_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}

    def write_player_config(self, payload: dict[str, Any]) -> None:
        self.config_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def save_state(self, state: GameState, slot: str) -> Path:
        adv_dir = self.saves_root / state.creator / state.adventure_id
        adv_dir.mkdir(parents=True, exist_ok=True)
        save_path = adv_dir / f"{slot}.yaml"
        save_path.write_text(yaml.safe_dump(state.to_dict(), sort_keys=False), encoding="utf-8")

        config = self.read_player_config()
        config.setdefault("last_session", {})
        config["last_session"] = {
            "creator": state.creator,
            "adventure_id": state.adventure_id,
            "slot": slot,
        }
        self.write_player_config(config)
        return save_path

    def load_state(self, creator: str, adventure_id: str, slot: str) -> GameState:
        save_path = self.saves_root / creator / adventure_id / f"{slot}.yaml"
        payload = yaml.safe_load(save_path.read_text(encoding="utf-8")) or {}
        return GameState.from_dict(payload)

    def list_slots(self, creator: str, adventure_id: str) -> list[str]:
        folder = self.saves_root / creator / adventure_id
        if not folder.exists():
            return []
        return sorted(path.stem for path in folder.glob("*.yaml"))

    def load_last_session(self) -> tuple[GameState | None, str]:
        config = self.read_player_config()
        session = config.get("last_session") or {}
        creator = session.get("creator")
        adventure_id = session.get("adventure_id")
        slot = session.get("slot")
        if not (creator and adventure_id and slot):
            return None, "No last session found."

        save_path = self.saves_root / creator / adventure_id / f"{slot}.yaml"
        if not save_path.exists():
            return None, "Last session points to a missing save file."

        payload = yaml.safe_load(save_path.read_text(encoding="utf-8")) or {}
        return GameState.from_dict(payload), f"Loaded last session: {creator}/{adventure_id} ({slot})"

    def list_journal_pages(self, creator: str, adventure_id: str) -> list[dict[str, Any]]:
        journal_path = self._journal_path(creator, adventure_id)
        if not journal_path.exists():
            return []
        payload = yaml.safe_load(journal_path.read_text(encoding="utf-8")) or {}
        pages = payload.get("pages", [])
        if not isinstance(pages, list):
            return []
        return pages

    def append_journal_page(
        self,
        creator: str,
        adventure_id: str,
        node_id: str,
        location_id: str,
        text: str,
    ) -> int:
        pages = self.list_journal_pages(creator, adventure_id)
        page_number = len(pages) + 1
        pages.append(
            {
                "page": page_number,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "node_id": node_id,
                "location_id": location_id,
                "text": text,
            }
        )

        journal_path = self._journal_path(creator, adventure_id)
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            yaml.safe_dump({"pages": pages}, sort_keys=False),
            encoding="utf-8",
        )
        return page_number

    def remove_journal_page(self, creator: str, adventure_id: str, page_number: int) -> bool:
        pages = self.list_journal_pages(creator, adventure_id)
        kept = [p for p in pages if int(p.get("page", 0)) != page_number]
        if len(kept) == len(pages):
            return False

        # Renumber pages so list/read remain simple after removals.
        for idx, page in enumerate(kept, start=1):
            page["page"] = idx

        journal_path = self._journal_path(creator, adventure_id)
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(
            yaml.safe_dump({"pages": kept}, sort_keys=False),
            encoding="utf-8",
        )
        return True

    def _journal_path(self, creator: str, adventure_id: str) -> Path:
        return self.journal_root / creator / f"{adventure_id}.yaml"
