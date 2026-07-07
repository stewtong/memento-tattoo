from __future__ import annotations

import uuid
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

from .agent import format_delta_marker, parse_delta_marker, resolve_agent
from .config import paths_for
from .lock import memory_lock
from .project_memory import append_section, delta_note_ids, ensure_project_memory, extract_section_body, replace_section, section_changed_since


# The notes file is what situation-recognition greps and what a save loads
# contextually, so it must stay bounded. Rotated blocks are NOT lost: load_memento_notes
# (and thus recall + retention's classify) reads notes.md + notes_archive.md, so a rotated
# note still ranks and still covers a repeat. TARGET leaves headroom so the next note-add
# does not immediately re-trip the line.
HOT_NOTES_ROTATE_BYTES = 30 * 1024
HOT_NOTES_TARGET_BYTES = 29 * 1024

_DELTA_MARK = "<!-- delta:"


def _hash8(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:8]


def rotate_hot_notes(hot_path: Path, archive_path: Path, *, threshold: Optional[int] = None, target: Optional[int] = None) -> int:
    """Move the oldest delta-marked note blocks from the hot notes file to the cold
    archive until the hot file is at or under `target` bytes. Returns blocks moved.

    No-op (returns 0) when the hot file is missing, at/under `threshold`, or has no
    delta-marked blocks. Always keeps at least the newest block, so one over-target
    block never empties the file. Assumes any needed lock is already held; reads the
    module byte limits at call time so callers/tests can override them."""
    threshold = HOT_NOTES_ROTATE_BYTES if threshold is None else threshold
    target = HOT_NOTES_TARGET_BYTES if target is None else target
    if not hot_path.exists():
        return 0
    text = hot_path.read_text(encoding="utf-8")
    if len(text.encode("utf-8")) <= threshold:
        return 0
    first = text.find(_DELTA_MARK)
    if first == -1:
        return 0  # all preamble, nothing rotatable
    preamble, body = text[:first], text[first:]
    starts = [i for i in range(len(body)) if body.startswith(_DELTA_MARK, i)]
    blocks = [body[starts[i]:(starts[i + 1] if i + 1 < len(starts) else len(body))] for i in range(len(starts))]

    kept = list(blocks)
    moved: list[str] = []
    while len(kept) > 1 and len((preamble + "".join(kept)).encode("utf-8")) > target:
        moved.append(kept.pop(0))
    if not moved:
        return 0

    _atomic_write(hot_path, preamble + "".join(kept))
    existing = archive_path.read_text(encoding="utf-8") if archive_path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    _atomic_write(archive_path, existing + "\n" + "".join(moved))
    return len(moved)


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


_SITUATION_SIGNAL_RE = re.compile(
    r"(?i)"
    r"\b(when|after|before|once|while|if|unless)\b"
    r"|\b(fails?|failed|failing|breaks?|broke|breaking|returns?|returned|returning"
    r"|hangs?|hung|hanging|drops?|dropped|dropping|crash(es|ed|ing)?|errors?|errored"
    r"|throws?|thrown|throwing|miss(es|ed|ing)?|lies|lied|clobbers?|clobbered|clobbering"
    r"|races?|raced|racing|regress(es|ed|ing)?|silently|stale|empty|wrong|no results)\b"
    r"|['\"][^'\"]{3,}['\"]"
)
_LABEL_SHAPE_RE = re.compile(
    r"(?i)"
    r"(\bphase\s*\d)"
    r"|(\bv\d+\b.*\b(implementation|build|rollout|migration|integration|setup|refactor)\b)"
    r"|(\b(implementation|rollout|integration)\s*$)"
)


def note_situation_altitude_hint(text: str, *, root: Optional[Path] = None) -> str | None:
    """Return a non-blocking routing hint for label-shaped Situation lines."""
    situation = _first_situation_line(text)
    if not situation:
        return None
    if _SITUATION_SIGNAL_RE.search(situation):
        return None
    if not _LABEL_SHAPE_RE.search(situation):
        return None
    return (
        "situation looks like a project/phase label, not a recurring situation. if this is "
        "project status it belongs in the project's memory.md (routing test); if it's a "
        "real lesson, restate the Situation as its trigger (when X / X fails with Y)."
    )


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
    author: Optional[str] = None,
    decision: Optional[str] = None,
    covered_note_id: Optional[str] = None,
) -> Tuple[bool, str]:
    paths = paths_for(root)
    agent_id = resolve_agent(agent)
    has_retention_judgment = decision is not None or covered_note_id is not None

    if kind == "seed":
        if has_retention_judgment:
            raise ValueError("retention judgment requires correction, reflection, or pattern note")
        with memory_lock(paths.root):
            applied, marker = _append_eof(paths.notes, sess, "note", text, agent=agent_id)
            rotate_hot_notes(paths.notes, paths.notes_archive)  # keep the hot file bounded
        return applied, marker

    from ._time import now_iso
    from .retention import DECISIONS, append_retention_event, classify

    if decision is not None and decision not in DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(DECISIONS)}")

    situation = _first_situation_line(text)
    result = classify(situation, root=paths.root)
    final_decision = decision or result["suggested_decision"]
    if result["has_cover"]:
        print(
            f"possible cover: {result['cover_note_id']} "
            "(extend or supersede it instead of appending a near-duplicate)",
            file=sys.stderr,
        )
    if alt_hint := note_situation_altitude_hint(text, root=paths.root):
        print(alt_hint, file=sys.stderr)
    with memory_lock(paths.root):
        applied, marker = _append_eof(paths.notes, sess, "note", text, agent=agent_id)
        if applied and kind in ("correction", "reflection"):
            event = {
                "ts": now_iso(),
                "sess": sess,
                "kind": kind,
                "author": author,
                "situation": situation,
                "note_id": _note_id_from_marker(marker),
                "candidates": result["candidates"],
                "decision": final_decision,
                "cover_note_id": covered_note_id or result["cover_note_id"],
            }
            append_retention_event(event, root=paths.root, assume_locked=True)
        if applied:
            from .tattoo_firing import bump_tattoo_firing

            bump_tattoo_firing(text, root=paths.root, now=now_iso(), assume_locked=True)
        rotate_hot_notes(paths.notes, paths.notes_archive)  # keep the hot file bounded (every writer)
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
