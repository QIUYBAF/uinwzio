# AgentCut Director 4 — Agent Rules

1. Read this file and `README.md`; do not recursively read AgentCut Classic documentation unless migration is the task.
2. Treat `agentcut.director.cutgraph.v1` JSON as the only canonical edit state.
3. Preflight before apply. Apply with `expected_project_hash`.
4. Prefer one atomic transaction over many partially dependent writes.
5. Use the returned impact plan; do not render the full video for a local change without a reason.
6. Generated Remotion files are compiler output. Fix the CutGraph/compiler rather than hand-forking timing in TSX.
7. Do not modify source media. Verify recorded hashes before copying.
8. Preserve the naming boundary: “AgentCut Director 4” and “AgentCut Classic 3.x” are distinct products.
9. Do not claim Codex credit savings from structural byte/frame proxies; record actual usage separately.
10. Every release requires tests, clean wheel install, demo bridge verification, checksums and one Drive ACTIVE handoff.
