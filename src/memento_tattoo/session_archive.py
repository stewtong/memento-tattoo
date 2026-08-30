from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .config import paths_for
from .lock import memory_lock
from .rebuild import _rebuild_locked
from .session_store import SessionRecord, load_sessions, parse_session_file


@dataclass(frozen=True)
class ArchiveMove:
    source: Path
    destination: Path
    session_id: str
    session_date: str


def archive_candidates(
    root: Path,
    *,
    days: int,
    today: date | None = None,
    limit: int = 100,
) -> list[ArchiveMove]:
    if days < 0:
        raise ValueError("days must be nonnegative")
    if limit < 0:
        raise ValueError("limit must be nonnegative")

    paths = paths_for(root)
    cutoff = (today or date.today()) - timedelta(days=days)
    moves: list[ArchiveMove] = []
    for source in paths.sessions.glob("sess_*.md"):
        record = parse_session_file(source)
        parsed_date = _session_date(record)
        if parsed_date >= cutoff:
            continue
        moves.append(
            ArchiveMove(
                source=source,
                destination=paths.sessions / "archive" / source.name,
                session_id=record.sess,
                session_date=record.date,
            )
        )

    moves.sort(key=lambda move: (_date_prefix(move.session_date), move.session_id, str(move.source)))
    return moves if limit == 0 else moves[:limit]


def apply_archive(moves: list[ArchiveMove], root: Path) -> int:
    if not moves:
        return 0

    paths = paths_for(root)
    archive_dir = paths.sessions / "archive"
    index_snapshot: dict[Path, bytes | None] = {}
    source_snapshot: dict[Path, bytes] = {}
    moved: list[ArchiveMove] = []
    with memory_lock(paths.root):
        archive_dir_preexisting = archive_dir.exists()
        for move in moves:
            if not move.source.exists():
                raise FileNotFoundError(move.source)
            if move.destination.exists():
                raise FileExistsError(move.destination)
        records = load_sessions(paths.root)
        _validate_batch(paths.root, moves, records)
        index_snapshot = _snapshot_indexes(paths.sessions)
        source_snapshot = {move.source: move.source.read_bytes() for move in moves}
        try:
            archive_dir.mkdir(parents=True, exist_ok=True)
            if archive_dir.stat().st_dev != paths.sessions.stat().st_dev:
                raise OSError("session archive must be on the same filesystem as hot sessions")
            for move in moves:
                os.rename(move.source, move.destination)
                moved.append(move)
        except Exception as exc:
            rollback_errors = _rollback(
                moves,
                moved,
                source_snapshot,
                index_snapshot,
                paths.root,
                archive_dir,
                archive_dir_preexisting,
            )
            raise _archive_failure(exc, rollback_errors) from exc
        try:
            ok, output = _rebuild_locked(paths.root)
            if not ok:
                raise RuntimeError(f"session index rebuild failed: {output}")
            verified, verification = _rebuild_locked(paths.root, check=True)
            if not verified:
                raise RuntimeError(f"session index rebuild verification failed: {verification}")
        except Exception as exc:
            rollback_errors = _rollback(
                moves,
                moved,
                source_snapshot,
                index_snapshot,
                paths.root,
                archive_dir,
                archive_dir_preexisting,
            )
            raise _archive_failure(exc, rollback_errors) from exc
    return len(moves)


def render_archive_plan(moves: list[ArchiveMove], root: Path, *, applied: bool = False) -> str:
    mode = "APPLY" if applied else "DRY_RUN"
    lines = [f"SESSION_ARCHIVE {mode} {len(moves)} candidate(s)"]
    for move in moves:
        lines.append(
            f"{move.session_id}\t{move.session_date}\t"
            f"{move.source.relative_to(root)} -> {move.destination.relative_to(root)}"
        )
    return "\n".join(lines)


def _validate_batch(root: Path, moves: list[ArchiveMove], records: list[SessionRecord]) -> None:
    source_keys = [str(move.source.resolve()) for move in moves]
    if len(source_keys) != len(set(source_keys)):
        raise ValueError("archive batch contains duplicate sources")
    destination_keys = [str(move.destination.resolve()) for move in moves]
    if len(destination_keys) != len(set(destination_keys)):
        raise ValueError("archive batch contains duplicate destinations")
    session_ids = [move.session_id for move in moves]
    if len(session_ids) != len(set(session_ids)):
        raise ValueError("archive batch contains duplicate session IDs")

    grouped: dict[str, list[SessionRecord]] = {}
    for record in records:
        grouped.setdefault(record.sess, []).append(record)
    duplicates = sorted(sess for sess, matching in grouped.items() if len(matching) > 1)
    if duplicates:
        raise ValueError(f"conflicting session IDs must be repaired before archival: {', '.join(duplicates)}")

    sessions_dir = paths_for(root).sessions.resolve()
    for move in moves:
        if not move.source.exists():
            raise FileNotFoundError(move.source)
        if move.source.parent.resolve() != sessions_dir:
            raise ValueError(f"archive source is not a hot session file: {move.source}")
        if move.destination.parent.resolve() != sessions_dir / "archive":
            raise ValueError(f"archive destination is outside the session archive: {move.destination}")
        if move.destination.exists():
            raise FileExistsError(move.destination)
        record = parse_session_file(move.source)
        if record.sess != move.session_id or record.date != move.session_date:
            raise ValueError(f"session changed after archive selection: {move.source}")


def _session_date(record: SessionRecord) -> date:
    try:
        return date.fromisoformat(_date_prefix(record.date))
    except ValueError as exc:
        raise ValueError(f"invalid session date in {record.path}: {record.date}") from exc


def _date_prefix(value: str) -> str:
    return value[:10]


def _snapshot_indexes(sessions_dir: Path) -> dict[Path, bytes | None]:
    return {
        path: path.read_bytes() if path.exists() else None
        for path in (sessions_dir / "index.md", sessions_dir / "index-recent.md")
    }


def _rollback(
    moves: list[ArchiveMove],
    moved: list[ArchiveMove],
    source_snapshot: dict[Path, bytes],
    index_snapshot: dict[Path, bytes | None],
    root: Path,
    archive_dir: Path,
    archive_dir_preexisting: bool,
) -> list[str]:
    errors: list[str] = []
    for move in reversed(moved):
        try:
            if move.source.exists():
                raise FileExistsError(f"rollback source already exists: {move.source}")
            if not move.destination.exists():
                raise FileNotFoundError(f"rollback destination missing: {move.destination}")
            os.rename(move.destination, move.source)
        except Exception as exc:
            errors.append(str(exc))

    errors.extend(_restore_indexes(index_snapshot))

    if not archive_dir_preexisting and archive_dir.exists():
        try:
            archive_dir.rmdir()
        except Exception as exc:
            errors.append(f"could not remove created archive directory {archive_dir}: {exc}")

    errors.extend(
        _verify_rollback(
            moves,
            source_snapshot,
            index_snapshot,
            root,
            archive_dir,
            archive_dir_preexisting,
        )
    )
    return errors


def _restore_indexes(index_snapshot: dict[Path, bytes | None]) -> list[str]:
    errors: list[str] = []
    for path, content in index_snapshot.items():
        try:
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                _atomic_write_bytes(path, content)
        except Exception as exc:
            errors.append(f"could not restore {path}: {exc}")
    return errors


def _verify_rollback(
    moves: list[ArchiveMove],
    source_snapshot: dict[Path, bytes],
    index_snapshot: dict[Path, bytes | None],
    root: Path,
    archive_dir: Path,
    archive_dir_preexisting: bool,
) -> list[str]:
    errors: list[str] = []
    for move in moves:
        try:
            if not move.source.exists():
                errors.append(f"rollback verification missing source: {move.source}")
            elif move.source.read_bytes() != source_snapshot[move.source]:
                errors.append(f"rollback verification changed source bytes: {move.source}")
            if move.destination.exists():
                errors.append(f"rollback verification destination remains: {move.destination}")
        except Exception as exc:
            errors.append(f"could not verify rollback for {move.session_id}: {exc}")
    for path, content in index_snapshot.items():
        try:
            if content is None:
                if path.exists():
                    errors.append(f"rollback verification unexpected index: {path}")
            elif not path.exists() or path.read_bytes() != content:
                errors.append(f"rollback verification changed index: {path}")
        except Exception as exc:
            errors.append(f"could not verify restored index {path}: {exc}")
    try:
        current, output = _rebuild_locked(root, check=True)
        if not current:
            errors.append(f"rollback verification found stale indexes: {output}")
    except Exception as exc:
        errors.append(f"could not verify rollback indexes: {exc}")
    if not archive_dir_preexisting and archive_dir.exists():
        errors.append(f"rollback verification created archive directory remains: {archive_dir}")
    return errors


def _archive_failure(original: Exception, rollback_errors: list[str]) -> RuntimeError:
    if rollback_errors:
        detail = "; ".join(rollback_errors)
        return RuntimeError(f"session archive failed: {original}; rollback incomplete: {detail}")
    return RuntimeError(f"session archive failed: {original}; rollback verified clean")


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
