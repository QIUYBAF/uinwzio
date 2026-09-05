"""AgentCut: semantic video editing runtime for autonomous agents."""

from typing import TYPE_CHECKING

__all__ = ["Editor"]
__version__ = "1.1.0.dev0"

if TYPE_CHECKING:
    from .editor import Editor


def __getattr__(name: str):
    if name == "Editor":
        from .editor import Editor
        return Editor
    raise AttributeError(name)
