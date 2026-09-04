from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from importlib import resources
from copy import deepcopy

from .errors import AgentCutError

LIBRARY_FILES = {
    'transitions': 'transitions.json',
    'effects': 'effects.json',
    'filters': 'filters.json',
    'motions': 'motions.json',
    'layer_motions': 'layer_motions.json',
    'subtitle_styles': 'subtitle_styles.json',
    'audio_cues': 'audio_cues.json',
    'materials': 'materials.json',
}


def _library_root() -> Path:
    # Kept for source-checkout diagnostics/backward compatibility. Runtime loading uses
    # package resources so wheel installations do not depend on a sibling directory.
    return Path(__file__).resolve().parent.parent / 'libraries'


def _library_text(filename: str) -> str:
    try:
        ref = resources.files('agentcut.data.libraries').joinpath(filename)
        return ref.read_text(encoding='utf-8')
    except (ModuleNotFoundError, FileNotFoundError):
        path = _library_root() / filename
        if path.exists():
            return path.read_text(encoding='utf-8')
        raise AgentCutError('LIBRARY_MISSING', 'Library file is missing', path=str(path), resource=f'agentcut.data.libraries/{filename}')


@lru_cache(maxsize=None)
def _load(kind: str) -> dict:
    if kind not in LIBRARY_FILES:
        raise AgentCutError('UNKNOWN_LIBRARY', 'Unknown content library', kind=kind, allowed=sorted(LIBRARY_FILES))
    data = json.loads(_library_text(LIBRARY_FILES[kind]))
    items = data.get('items')
    if not isinstance(items, list):
        raise AgentCutError('INVALID_LIBRARY', 'Library items must be an array', kind=kind)
    index = {item['id']: item for item in items if isinstance(item, dict) and item.get('id')}
    return {'schema_version': data.get('schema_version', 1), 'items': items, 'index': index}


def list_libraries() -> dict:
    return {kind: len(_load(kind)['items']) for kind in LIBRARY_FILES}


def list_items(kind: str, *, tags: list[str] | tuple[str, ...] | None = None, stable_only: bool = False) -> list[dict]:
    rows = _load(kind)['items']
    tags = [t.lower() for t in (tags or [])]
    out = []
    for row in rows:
        if stable_only and row.get('stability') != 'stable':
            continue
        row_tags = {str(x).lower() for x in row.get('tags', [])}
        if tags and not all(t in row_tags for t in tags):
            continue
        out.append(deepcopy(row))
    return out


def get_item(kind: str, item_id: str) -> dict:
    row = _load(kind)['index'].get(item_id)
    if row is None:
        raise AgentCutError('LIBRARY_ITEM_NOT_FOUND', 'Unknown library item', kind=kind, item_id=item_id)
    return deepcopy(row)


def material_defaults(material_id: str | None) -> dict:
    if not material_id:
        return {}
    return deepcopy(get_item('materials', material_id).get('defaults', {}))


def transition_backend(transition_id: str) -> str:
    if transition_id == 'cut':
        return 'cut'
    return str(get_item('transitions', transition_id).get('backend', 'fade'))


def filter_backend(filter_id: str) -> str:
    return str(get_item('filters', filter_id).get('backend', 'null'))
