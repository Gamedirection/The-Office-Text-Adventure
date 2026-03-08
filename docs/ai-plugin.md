# AI Plugin Integration

## Default behavior

`GameEngine` uses `MockAIAdapter` by default, so no external services are required.

## Adapter contract

Implement `AIAdapter.generate_reply(context)` in `engine/ai.py`.

Context includes:

- `npc_id`
- `npc_name`
- `npc_role`
- `npc_profile.personality`
- `npc_profile.age`
- `npc_profile.appearance`
- `npc_profile.tone`
- `npc_profile.backstory`
- `npc_profile.extra_context`
- `npc_stats.intelligence`
- `npc_stats.vibes`
- `npc_stats.physique`
- `npc_stats.luck`
- `interaction`
- `node_id`
- `node_text`
- `location_id`
- `adventure_id`
- `player_action`
- `prompt_append` (combined NPC + interaction prompt additions)

## Wiring a real provider

1. Create a new adapter class that implements `AIAdapter`.
2. Add API calls, retries, and failure handling there.
3. Pass adapter into engine: `GameEngine(ai_adapter=YourAdapter())`.

## NPC data configuration

In `world/npcs/*.yaml`, set interaction modes and optional AI prompt/profile fields:

```yaml
personality: "Analytical and direct"
age: 32
appearance: "Wears a team hoodie and carries a notebook"
tone: "Friendly but concise"
backstory: "Joined during a migration project and became domain expert"
extra_context:
  team: "Platform"
ai_prompt_append: "Stay realistic and reference office workflows."
interactions:
  greet:
    mode: ai
  coaching:
    mode: hybrid
    ai_prompt_append: "Ask one clarifying question before advising."
    manual_responses:
      - "Fallback response if provider fails."
```
