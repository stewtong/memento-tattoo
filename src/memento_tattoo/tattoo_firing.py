from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .config import PathLike, paths_for
from .lock import memory_lock

_TATTOO_REF_RE = re.compile(r"\[\[((?:sess_[0-9A-Za-z]+)\.tattoo\.[0-9A-Za-z]+)\]\]")


def tattoo_firing_path(root: Optional[PathLike] = None) -> Path:
    return paths_for(root).root / "tattoo_firing.json"


def extract_tattoo_refs(text: str) -> list[str]:
    return _TATTOO_REF_RE.findall(text or "")


def tattoo_firing_counts(root: Optional[PathLike] = None) -> dict:
    path = tattoo_firing_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def durable_tattoo_firing_counts(root: Optional[PathLike] = None) -> dict:
    paths = paths_for(root)
    sources = [paths.notes, paths.notes_archive]
    if paths.sessions.exists():
        sources.extend(paths.sessions.glob("sess_*.md"))
        sources.extend((paths.sessions / "archive").glob("sess_*.md"))
    counts: dict[str, dict] = {}
    for path in sources:
        if not path.exists() or not path.is_file():
            continue
        for tattoo_id in extract_tattoo_refs(path.read_text(encoding="utf-8", errors="replace")):
            entry = counts.setdefault(tattoo_id, {"count": 0, "last_used": None})
            entry["count"] += 1
    return counts


def effective_tattoo_firing_counts(root: Optional[PathLike] = None) -> dict:
    cached = tattoo_firing_counts(root)
    durable = durable_tattoo_firing_counts(root)
    merged = {key: dict(value) for key, value in cached.items() if isinstance(value, dict)}
    for key, value in durable.items():
        current = merged.setdefault(key, {"count": 0, "last_used": None})
        current["count"] = max(int(current.get("count", 0)), int(value["count"]))
    return merged


def firings_for_session(sess: str | None, counts: dict) -> int:
    if not sess:
        return 0
    return sum(int(value.get("count", 0)) for key, value in counts.items() if key.startswith(f"{sess}.tattoo."))


def bump_tattoo_firing(
    text: str,
    root: Optional[PathLike] = None,
    *,
    now: str,
    assume_locked: bool = False,
) -> int:
    refs = extract_tattoo_refs(text)
    if not refs:
        return 0
    path = tattoo_firing_path(root)
    lock_root = paths_for(root).root

    def _do() -> int:
        data = tattoo_firing_counts(root)
        for tattoo_id in refs:
            entry = data.get(tattoo_id) or {"count": 0, "last_used": None}
            entry["count"] = int(entry.get("count", 0)) + 1
            entry["last_used"] = now
            data[tattoo_id] = entry
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return len(refs)

    if assume_locked:
        return _do()
    with memory_lock(lock_root):
        return _do()
