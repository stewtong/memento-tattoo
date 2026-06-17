from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional, Tuple

from .config import paths_for
from .lock import memory_lock
from .project_memory import ensure_project_memory, replace_section


def _hash8(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:8]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _append_eof(path: Path, sess: str, kind: str, body: str) -> Tuple[bool, str]:
    marker = f"<!-- delta:{sess}.{kind}.{_hash8(body)} -->"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in existing:
        return False, marker
    prefix = existing
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    spacer = "\n" if prefix else ""
    _atomic_write(path, f"{prefix}{spacer}{marker}\n{body.rstrip()}\n")
    return True, marker


def _first_situation_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip().lower().startswith("situation:"):
            return line.split(":", 1)[1].strip()
    stripped = [line.strip() for line in text.splitlines() if line.strip()]
    return stripped[0] if stripped else ""


def _note_id_from_marker(marker: str) -> str:
    return marker[len("<!-- delta:") : -len(" -->")]


def note_add(
    text: str,
    *,
    sess: str,
    root: Path,
    kind: str = "reflection",
) -> Tuple[bool, str]:
    paths = paths_for(root)

    if kind == "seed":
        with memory_lock(paths.root):
            return _append_eof(paths.notes, sess, "note", text)

    from ._time import now_iso
    from .retention import append_retention_event, classify

    situation = _first_situation_line(text)
    result = classify(situation, root=paths.root)
    with memory_lock(paths.root):
        applied, marker = _append_eof(paths.notes, sess, "note", text)
        if applied:
            append_retention_event(
                {
                    "ts": now_iso(),
                    "sess": sess,
                    "kind": kind,
                    "situation": situation,
                    "note_id": _note_id_from_marker(marker),
                    "candidates": result["candidates"],
                    "decision": result["suggested_decision"],
                    "repair": "",
                    "decided_by": "agent",
                    "review_needed": True,
                },
                root=paths.root,
                assume_locked=True,
            )
    return applied, marker


def tattoo_add(text: str, *, sess: str, root: Path) -> Tuple[bool, str]:
    paths = paths_for(root)
    body = text.strip()
    if not body.startswith("- "):
        body = f"- {body}"
    with memory_lock(paths.root):
        if not paths.tattoos.exists():
            _atomic_write(paths.tattoos, "# Tattoos\n")
        return _append_eof(paths.tattoos, sess, "tattoo", body)


def project_edit(
    body: str,
    *,
    sess: str,
    root: Path,
    project: Path,
    section: str = "## State",
    flow_start: Optional[str] = None,
) -> Tuple[bool, str]:
    paths = paths_for(root)
    marker = f"<!-- delta:{sess}.project.{_hash8(section + body)} -->"
    with memory_lock(paths.root):
        path = ensure_project_memory(project)
        existing = path.read_text(encoding="utf-8")
        if marker in existing:
            return False, marker
        updated = replace_section(existing, section, body, marker, preserve_existing=bool(flow_start))
        _atomic_write(path, updated)
        return True, marker
