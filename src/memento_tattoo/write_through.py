from __future__ import annotations

import uuid
import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple

from .agent import format_delta_marker, parse_delta_marker, resolve_agent
from .config import paths_for
from .lock import memory_lock
from .project_memory import append_section, delta_note_ids, ensure_project_memory, extract_section_body, replace_section, section_changed_since


def _hash8(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:8]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _append_eof(path: Path, sess: str, kind: str, body: str, *, agent: str = "unknown") -> Tuple[bool, str]:
    note_id = f"{sess}.{kind}.{_hash8(body)}"
    marker = format_delta_marker(note_id, agent=agent)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if note_id in existing:
        return False, _find_existing_marker(existing, note_id) or marker
    prefix = existing
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    spacer = "\n" if prefix else ""
    _atomic_write(path, f"{prefix}{spacer}{marker}\n{body.rstrip()}\n")
    return True, marker


def _find_existing_marker(text: str, note_id: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("<!--") and f"delta:{note_id}" in line:
            return line.strip()
    return None


def _first_situation_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip().lower().startswith("situation:"):
            return line.split(":", 1)[1].strip()
    stripped = [line.strip() for line in text.splitlines() if line.strip()]
    return stripped[0] if stripped else ""


def _note_id_from_marker(marker: str) -> str:
    parsed = parse_delta_marker(marker)
    if parsed is not None:
        return parsed.note_id
    return marker[len("<!-- delta:") : -len(" -->")]


def note_add(
    text: str,
    *,
    sess: str,
    root: Path,
    kind: str = "reflection",
    agent: Optional[str] = None,
    decision: Optional[str] = None,
    repair: str = "",
    covered_note_id: Optional[str] = None,
) -> Tuple[bool, str]:
    paths = paths_for(root)
    agent_id = resolve_agent(agent)
    has_retention_judgment = decision is not None or bool(repair) or covered_note_id is not None

    if kind == "seed":
        if has_retention_judgment:
            raise ValueError("retention judgment requires correction or reflection note")
        with memory_lock(paths.root):
            return _append_eof(paths.notes, sess, "note", text, agent=agent_id)

    from ._time import now_iso
    from .retention import DECISIONS, append_retention_event, classify

    if decision is not None and decision not in DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(DECISIONS)}")

    situation = _first_situation_line(text)
    result = classify(situation, root=paths.root)
    final_decision = decision or result["suggested_decision"]
    with memory_lock(paths.root):
        applied, marker = _append_eof(paths.notes, sess, "note", text, agent=agent_id)
        if applied:
            event = {
                "ts": now_iso(),
                "sess": sess,
                "kind": kind,
                "situation": situation,
                "note_id": _note_id_from_marker(marker),
                "candidates": result["candidates"],
                "decision": final_decision,
                "repair": repair,
                "decided_by": "agent",
                "review_needed": decision is None,
            }
            if covered_note_id:
                event["covered_note_id"] = covered_note_id
            append_retention_event(event, root=paths.root, assume_locked=True)
    return applied, marker


def tattoo_add(text: str, *, sess: str, root: Path, agent: Optional[str] = None) -> Tuple[bool, str]:
    paths = paths_for(root)
    agent_id = resolve_agent(agent)
    body = text.strip()
    if not body.startswith("- "):
        body = f"- {body}"
    with memory_lock(paths.root):
        if not paths.tattoos.exists():
            _atomic_write(paths.tattoos, "# Tattoos\n")
        return _append_eof(paths.tattoos, sess, "tattoo", body, agent=agent_id)


def project_edit(
    body: str,
    *,
    sess: str,
    root: Path,
    project: Path,
    section: str = "## State",
    flow_start: Optional[str] = None,
    agent: Optional[str] = None,
    mode: str = "auto",
) -> Tuple[bool, str]:
    if mode not in {"auto", "append", "replace"}:
        raise ValueError("mode must be auto, append, or replace")
    paths = paths_for(root)
    note_id = f"{sess}.project.{_hash8(section + body)}"
    marker = format_delta_marker(note_id, agent=resolve_agent(agent))
    with memory_lock(paths.root):
        path = ensure_project_memory(project)
        existing = path.read_text(encoding="utf-8")
        if note_id in existing:
            return False, _find_existing_marker(existing, note_id) or marker
        existing_section = extract_section_body(existing, section)
        if mode == "append":
            updated = append_section(existing, section, body, marker)
        else:
            preserve_existing = mode == "auto" and section_changed_since(existing_section, flow_start)
            if mode == "auto" and not preserve_existing:
                existing_delta_ids = delta_note_ids(existing_section)
                body_delta_ids = delta_note_ids(body)
                dropped = sorted(existing_delta_ids - body_delta_ids)
                if dropped:
                    raise ValueError(
                        "project-edit auto mode would drop existing delta markers; choose --append or --replace"
                    )
            updated = replace_section(
                existing,
                section,
                body,
                marker,
                preserve_existing=preserve_existing,
            )
        _atomic_write(path, updated)
        return True, marker
