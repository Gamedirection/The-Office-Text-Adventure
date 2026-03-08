from __future__ import annotations

from pathlib import Path

import yaml

from engine.scanner import AdventureScanner


def test_discovery_finds_seed_adventures() -> None:
    scanner = AdventureScanner("adventures")
    found = scanner.discover_adventures()
    valid = [d for d in found if d.valid]

    creators = {d.creator for d in valid}
    assert "alex" in creators
    assert "jon" in creators
    assert "dylon" in creators


def test_discovery_reports_invalid_manifest(tmp_path: Path) -> None:
    adventures = tmp_path / "adventures"
    broken = adventures / "sam" / "broken-adventure"
    broken.mkdir(parents=True)
    (broken / "manifest.yaml").write_text(yaml.safe_dump({"id": "broken"}), encoding="utf-8")

    scanner = AdventureScanner(adventures)
    found = scanner.discover_adventures()
    assert len(found) == 1
    assert found[0].valid is False
    assert "Missing manifest keys" in (found[0].error or "")
