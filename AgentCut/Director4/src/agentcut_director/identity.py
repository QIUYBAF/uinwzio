from __future__ import annotations

from typing import Any

PRODUCT_NAME = "AgentCut Director"
PRODUCT_SLUG = "agentcut-director"
CLI_NAME = "agentcut-director"
VERSION = "4.0.0"
GENERATION = 4
SCHEMA = "agentcut.director.cutgraph.v1"
REMOTION_SCHEMA = "agentcut.director.remotion.v1"
CLASSIC_FAMILY = "AgentCut Classic 3.x"
COMPOSITION_ID = "AgentCutDirector4"


def product_identity() -> dict[str, Any]:
    return {
        "name": PRODUCT_NAME,
        "slug": PRODUCT_SLUG,
        "cli": CLI_NAME,
        "version": VERSION,
        "generation": GENERATION,
        "schema": SCHEMA,
        "classic_family": CLASSIC_FAMILY,
        "composition_id": COMPOSITION_ID,
    }


def assert_director_identity(project: dict[str, Any]) -> None:
    if project.get("schema") != SCHEMA:
        raise ValueError(f"expected schema {SCHEMA!r}, got {project.get('schema')!r}")
    identity = project.get("product") or {}
    if identity.get("name") != PRODUCT_NAME or int(identity.get("generation", -1)) != GENERATION:
        raise ValueError("project identity is not AgentCut Director generation 4")
