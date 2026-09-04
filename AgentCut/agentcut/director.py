from __future__ import annotations
import shutil

def choose_backend(*, needs_react_ui=False):
    node=shutil.which("node"); npm=shutil.which("npm"); remotion=bool(node and npm)
    if needs_react_ui and remotion: selected="remotion"; reason="React/UI presentation requested and Node/npm available"
    else: selected="ffmpeg/pillow"; reason="deterministic low-friction path is sufficient"
    return {"selected":selected,"remotion_available":remotion,"reason":reason,"rule":"Prefer the cheapest healthy backend that satisfies the result."}

def plan(goal, *, scenes=None, domains=None, needs_react_ui=False):
    return {"schema":"agentcut-director-plan-v1","goal":goal,"scope":scenes or ["task-scoped"],"domains":domains or ["infer-minimum-required"],"backend":choose_backend(needs_react_ui=needs_react_ui),"loop":["bootstrap","scoped-context","preflight","apply","local-preview","qa","stop-or-one-local-fix"],"guardrails":["no repository archaeology","no full render when local preview is sufficient","no repeated QA without a concrete failure","preserve canonical project state"]}
