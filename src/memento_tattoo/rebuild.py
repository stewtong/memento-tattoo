from __future__ import annotations

import os
import uuid
from pathlib import Path

from .config import paths_for
from .lock import memory_lock
from .session_store import SessionRecord, load_sessions


def build_generated_files(root: Path) -> dict[Path, str]:
    paths = paths_for(root)
    records = load_sessions(paths.root)
    return {
        paths.sessions / "index.md": _render_index(records),
        paths.sessions / "index-recent.md": _render_recent(records),
    }


def rebuild(root: Path, *, check: bool = False) -> tuple[bool, str]:
    paths = paths_for(root)
    generated = build_generated_files(paths.root)
    changed = [path for path, text in generated.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
    if check:
        if changed:
            rel = ", ".join(path.name for path in changed)
            return False, f"session indexes stale; would change: {rel}"
        return True, "session indexes current"

    with memory_lock(paths.root):
        for path, text in generated.items():
            _atomic_write(path, text)
    return True, f"rebuilt session indexes: {len(generated)} files"


def _render_index(records: list[SessionRecord]) -> str:
    lines = ["# Session Index", ""]
    if not records:
        lines.append("- none")
    for record in sorted(records, key=lambda item: (item.sess, item.date)):
        lines.append(_record_line(record))
    return "\n".join(lines).rstrip() + "\n"


def _render_recent(records: list[SessionRecord]) -> str:
    lines = ["# Recent Sessions", ""]
    if not records:
        lines.append("- none")
    for record in sorted(records, key=lambda item: (item.date, item.sess), reverse=True)[:50]:
        lines.append(_record_line(record))
    return "\n".join(lines).rstrip() + "\n"


def _record_line(record: SessionRecord) -> str:
    topics = ", ".join(record.topics) if record.topics else "none"
    accomplished = record.accomplished or "none"
    return f"- `{record.sess}` | {record.date} | {record.agent} | {topics} | {record.significance} | {accomplished}"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
