# Architecture

```text
User / Codex intent
        ↓
Semantic operations
        ↓
Preflight + deterministic normalization
        ↓
CutGraph transaction (hash guarded)
        ↓
Receipt + inverse operations + impact plan
        ↓
Remotion Bridge compiler
        ↓
Verified manifest/assets/runtime
        ↓
Remotion render / optional deterministic fallback
```

## CutGraph

The CutGraph stores delivery settings, registered assets, scenes and caption/audio tracks in frames. It is intentionally smaller than a generated React codebase and stable across sessions.

## Transactions

Transactions are applied to a deep copy, validated, and committed only when the complete batch succeeds. Each receipt stores before/after hashes, normalized operations, inverse operations and affected domains/spans. `undo` replays the inverse batch as a new transaction, preserving audit history.

## Impact planner

- Canvas, FPS or timeline-wide structural change: full visual render.
- Scene visual change: affected scene span.
- Caption change: caption span and subtitle/UI layer only.
- Audio change: affected audio span; no video render required.
- Delivery metadata change: no preview render.

The planner is conservative when semantics are unclear.

## Remotion Bridge

The compiler emits:

- `public/director-manifest.json`
- `bridge-receipt.json`
- copied reachable assets under `public/assets/`
- pinned `package.json`
- frame-driven TypeScript/TSX runtime

Verification checks the canonical project hash, manifest hash, runtime hashes and every copied asset hash.
