# AgentCut 3.0.2 — Agent Protocol v2

## Preferred loop

```text
GET /agent/context
→ POST /agent/preflight
→ inspect repairs + impact + verification
→ POST /agent/apply with expected_project_hash
→ render recommended scene/span/full scope
→ QA + inspect relevant frames
```

## Flexible input, strict semantics

Canonical:

```json
{"action":"set_camera","args":{"scene_id":"scene_01","motion":"slow_push"}}
```

Also accepted by the Agent gateway:

```json
{"operation":"camera","params":{"scene":"scene_01","type":"slow_push"}}
```

and flattened arguments:

```json
{"action":"camera","scene":"scene_01","type":"slow_push"}
```

A singleton operation object or `{ "operations": [...] }` wrapper is accepted. The strict transaction endpoint remains canonical-only.

Safe automatic repair covers deterministic action/argument/shape aliases, case/hyphen/snake normalization and uniquely high-confidence syntax typos. Creative/library ambiguity is never silently fuzzy-corrected.

## Agent Context

`GET /agent/context` combines compact state, entity IDs, selected scene context and an optionally domain-filtered operation schema. Example: `?scene_ids=scene_04,scene_05&domains=visual,cinematic,text`.

## Compact preflight

Preflight returns normalized operations, repairs/warnings, projected digest/hash, changed scene IDs, global-change flags, a recommended render scope and verification/risk steps. Full projected `project.json` is opt-in.

Transition edits are boundary-aware and recommend rendering the current + next scene span.

## Apply receipt

Apply returns a compact transaction receipt containing transaction ID, before/after hashes, normalized operations, result summaries, final state digest, impact and verification plan. Full project/results are opt-in.

## Recovery

Preflight syntax errors return structured `ok:false` results. Missing entity IDs include nearby valid candidates when possible. State conflict recovery explicitly tells the Agent to reread `/agent/context` and retry with the new hash.

## Export

Export remains separate from canonical edit transactions. Always inspect export planning and the actual `.agentcut-export.json` result before claiming GPU/AI backends were used.
