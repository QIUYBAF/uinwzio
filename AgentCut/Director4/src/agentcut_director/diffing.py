from __future__ import annotations

from typing import Any


def semantic_diff(before: Any, after: Any, path: str = "$") -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after, "kind": "type_changed"}]
    if isinstance(before, dict):
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}"
            if key not in before:
                changes.append({"path": child, "before": None, "after": after[key], "kind": "added"})
            elif key not in after:
                changes.append({"path": child, "before": before[key], "after": None, "kind": "removed"})
            else:
                changes.extend(semantic_diff(before[key], after[key], child))
        return changes
    if isinstance(before, list):
        if all(isinstance(x, dict) and "id" in x for x in before + after):
            left = {x["id"]: x for x in before}
            right = {x["id"]: x for x in after}
            for item_id in sorted(set(left) | set(right)):
                changes.extend(semantic_diff(left.get(item_id), right.get(item_id), f"{path}[id={item_id}]"))
            return changes
        limit = max(len(before), len(after))
        for index in range(limit):
            if index >= len(before):
                changes.append({"path": f"{path}[{index}]", "before": None, "after": after[index], "kind": "added"})
            elif index >= len(after):
                changes.append({"path": f"{path}[{index}]", "before": before[index], "after": None, "kind": "removed"})
            else:
                changes.extend(semantic_diff(before[index], after[index], f"{path}[{index}]"))
        return changes
    if before != after:
        changes.append({"path": path, "before": before, "after": after, "kind": "changed"})
    return changes
