from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "agentcut.cutgraph.v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class CutGraphError(ValueError):
    def __init__(self, code: str, message: str, *, path: str | None = None, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.path = path
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "path": self.path, "details": self.details}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def object_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _number(value: Any, name: str, *, integer: bool = False, minimum: float = 0) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < minimum:
        raise CutGraphError("INVALID_NUMBER", f"{name} must be finite and >= {minimum}", path=name)
    return int(value) if integer else float(value)


@dataclass(frozen=True)
class GraphReport:
    ok: bool
    sha256: str
    project_id: str
    asset_count: int
    node_count: int
    edge_count: int
    duration_frames: int

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class CutGraph:
    def __init__(self, data: Mapping[str, Any]):
        self._data = copy.deepcopy(dict(data))

    @classmethod
    def create(cls, *, project_id: str, title: str, width: int, height: int, fps: float, duration_frames: int,
               assets: list[dict[str, Any]] | None = None, nodes: list[dict[str, Any]] | None = None,
               edges: list[dict[str, Any]] | None = None, extensions: dict[str, Any] | None = None) -> "CutGraph":
        return cls.from_dict({
            "schema": SCHEMA,
            "project": {"id": project_id, "title": title, "width": width, "height": height, "fps": fps, "duration_frames": duration_frames},
            "assets": assets or [], "nodes": nodes or [], "edges": edges or [], "extensions": extensions or {},
        })

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, validate: bool = True) -> "CutGraph":
        graph = cls(data)
        if validate:
            graph.validate()
        return graph

    @classmethod
    def load(cls, path: str | Path, *, validate: bool = True) -> "CutGraph":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise CutGraphError("INVALID_ROOT", "CutGraph root must be an object")
        return cls.from_dict(raw, validate=validate)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    @property
    def sha256(self) -> str:
        return object_sha256(self._data)

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self._data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return target

    def validate(self) -> GraphReport:
        data = self._data
        if data.get("schema") != SCHEMA:
            raise CutGraphError("SCHEMA_MISMATCH", f"Expected {SCHEMA}", path="schema")
        project = data.get("project")
        if not isinstance(project, Mapping):
            raise CutGraphError("MISSING_PROJECT", "project must be an object", path="project")
        project_id = str(project.get("id") or "")
        if not project_id:
            raise CutGraphError("MISSING_PROJECT_ID", "project.id is required")
        _number(project.get("width"), "project.width", integer=True, minimum=1)
        _number(project.get("height"), "project.height", integer=True, minimum=1)
        _number(project.get("fps"), "project.fps", minimum=0.001)
        duration = int(_number(project.get("duration_frames"), "project.duration_frames", integer=True, minimum=1))
        assets = data.get("assets")
        nodes = data.get("nodes")
        edges = data.get("edges")
        if not isinstance(assets, list) or not isinstance(nodes, list) or not isinstance(edges, list):
            raise CutGraphError("INVALID_COLLECTION", "assets, nodes and edges must be arrays")

        asset_ids: set[str] = set()
        for i, asset in enumerate(assets):
            if not isinstance(asset, Mapping):
                raise CutGraphError("INVALID_ASSET", "asset must be an object", path=f"assets[{i}]")
            asset_id = str(asset.get("id") or "")
            if not asset_id or asset_id in asset_ids:
                raise CutGraphError("DUPLICATE_ASSET", f"Invalid or duplicate asset id: {asset_id}")
            asset_ids.add(asset_id)
            if asset.get("sha256") is not None and not HEX64.fullmatch(str(asset["sha256"]).lower()):
                raise CutGraphError("INVALID_ASSET_HASH", f"Invalid sha256 for {asset_id}")

        node_ids: set[str] = set()
        max_end = 0
        for i, node in enumerate(nodes):
            if not isinstance(node, Mapping):
                raise CutGraphError("INVALID_NODE", "node must be an object", path=f"nodes[{i}]")
            node_id = str(node.get("id") or "")
            if not node_id or node_id in node_ids:
                raise CutGraphError("DUPLICATE_NODE", f"Invalid or duplicate node id: {node_id}")
            node_ids.add(node_id)
            start = _number(node.get("start_frame"), f"nodes[{i}].start_frame", integer=True, minimum=0)
            length = _number(node.get("duration_frames"), f"nodes[{i}].duration_frames", integer=True, minimum=1)
            max_end = max(max_end, int(start) + int(length))
            for ref in node.get("asset_refs", []):
                if str(ref) not in asset_ids:
                    raise CutGraphError("MISSING_ASSET_REF", f"{node_id} references missing asset {ref}")
            if node.get("parent") is not None and str(node["parent"]) == node_id:
                raise CutGraphError("SELF_PARENT", f"{node_id} cannot parent itself")
        if max_end > duration:
            raise CutGraphError("NODE_OUT_OF_RANGE", f"nodes end at {max_end}, project ends at {duration}")

        dependency_relations = {"depends_on", "derived_from", "invalidates"}
        adjacency = {node_id: set() for node_id in node_ids}
        indegree = {node_id: 0 for node_id in node_ids}
        for edge in edges:
            if not isinstance(edge, Mapping):
                raise CutGraphError("INVALID_EDGE", "edge must be an object")
            source, target = str(edge.get("from") or ""), str(edge.get("to") or "")
            if source not in node_ids or target not in node_ids:
                raise CutGraphError("MISSING_EDGE_NODE", f"unknown edge endpoint {source}->{target}")
            if edge.get("relation") in dependency_relations and target not in adjacency[source]:
                adjacency[source].add(target)
                indegree[target] += 1
        queue = sorted(k for k, v in indegree.items() if v == 0)
        visited = 0
        while queue:
            node = queue.pop(0)
            visited += 1
            for target in sorted(adjacency[node]):
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
                    queue.sort()
        if visited != len(node_ids):
            raise CutGraphError("DEPENDENCY_CYCLE", "dependency graph contains a cycle")
        return GraphReport(True, self.sha256, project_id, len(assets), len(nodes), len(edges), duration)
