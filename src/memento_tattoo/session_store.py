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
    _validate_session_id(sess)
    for name, value in (("date", date), ("agent", agent if agent is not None else ""), ("significance", significance),
                        *(("topic", topic) for topic in topics)):
        if not isinstance(value, str) or re.search(r"[\x00-\x1f\x7f|\[\]]", value):
            raise ValueError(f"invalid session header {name}")
    parse_session_date(date)
    block = (
        "---\n"
        f"[{sess} | {date} | {normalize_agent(agent)} | {', '.join(topics)} | {significance}]\n"
        f"Accomplished: {accomplished}\n"
        f"Started: {started}\n"
        f"Pending: {pending}\n"
        f"Insights: {insights}\n"
        f"Files: {'; '.join(files)}\n"
        "---\n"
    )
    _validate_session_block(block, sess)
    return block


def _validate_session_id(sess: str) -> None:
    if not isinstance(sess, str) or not re.fullmatch(r"sess_[A-Za-z0-9_]+", sess):
        raise ValueError("session id must match sess_[A-Za-z0-9_]+")


def _validate_session_block(block: str, sess: str) -> None:
    """Validate serialized input before even creating the root lock directory."""
    _validate_session_id(sess)
    if not isinstance(block, str) or "\r" in block or "\x00" in block:
        raise ValueError("invalid session block")
    lines = block.splitlines()
    if len(lines) < 4 or lines[0] != "---" or lines[-1] != "---":
        raise ValueError("session block must have opening and closing delimiters")
    if not re.fullmatch(r"\[[^\[\]]+\]", lines[1]):
        raise ValueError("invalid session header")
    if re.search(r"[\x00-\x1f\x7f]", lines[1]):
        raise ValueError("invalid session header control character")
    parts = [part.strip() for part in lines[1][1:-1].split("|")]
    if len(parts) != 5 or parts[0] != sess or not parts[2] or parts[4] not in {"low", "medium", "high"}:
        raise ValueError("invalid session header or mismatched session id")
    parse_session_date(parts[1])
    labels = []
    for line in lines[2:-1]:
        if line.strip() == "---" or re.fullmatch(r"\[.*\]\s*", line):
            raise ValueError("session narrative contains a reserved record delimiter")
        match = re.match(rf"^({_FIELD_NAMES}):", line, re.IGNORECASE)
        if match:
            labels.append(match.group(1).lower())
    if labels != [name.lower() for name in _FIELD_NAMES.split("|")]:
        raise ValueError("session fields must occur exactly once in canonical order")


def validate_session_destination(root: Path, sess: str) -> Path:
    _validate_session_id(sess)
    paths = paths_for(root)
    sessions = paths.sessions.resolve()
    path = paths.sessions / f"{sess}.md"
    if not sessions.is_relative_to(paths.root) or not path.resolve().is_relative_to(sessions):
        raise ValueError("session destination escapes memory root or sessions directory")
    return path


def write_session_block(root: Path, block: str, sess: str) -> Path:
    _validate_session_block(block, sess)
    paths = paths_for(root)
    path = validate_session_destination(paths.root, sess)
    with memory_lock(paths.root):
        validate_session_destination(paths.root, sess)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == block:
                return path
            raise FileExistsError(f"session file already exists with different content: {path}")
        for record in load_sessions(paths.root):
            if record.sess == sess:
                if record.path.read_text(encoding="utf-8") == block:
                    return record.path
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
        rf"^{re.escape(field_name)}:[ \t]*(.*?)(?=\n(?:{_FIELD_NAMES}):|\n---[ \t]*(?:\n|\Z)|\Z)",
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
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
