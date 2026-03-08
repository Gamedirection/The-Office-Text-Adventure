# Code Snippets

Reusable snippets for common collaboration tasks.

## Add a shared location (`world/locations/*.yaml`)

```yaml
locations:
  - id: finance_corner
    name: "Finance Corner"
    description: "Budget spreadsheets and planning boards."
    connections:
      - lobby
      - dev_bay
```

## Add a shared global event (`world/events/*.yaml`)

```yaml
events:
  - id: incident_response_week
    name: "Incident Response Week"
    start_date: "2026-06-01"
    end_date: "2026-06-05"
    description: "Focused triage and reliability hardening."
    tags: [ops, reliability]
```

## Add a shared holiday (`world/calendar/*.yaml`)

```yaml
holidays:
  - id: innovation_day
    name: "Innovation Day"
    date: "2026-09-18"
    description: "Dedicated team experimentation day."
```

## Add a shared NPC with AI fallback + profile context

```yaml
npcs:
  - id: analyst_lee
    profile:
      name: "Lee (Analyst)"
      role: "Business Analyst"
      personality: "Calm and evidence-driven"
      age: 34
      appearance: "Blue badge lanyard, laptop full of sticky tabs"
      tone: "Professional and clear"
      backstory: "Former consultant who now leads requirement workshops"
      extra_context:
        domain: "Finance"
        timezone: "EST"
    ai_prompt_append: "Use concise business language and mention tradeoffs."
    stats:
      intelligence: 4
      vibes: 5
      physique: 2
      luck: 3
    relationship:
      favorability_default: 2
    dialogue:
      manual_responses:
        - "Let's align this with the roadmap."
      interactions:
        greet:
          mode: hybrid
          ai_prompt_append: "Ask one clarifying question first."
          manual_responses:
            - "I can summarize requirements if AI is unavailable."
        rude_comment:
          mode: manual
          manual_responses:
            - "That was unhelpful. Let's keep this constructive."
          effects:
            favorability_delta: -1
            memory_tag: "player_was_rude"
```

## Create a new adventure manifest

```yaml
id: your-adventure-id
name: "Your Adventure Title"
creator: "YourName"
description: "One-line summary for the launcher menu."
start_node: intro
supported_players: [Alex, Jon, Dylon]
content:
  story_file: code/story.yaml
```

## Add a story node with choices

```yaml
events:
  - id: janet_new_car
    name: "Janet got a new car"
    day_offset: 5
    description: "Happens 5 days after the adventure starts."
  - id: quarter_kickoff
    name: "Quarter Kickoff"
    date: "2026-04-01"
    description: "Absolute-date event for a fixed world day."

nodes:
  intro:
    location_id: lobby
    text: "[bold][green]You arrive just before a critical meeting.[/green][/bold]"
    npcs: [manager_mina]
    choices:
      - id: prep
        text: "Review notes first"
        next_node: prep_room
        unlock_npc_stats:
          - manager_mina
      - id: enter
        text: "Go in now"
        next_node: meeting_room
```

## Unlock NPC stats on scene entry

```yaml
nodes:
  meeting_room:
    unlock_npc_stats_on_enter:
      - qa_riley
```

## Unlock NPC stats via intelligence check in talk interaction

```yaml
dialogue:
  interactions:
    profile_check:
      mode: manual
      manual_responses:
        - "Let's compare your diagnosis to mine."
      unlock_stats_on_intelligence_check: true
```

Rule: this unlock check can be attempted once per NPC; after a failed first attempt, reach favorability `3` to unlock later.

## Add TUI color + text-style tags in story text

```yaml
text: "[gold]Mina[/gold] says: [italic]Let's stay aligned.[/italic]"
```

```yaml
text: "[bold][blue]Checklist Updated[/blue][/bold] and ready for review."
```

## Execute commands via engine API

```python
from engine.game_engine import GameEngine

engine = GameEngine()
print(engine.start("alex/sprint-standup"))
print(engine.execute_command("talk manager_mina greet"))
print(engine.execute_command("choose prep_board"))
print(engine.execute_command("save slot1"))
```

## Inject a custom AI adapter

```python
from engine.ai import AIAdapter
from engine.game_engine import GameEngine

class MyAdapter(AIAdapter):
    def generate_reply(self, context: dict[str, object]) -> str:
        # context["npc_profile"] and context["prompt_append"] are available.
        return "[REAL-AI] Implement provider call here."

engine = GameEngine(ai_adapter=MyAdapter())
```

## Add a save/load helper call in scripts

```python
print(engine.execute_command("save demo"))
print(engine.execute_command("load demo"))
print(engine.execute_command("saves"))
print(engine.execute_command("goto meeting_room"))
print(engine.execute_command("journal add Check QA coverage before release"))
print(engine.execute_command("journal remove 1"))
print(engine.execute_command("stats"))
print(engine.execute_command("check vibes qa_riley Pitch update clearly in standup"))
print(engine.execute_command("inspect qa_riley favorability"))
print(engine.execute_command("name Alex"))
print(engine.execute_command("calendar day"))
print(engine.execute_command("calendar day weather"))
print(engine.execute_command("settings calendar"))
print(engine.execute_command("settings calendar timezone America/New_York"))
print(engine.execute_command("settings calendar seed randomize"))
print(engine.execute_command("settings calendar timetravel 2026-12-24"))
```
