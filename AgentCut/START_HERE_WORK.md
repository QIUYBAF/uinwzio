# START HERE — AgentCut 3.2.3

Cross-conversation / Work / Codex handoff entry.

## Current stable baseline

**3.2.3 — Editorial Coverage / Anti-Template Pass.**

Validation:
- **145 / 145 automated tests passed**
- dedicated 3.2.3 coverage tests: 10 / 10
- `agentcut doctor`: pass
- EP07 Nether diagnostic coverage proxy: render + QA pass
- bundled Real-ESRGAN retained

## First action on restart

Do **not** reread the repository or full operation schema.

```text
agentcut agent-start PROJECT
# or GET /agent/bootstrap
```

Protocol v5 returns a bounded resume capsule containing current goal, active scenes, last receipt, key decisions and exact schema delta when needed. Normal project edits remain warm resume.

## Preferred edit loop

```text
bootstrap
→ task-scoped context only if needed
→ preflight
→ apply
→ render recommended proxy scene/span/full scope
→ QA + visual inspection
→ repeat
→ export-plan/export only at delivery
```

## 3.2.3 editorial rule

For dialogue-heavy anime/dynamic-manga scenes, do not default to one continuous push just to avoid stillness. Use semantic hierarchy only when motivated:

```text
establish/group
→ speaker coverage
→ reaction or object/action insert
→ group reset
```

Use `direct_dialogue_coverage` for Cast-aware dialogue and `direct_attention_insert` for non-Cast objects/actions. `compose_dialogue_scene(direction="auto")` may select coverage on longer multi-speaker scenes.

Important boundaries:
- coverage does not rewrite subtitle text/timing
- stillness remains valid on short/contemplative scenes
- visual anchors estimate positions, never character identity without explicit order
- editorial QA warnings are prompts, not renderer failures

## EP07 asset boundary

Current 3.2.3 validation visuals are marked **PROXY STORYBOARD**. They are not final generated EP07 release art. Do not publish or use them as canonical final imagery. When the prepared final images are accessible, swap scene assets and rerun staging/coverage/QA/proxy; keep the existing canonical timeline and subtitle logic unless actual art reveals a concrete reason to change it.

Full source Handoff: `AgentCut_v3.2.3_Handoff`.

Read next:
1. `V3.2.3_EDITORIAL_COVERAGE.md`
2. `V3.2.2_PRODUCTION_FRICTION.md`
3. `AGENT_PROTOCOL.md`
4. `VALIDATION_SUMMARY_V3.md`