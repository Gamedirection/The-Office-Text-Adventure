# Content Authoring Rules

## ID rules

- Use stable lowercase IDs with underscores.
- Never rename IDs without updating all references.

## Cross-reference keys

- `location_id` -> `world/locations` IDs.
- `npcs[]` -> `world/npcs` IDs.
- `items[]` -> `world/items` IDs.
- `objects[]` -> `world/objects` IDs.
- `choices[].next_node` -> another node ID in the same story file.

## Adventure folder contract

- `adventures/<creator>/<adventure_name>/manifest.yaml`
- `adventures/<creator>/<adventure_name>/code/story.yaml`

## Adventure timeline events (`story.yaml`)

Add optional top-level `events: []` in story files.

Relative event (default style):

- `day_offset`: integer days from the adventure start date.

Absolute event (explicit date):

- `date`: `YYYY-MM-DD` (use this only when event must happen on a specific day).

Required fields for both:

- `id` (lowercase/underscore)
- `name`
- `description`

## Global calendar content (shared world)

- `world/events/*.yaml` with top-level `events: []`
- `world/calendar/*.yaml` with top-level `holidays: []`

Event schema:

- `id` (lowercase/underscore)
- `name`
- `start_date` (`YYYY-MM-DD`)
- `end_date` (`YYYY-MM-DD`, optional; defaults to start date)
- `description`
- `tags` (optional list)

Holiday schema:

- `id` (lowercase/underscore)
- `name`
- `date` (`YYYY-MM-DD`)
- `description` (optional)

## Choice templates

Optional choice keys:

- `requires_item`
- `add_items`
- `remove_items`
- `set_flags`

## NPC interaction modes

- `manual`: always use scripted response.
- `ai`: always ask AI adapter.
- `hybrid`: try AI, then fallback to manual response.

## NPC AI context fields

Optional NPC-level fields for richer AI responses:

- `personality`
- `age`
- `appearance`
- `tone`
- `backstory`
- `extra_context` (any YAML object/list)
- `ai_prompt_append` (extra prompt text applied to all AI interactions)

Optional interaction-level field:

- `interactions.<name>.ai_prompt_append` (extra prompt text for that interaction)

## Rebased NPC structure

Preferred NPC layout in `world/npcs/*.yaml`:

- `profile`: name, role, personality, age, appearance, tone, backstory, extra_context
- `stats`: intelligence/vibes/physique/luck (1-6)
- `relationship`: includes `favorability_default` (1-3)
- `dialogue`:
  - `manual_responses` (fallback)
  - `interactions.<interaction_name>` with `mode`, responses, and optional effects

Interaction effect keys:

- `effects.favorability_delta`: integer change applied after interaction
- `effects.memory_tag`: string tag appended to NPC memory history

## Unlock NPC stats via intelligence check

Interactions can trigger an opposed intelligence check against the NPC.
If player succeeds, that NPC's stats unlock.

```yaml
dialogue:
  interactions:
    profile_check:
      mode: manual
      manual_responses:
        - "Let's compare notes."
      unlock_stats_on_intelligence_check: true
```

Behavior rule:

- First intelligence unlock attempt is always tracked.
- If it fails, further unlock attempts are blocked until NPC favorability reaches `3`.
- Successful vibe checks can reveal favorability before full stat unlock.
- When only favorability is visible, player output reads:
  - `Some stats for <npc> are still locked.`
  - favorability line only; other stats remain hidden.

## Stat fields (1-6 scale)

Stats use a 1-6 scale where 6 is best and 1 is worst.

- `intelligence`: analysis, planning, technical reasoning.
- `vibes`: social/emotional intelligence and communication quality.
- `physique`: stamina/coordination for physical tasks.
- `luck`: chance-driven outcomes.

Player stats live in `.player/config/player.yaml`:

```yaml
player_stats:
  intelligence: 3
  vibes: 3
  physique: 3
  luck: 3
```

NPC stats can be authored in `world/npcs/*.yaml`:

```yaml
stats:
  intelligence: 4
  vibes: 5
  physique: 2
  luck: 3
```

## Choice checks (optional)

Choices can include a stat check block:

```yaml
choices:
  - id: risky_pitch
    text: "Pitch an ambitious idea to leadership."
    check:
      stat: vibes
      description: "Present confidently to leadership"
      on_critical: perfect_outcome_node
      on_success: success_node
      on_fail: awkward_outcome_node
```

## NPC stat unlocks (default false)

NPC stats are hidden until unlocked by adventure content.

Use these optional keys:

- `choices[].unlock_npc_stats` -> list of NPC IDs to unlock
- `choices[].lock_npc_stats` -> list of NPC IDs to lock
- `nodes.<id>.unlock_npc_stats_on_enter` -> list of NPC IDs unlocked when node is rendered

Example:

```yaml
nodes:
  intro:
    unlock_npc_stats_on_enter: [manager_mina]
```

## Missing outcome logging for authors

Unhandled actions are logged per adventure:

- `.player/logs/%USERNAME%-<Adventure>-MissingAction.log`

Use these logs to identify content gaps (for example, unsupported inspect sub-targets) and add outcomes to story/NPC/world data.
