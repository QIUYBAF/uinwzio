# AgentCut Director 4.0.0

AgentCut Director is the semantic control plane for AI-operated video editing. It does not compete with Remotion as a frame renderer.

## Names

| Name | Exact role |
|---|---|
| **AgentCut Director 4** | Product, agent API and transaction layer |
| **CutGraph v1** | Backend-neutral canonical timeline/state |
| **CutBundle v1** | Immutable output compiled for one renderer |
| **AgentCut Remotion Adapter** | CutGraph → Remotion compiler |
| **Remotion** | Presentation/frame rendering engine |
| **AgentCut Classic 3** | Optional legacy runtime, distribution `agentcut` |

The new distribution is `agentcut-director`, the Python import is `agentcut_director`, and the commands are `agentcut-director` and `agentcut4`. It deliberately does not overwrite the Classic 3 `agentcut` command.

## Workflow

```bash
agentcut-director identity
agentcut-director migrate old/project.json --out project/cutgraph.json
agentcut-director verify-graph project/cutgraph.json
agentcut-director compile-remotion project/cutgraph.json --out project/remotion_bundle
agentcut-director verify-bundle project/remotion_bundle
```

## Guarantees

- deterministic canonical JSON and SHA-256;
- atomic transactions with optimistic concurrency;
- history receipts and linear undo;
- dependency-aware video/audio impact spans;
- externally supplied usage only—no fake Codex credit estimates;
- pinned, hash-verified Remotion CutBundles;
- full Classic 3 source payload preserved during migration.

Read `docs/NAMING.md`, `docs/ARCHITECTURE.md`, `docs/CUTGRAPH_V1.md`, `docs/REMOTION_ADAPTER.md`, and `docs/MIGRATION.md`.
