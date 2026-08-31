# Agent Protocol v5

AgentCut accepts semantic operations through deterministic normalization. Artistic ambiguity is never silently fuzzy-corrected.

## Restart

1. Read `agent-start` / `/agent/bootstrap`.
2. Reuse `checkpoint` and `last_receipt`.
3. On upgrade, inspect `schema_delta`; fetch operation schema only for changed/added actions.
4. Request task-scoped context only for touched scenes/domains.

Do not restore state from chat history when project-local runtime state exists.

## Editing loop

```text
bootstrap → context(scope) → preflight → apply(hash) → recommended render → QA
```

## Low-cognition helpers

- `recipe=dialogue`
- `recipe=band_performance`
- `recipe=reaction`
- `auto_subtitles`
- `subtitle_optimize`
- `stage_by_order`

`stage_by_order` requires explicit character order; visual analysis supplies coordinates only.

## State safety

- `project.json` is canonical.
- Mutations are atomic/versioned.
- Explicit user artistic choices override automation.
- Runtime checkpoint stores bounded semantic decisions, not transcript/chat text.
- Normal project edits do not force a cold bootstrap.
- Upgrade bootstrap returns exact operation-signature delta so unchanged tool definitions need not be reread.