from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import metadata
from typing import Any


@dataclass(frozen=True)
class ProductIdentity:
    product: str = "AgentCut Director"
    release_line: str = "AgentCut Director 4"
    cli: str = "agentcut-director"
    python_package: str = "agentcut_director"
    classic_line: str = "AgentCut Classic 3"
    classic_distribution: str = "agentcut"
    canonical_ir: str = "CutGraph"
    portable_build: str = "CutBundle"
    remotion_adapter: str = "AgentCut Remotion Adapter"
    ffmpeg_adapter: str = "AgentCut FFmpeg Adapter"
    reserved_gui: str = "AgentCut Studio"


PRODUCT_IDENTITY = ProductIdentity()


def package_version() -> str:
    try:
        return metadata.version("agentcut-director")
    except metadata.PackageNotFoundError:
        return "4.0.0"


def identity_payload() -> dict[str, Any]:
    return {
        "schema": "agentcut.identity.v1",
        "version": package_version(),
        "identity": asdict(PRODUCT_IDENTITY),
        "ownership": {
            "canonical_timeline": "CutGraph",
            "semantic_transactions": "AgentCut Director",
            "presentation": "renderer adapter",
            "remotion": "rendering backend only",
            "classic3": "optional compatibility runtime only",
        },
    }
