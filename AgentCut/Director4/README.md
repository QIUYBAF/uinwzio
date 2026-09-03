# AgentCut Director 4.0.0

**AgentCut Director 4** is the new semantic control plane for agent-driven video production.
It is deliberately named and packaged separately from **AgentCut Classic 3.x**.

## Naming boundary

| Generation | Product name | Python distribution | CLI | Canonical state |
|---|---|---|---|---|
| Mature legacy line | AgentCut Classic 3.x | `agentcut` | `agentcut` | Classic `project.json` |
| New generation | AgentCut Director 4 | `agentcut-director` | `agentcut-director` | `agentcut.director.cutgraph.v1` |

Director 4 does not silently overwrite, import as, or masquerade as Classic 3. A Classic project is migrated into a **new** CutGraph file, with source identity and hash recorded.

## What 4.0 adds

- A compact, canonical **CutGraph** designed for agents rather than GUI coordinates.
- Atomic semantic transactions with optimistic hash checks, receipts and reversible undo.
- Dependency-aware impact planning: visual, caption, audio and metadata changes are separated.
- A deterministic, versioned **Remotion Bridge** with copied-asset hashes and bundle verification.
- A non-destructive Classic 3 migration path.
- Structural efficiency auditing without pretending byte reduction equals Codex billing reduction.
- A separate package, CLI, directory and composition ID to prevent generation ambiguity.

## Quick start

```bash
python -m pip install agentcut_director-4.0.0-py3-none-any.whl

agentcut-director init project.json --title "Episode 01"
agentcut-director validate project.json
agentcut-director hash project.json

agentcut-director preflight project.json operations.json
agentcut-director apply project.json operations.json --expected-hash <HASH>
agentcut-director undo project.json

agentcut-director remotion-export project.json remotion_bundle --project-root .
agentcut-director remotion-verify remotion_bundle
```

## Editing loop

```text
bootstrap/hash
→ request task-scoped state
→ preflight semantic operations
→ apply with expected hash
→ render only recommended span/domain
→ QA
→ repeat
→ full Remotion render only at delivery
```

## Remotion division of labour

Director 4 owns project state, timing, assets, transactions, impact analysis, verification and audit receipts.
Remotion owns React presentation, frame-accurate animation and final rendering.
The generated bridge follows Remotion's frame-driven model (`useCurrentFrame`, `interpolate`, `Sequence`) and does not rely on CSS animation.

## Safety rules

- `project.json` is canonical; generated TSX is an output, never a second project state.
- Source assets are never modified.
- Ambiguous creative choices are not silently guessed.
- A failed transaction does not partially mutate the project.
- Hash mismatch rejects stale agent writes.
- Large binaries belong in Drive/release storage, not Git history.

See `ARCHITECTURE.md`, `MIGRATION_FROM_CLASSIC3.md`, and `RELEASE_NOTES_4.0.0.md`.
