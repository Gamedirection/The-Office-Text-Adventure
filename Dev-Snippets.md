# Dev Snippets

See [Code-Snippets.md](Code-Snippets.md) for the full snippet catalog.

## NPC favorability + memory effect

```yaml
effects:
  favorability_delta: -1
  memory_tag: "player_was_dismissive"
```

## Set player name

```text
name Alex
```

## Reveal favorability (without full stat unlock)

```text
check vibes qa_riley "Build rapport before asking for details"
inspect qa_riley favorability
```

## Toggle autosave settings in game

```text
settings autosave on
settings autosave-notify off
```

## Calendar settings + weather checks

```text
settings calendar
settings calendar timezone UTC
settings calendar seed randomize
settings calendar timetravel 2026-12-24
calendar week weather
calendar day journal
```
