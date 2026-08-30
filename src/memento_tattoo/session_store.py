from __future__ import annotations

import re
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .agent import normalize_agent
from .config import paths_for
from .lock import memory_lock


_FIELD_NAMES = "Accomplished|Started|Pending|Insights|Files"


@dataclass(frozen=True)
class SessionRecord:
    sess: str
    date: str
    agent: str
    topics: list[str]
    significance: str
    accomplished: str
    started: str
    pending: str
    insights: str
    files: list[str]
    path: Path


def session_source_files(root: Path) -> list[Path]:
    sessions = paths_for(root).sessions
    files = list(sessions.glob("sess_*.md"))
    files.extend((sessions / "archive").glob("sess_*.md"))
    return sorted(files, key=lambda path: str(path))


def render_session_block(
    sess: str,
    *,
    date: str,
    agent: str,
    topics: list[str],
    significance: str,
    accomplished: str,
    started: str,
    pending: str,
    insights: str,
    files: list[str],
) -> str:
    parse_session_date(date)
    return (
        "---\n"
        f"[{sess} | {date} | {normalize_agent(agent)} | {', '.join(topics)} | {significance}]\n"
        f"Accomplished: {accomplished}\n"
        f"Started: {started}\n"
        f"Pending: {pending}\n"
        f"Insights: {insights}\n"
        f"Files: {'; '.join(files)}\n"
        "---\n"
    )


def write_session_block(root: Path, block: str, sess: str) -> Path:
    paths = paths_for(root)
    path = paths.sessions / f"{sess}.md"
    with memory_lock(paths.root):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == block:
                return path
            raise FileExistsError(f"session file already exists with different content: {path}")
        for record in load_sessions(paths.root):
            if record.sess == sess:
                raise FileExistsError(f"session id already exists in another source: {record.path}")
        _atomic_write(path, block)
    return path


def load_sessions(root: Path) -> list[SessionRecord]:
    records = [parse_session_file(path) for path in session_source_files(root)]
    return sorted(records, key=lambda record: (parse_session_date(record.date), record.sess))


def duplicate_session_ids(root: Path) -> dict[str, list[SessionRecord]]:
    grouped: dict[str, list[SessionRecord]] = {}
    for record in load_sessions(root):
        grouped.setdefault(record.sess, []).append(record)
    return {sess: records for sess, records in grouped.items() if len(records) > 1}


def parse_session_file(path: Path) -> SessionRecord:
    text = path.read_text(encoding="utf-8")
    header_matches = re.findall(r"^\[(.+?)\]\s*$", text, re.MULTILINE)
    if not header_matches:
        raise ValueError(f"missing session header: {path}")
    if len(header_matches) != 1:
        raise ValueError(f"expected exactly one session record: {path}")
    parts = [part.strip() for part in header_matches[0].split("|")]
    if len(parts) >= 5:
        sess, date, agent, topics, significance = parts[:5]
    elif len(parts) == 3:
        sess, date, topics = parts
        agent = "grandfathered"
        significance = "unknown"
    else:
        raise ValueError(f"invalid session header: {path}")
    try:
        parse_session_date(date)
    except ValueError as exc:
        raise ValueError(f"invalid session date in {path}: {date}") from exc
    return SessionRecord(
        sess=sess,
        date=date,
        agent=normalize_agent(agent),
        topics=_csv(topics),
        significance=significance or "unknown",
        accomplished=_extract_field(text, "Accomplished"),
        started=_extract_field(text, "Started"),
        pending=_extract_field(text, "Pending"),
        insights=_extract_field(text, "Insights"),
        files=_semi(_extract_field(text, "Files")),
        path=path,
    )


def parse_session_date(value: str) -> datetime:
    text = value.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[ T])", text):
        raise ValueError(f"invalid session date: {value}")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid session date: {value}") from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _extract_field(text: str, field_name: str) -> str:
    pattern = re.compile(
        rf"^{re.escape(field_name)}:\s*(.*?)(?=\n(?:{_FIELD_NAMES}):|\n---\s*$|$)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _csv(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _semi(text: str) -> list[str]:
    return [item.strip() for item in text.split(";") if item.strip()]


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
