from __future__ import annotations

import uuid
import json
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

from .agent import format_delta_marker, parse_delta_marker, resolve_agent
from .config import paths_for
from .lock import memory_lock
from .project_memory import append_section, delta_note_ids, extract_section_body, replace_section, section_changed_since


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

    # Preserve the destination first. A failed source replacement leaves overlap,
    # which a retry reconciles without duplicating archived blocks.
    existing = archive_path.read_text(encoding="utf-8") if archive_path.exists() else ""
    additions = []
    for block in moved:
        marker = block.splitlines()[0]
        if marker in existing:
            if block.strip() not in existing:
                raise ValueError("archive marker exists with different note content")
        else:
            additions.append(block)
    if additions:
        _atomic_write(archive_path, existing.rstrip() + "\n\n" + "".join(additions))
    _atomic_write(hot_path, preamble + "".join(kept))
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
    if kind == "note":
        archive = path.with_name("notes_archive.md")
        archived = archive.read_text(encoding="utf-8") if archive.exists() else ""
        if note_id in archived:
            return False, _find_existing_marker(archived, note_id) or marker
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


RESERVED_MARKERS = ("<!-- memento-history:", "<!-- delta:")


def _reject_reserved_markers(text: str) -> None:
    """A body containing a record marker would split or corrupt the record it lands in."""
    for marker in RESERVED_MARKERS:
        if marker in text:
            raise ValueError(f"text contains the reserved record marker {marker!r}")


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
    _reject_reserved_markers(text)
    paths = paths_for(root)
    agent_id = resolve_agent(agent)
    has_retention_judgment = decision is not None or covered_note_id is not None
    if kind in ("seed", "pattern") and has_retention_judgment:
        raise ValueError("retention judgment requires correction or reflection note")

    if kind == "seed":
        with memory_lock(paths.root):
            applied, marker = _append_eof(paths.notes, sess, "note", text, agent=agent_id)
            rotate_hot_notes(paths.notes, paths.notes_archive)  # keep the hot file bounded
        return applied, marker

    from ._time import now_iso
    from .retention import DECISIONS, append_retention_event, classify, read_retention_events, rotate_retention_log

    if decision is not None and decision not in DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(DECISIONS)}")

    situation = _first_situation_line(text)
    note_id = f"{sess}.note.{_hash8(text)}"
    result = classify(situation, root=paths.root, exclude_note_id=note_id)
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
        if kind in ("correction", "reflection") and not any(
            event.get("note_id") == note_id for event in read_retention_events(root=paths.root)
        ):
            event = {
                "ts": now_iso(),
                "sess": sess,
                "kind": kind,
                "author": author,
                "situation": situation,
                "note_id": _note_id_from_marker(marker),
                "candidates": result["candidates"],
                "decision": final_decision,
                "decision_source": "author" if decision is not None else "classifier",
                "cover_note_id": covered_note_id or result["cover_note_id"],
            }
            append_retention_event(event, root=paths.root, assume_locked=True)
        else:
            rotate_retention_log(root=paths.root, assume_locked=True)
        if applied:
            from .tattoo_firing import bump_tattoo_firing

            bump_tattoo_firing(text, root=paths.root, now=now_iso(), assume_locked=True)
        rotate_hot_notes(paths.notes, paths.notes_archive)  # keep the hot file bounded (every writer)
    return applied, marker


def tattoo_add(text: str, *, sess: str, root: Path, agent: Optional[str] = None) -> Tuple[bool, str]:
    _reject_reserved_markers(text)
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
    prepare_only: bool = False,
    require_receipt: bool = False,
) -> Tuple[bool, str]:
    """Reserve, apply and acknowledge a project edit under the root lock.

    A pending receipt permits retry only against its exact before/after bytes.
    Completed operations never rewrite state if their marker has disappeared.
    save-commit reserves before writing its session, avoiding ambiguous recovery.
    """
    if mode not in {"auto", "append", "replace"}:
        raise ValueError("mode must be auto, append, or replace")
    if not section.strip().startswith("## ") or "\n" in section:
        raise ValueError("section must be a markdown h2 such as '## State'")
    paths = paths_for(root)
    path = project.expanduser().resolve() / "memory.md"
    note_id = f"{sess}.project.{_hash8(section + body)}"
    identity = {"path": str(path), "sess": sess, "section": section, "body": body,
                "mode": mode, "flow_start": flow_start}
    receipt_key = hashlib.sha256(f"{path}\n{note_id}".encode()).hexdigest()
    receipt_path = paths.root / "_project_receipts" / f"{receipt_key}.json"
    with memory_lock(paths.root):
        existing = path.read_bytes().decode("utf-8") if path.exists() else None
        receipt = None
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if (not isinstance(receipt, dict) or receipt.get("version") != 1
                    or receipt.get("identity") != identity
                    or receipt.get("status") not in {"pending", "applied"}
                    or not isinstance(receipt.get("marker"), str)
                    or not isinstance(receipt.get("after_sha256"), str)
                    or "before_sha256" not in receipt):
                raise ValueError("invalid or conflicting project receipt; review current state and use a new session")
        marker = receipt["marker"] if receipt else format_delta_marker(note_id, agent=resolve_agent(agent))
        present = note_id in delta_note_ids(extract_section_body(existing or "", section))
        if receipt and receipt["status"] == "applied":
            if not present:
                raise ValueError("project operation was superseded; review current state and use a new session")
            return False, marker
        if receipt and _project_digest(existing) == receipt["after_sha256"]:
            receipt["status"] = "applied"
            _atomic_write(receipt_path, json.dumps(receipt, indent=2) + "\n")
            return False, marker
        if receipt and _project_digest(existing) != receipt["before_sha256"]:
            raise ValueError("pending project operation was superseded or edited; review current state and use a new session")
        if not receipt and present:
            # Bootstrap an old operation only when its marker still exists.
            marker = _find_existing_marker(existing, note_id) or marker
            receipt = {"version": 1, "identity": identity, "marker": marker, "status": "applied",
                       "before_sha256": _project_digest(existing), "after_sha256": _project_digest(existing)}
            _atomic_write(receipt_path, json.dumps(receipt, indent=2) + "\n")
            return False, marker
        if not receipt and require_receipt:
            raise ValueError("existing session has no project receipt; review current state and use a new session")

        source = existing if existing is not None else "# Project Memory\n\n## Key Decisions\n\n## State\n"
        existing_section = extract_section_body(source, section)
        if mode == "append":
            updated = append_section(source, section, body, marker)
        else:
            preserve_existing = mode == "auto" and section_changed_since(existing_section, flow_start)
            if mode == "auto" and not preserve_existing:
                dropped = sorted(delta_note_ids(existing_section) - delta_note_ids(body))
                if dropped:
                    raise ValueError(
                        "project-edit auto mode would drop existing delta markers; choose --append or --replace"
                    )
            updated = replace_section(source, section, body, marker, preserve_existing=preserve_existing)
        if receipt:
            if _project_digest(updated) != receipt["after_sha256"]:
                raise ValueError("project receipt does not match reconstructed write")
        else:
            receipt = {"version": 1, "identity": identity, "marker": marker, "status": "pending",
                       "before_sha256": _project_digest(existing), "after_sha256": _project_digest(updated)}
            _atomic_write(receipt_path, json.dumps(receipt, indent=2) + "\n")
        if prepare_only:
            return False, marker
        _atomic_write(path, updated)
        receipt["status"] = "applied"
        _atomic_write(receipt_path, json.dumps(receipt, indent=2) + "\n")
        return True, marker


def _project_digest(text: str | None) -> str | None:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None
