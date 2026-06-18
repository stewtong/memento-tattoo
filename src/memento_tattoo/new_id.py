from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import paths_for
from .lock import memory_lock


_RESERVATION_TTL = timedelta(hours=24)


def taken_session_ids(root: Path) -> set[str]:
    paths = paths_for(root)
    taken = _session_file_ids(paths.sessions)
    taken.update(_active_reservations(paths.reserved_ids, taken))
    return taken


def generate_session_id(root: Path) -> str:
    paths = paths_for(root)
    with memory_lock(paths.root):
        existing_files = _session_file_ids(paths.sessions)
        _write_reservations(paths.reserved_ids, _kept_reservations(paths.reserved_ids, existing_files))
        while True:
            sid = f"sess_{secrets.token_hex(2)}"
            taken = existing_files | _active_reservations(paths.reserved_ids, existing_files)
            if sid in taken:
                continue
            _append_reservation(paths.reserved_ids, sid)
            return sid


def prune_reservations(root: Path) -> int:
    paths = paths_for(root)
    with memory_lock(paths.root):
        existing_files = _session_file_ids(paths.sessions)
        before = _reservation_lines(paths.reserved_ids)
        kept = _kept_reservations(paths.reserved_ids, existing_files)
        _write_reservations(paths.reserved_ids, kept)
    return len(before) - len(kept)


def _session_file_ids(sessions: Path) -> set[str]:
    ids = {path.stem for path in sessions.glob("sess_*.md")}
    ids.update(path.stem for path in (sessions / "archive").glob("sess_*.md"))
    return ids


def _active_reservations(path: Path, existing_files: set[str]) -> set[str]:
    return {sid for sid, _expiry in _kept_reservations(path, existing_files)}


def _kept_reservations(path: Path, existing_files: set[str]) -> list[tuple[str, str]]:
    now = _now()
    kept: list[tuple[str, str]] = []
    for sid, expiry_text in _reservation_lines(path):
        if sid in existing_files:
            continue
        expiry = _parse_iso(expiry_text)
        if expiry is None or expiry <= now:
            continue
        kept.append((sid, expiry_text))
    return kept


def _reservation_lines(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    lines: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        parts = raw.split()
        if len(parts) >= 2 and parts[0].startswith("sess_"):
            lines.append((parts[0], parts[1]))
    return lines


def _append_reservation(path: Path, sid: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    expiry = (_now() + _RESERVATION_TTL).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{sid} {expiry}\n")


def _write_reservations(path: Path, reservations: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(f"{sid} {expiry}\n" for sid, expiry in reservations)
    path.write_text(text, encoding="utf-8")


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)
