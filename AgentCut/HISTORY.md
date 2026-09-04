# AgentCut — milestone history

This file is the compact development path. It is not a second current-state document; use `README.md` for the latest release and deployment status.

## Milestones

### 1.0.1 Remaster — Quick Connect
Restored the complete lightweight 3.3.1 editing runtime into the current 1.x release line, added a direct checkout runner, one-command project bootstrap, actionable non-crashing diagnostics, and verified automatic backend fallback. Heavy optional binaries and model weights remain outside GitHub.

### Alpha 5–10 — runtime/reliability prototypes
Established the early Agent-native editing loop, deterministic state, practical workflow experiments, and reliability/QA scaffolding. These builds are historical only and must not be selected for new deployments.

### 3.0.x — export/runtime consolidation
Established flexible export, 4K delivery profiles, runtime codec probing, and bundled slim Real-ESRGAN support. This was the first mature 3.x runtime line, but it is no longer current.

### 3.2.x — production/editorial coverage
Added stronger subtitles/dialogue handling, cast-aware staging, editorial coverage, attention inserts, and production-friction fixes. 3.2.3 became the last pre-Gen3 baseline. It is retained only as a development milestone.

### 3.3.0 — Gen3 / Jane3 + Remotion bridge
Introduced the semantic visual-essay workflow used by 《她们仍在旅行》: exhibit/info-card/return/montage/silence/quote scene grammar, tiled still-image refinement, actor-card processing, and an AgentCut→Remotion bridge. AgentCut remained the state/director layer while Remotion became the preferred presentation renderer when available.

### 3.3.1 — inherited source baseline
Improved task-scoped Agent context, warm bootstrap, local render-scope planning, efficiency telemetry, and Remotion Bridge v2 integrity checks. Validation recorded 156 automated tests passed with zero failures and a real three-scene bridge E2E proxy render.

However, the validation environment did not claim a fresh npm install + Chromium/Remotion render. Real project use exposed deployment friction. Therefore deployment simplicity is the next P0 rather than another feature-expansion cycle.

### Director 4.0.0 — placeholder / experimental name
A Drive handoff folder was created under this name, but it contains no usable package/source/validation payload. It is not a release baseline and must not supersede the 1.x line.

## Retention policy

Only major milestones are summarized here. Detailed Alpha and patch-by-patch notes are intentionally absent from the current tree; Git history is the archival source when regression archaeology is genuinely needed.
