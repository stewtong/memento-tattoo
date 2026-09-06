from __future__ import annotations

import os
import hashlib
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from ._time import now_iso
from .agent import resolve_agent
from .config import paths_for
from .lock import LockTimeout, memory_lock
from .rebuild import build_generated_files


_ACTIONS = {"add", "update", "archive"}
_DELTA_RE = re.compile(r"<!--\s*registry-delta\s+(?P<attrs>.*?)\s*-->")
_ENTRY_RE = re.compile(r"<!--\s*registry-entry\s+(?P<attrs>.*?)\s*-->")


@dataclass(frozen=True)
class RegistryDelta:
    path: Path
    sess: str
    action: str
    slug: str
    agent: str
    ts: str
    line: str
    expected_sha256: str | None = None


@dataclass(frozen=True)
class RegistryEntry:
    slug: str
    status: str
    updated: str
    agent: str
    sess: str
    line: str
    conflict_comment: str = ""


@dataclass(frozen=True)
class DrainResult:
    applied: int = 0
    conflicts: int = 0
    skipped: bool = False
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.skipped and not self.errors

    def render(self) -> str:
        if self.skipped:
            return "drain skipped: lock unavailable"
        lines = [f"drain applied={self.applied} conflicts={self.conflicts}"]
        lines.extend(f"error: {error}" for error in self.errors)
        return "\n".join(lines)


def slugify(value: str) -> str:
    raw = value.strip().lower()
    raw = re.sub(r"[^a-z0-9]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw or "unnamed"


def registry_queue(
    sess: str,
    action: str,
    slug: str,
    line: str,
    root: Path,
    agent: str | None = None,
    ts: str | None = None,
    expected_line: str | None = None,
) -> Path:
    action = action.strip().lower()
    if action not in _ACTIONS:
        raise ValueError(f"registry action must be one of {', '.join(sorted(_ACTIONS))}")
    paths = paths_for(root)
    validate_registry_delta(sess, action, slug, line)
    expected_sha256 = expected_line_hash(expected_line)
    with memory_lock(paths.root):
        prior = registry_receipt(paths.root, sess, action, slug, line, agent=agent)
        if prior is not None:
            return prior
        _check_expected(_parse_registry(paths.registry).get(slugify(slug)), expected_sha256, sess, action, line)
        timestamp = ts or now_iso()
        safe_ts = _safe_ts(timestamp)
        normalized_slug = slugify(slug)
        token = uuid.uuid4().hex[:8]
        final = paths.queue / f"{safe_ts}.{sess}.{normalized_slug}.{token}.registry.md"
        body = (
            f"<!-- registry-delta sess={sess} action={action} slug={normalized_slug} "
            f"agent={resolve_agent(agent)} ts={timestamp}"
            f"{' expected_sha256=' + expected_sha256 if expected_sha256 is not None else ''} -->\n"
            f"{line.rstrip()}\n"
        )
        _atomic_write(final, body)
        return final


def validate_registry_delta(sess: str, action: str, slug: str, line: str) -> None:
    if not re.fullmatch(r"sess_\w+", sess):
        raise ValueError("invalid registry session id")
    if action not in _ACTIONS or not slug.strip():
        raise ValueError("invalid registry action or slug")
    if not line.strip() or len(line.strip().splitlines()) != 1:
        raise ValueError("registry line must be a nonempty single line")
    if re.search(r"<!--\s*registry-", line):
        raise ValueError("registry line cannot contain registry metadata")


def expected_line_hash(line: str | None) -> str | None:
    if line is None:
        return None
    if not isinstance(line, str) or "\n" in line or "\r" in line:
        raise ValueError("expected_line must be one line; empty means absent")
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _check_expected(entry: RegistryEntry | None, expected: str | None, sess: str, action: str, line: str) -> None:
    if expected is None:
        return
    current = entry.line if entry is not None else ""
    recovery = entry is not None and entry.sess == sess and entry.line == (_archive_line(line.strip()) if action == "archive" else line.strip()) and entry.status == ("archived" if action == "archive" else "active")
    if expected_line_hash(current) != expected and not recovery:
        raise ValueError("stale registry delta; reread and reconcile the current entry")


def preflight_registry(root: Path, sess: str, action: str, slug: str, line: str, expected_line: str | None) -> None:
    expected = expected_line_hash(expected_line)
    paths = paths_for(root)
    with memory_lock(paths.root):
        _check_expected(_parse_registry(paths.registry).get(slugify(slug)), expected, sess, action, line)


def registry_receipt(root: Path, sess: str, action: str, slug: str, line: str, *, agent: str | None = None) -> Path | None:
    queue = paths_for(root).queue
    for folder in (queue, queue / "applied", queue / "applied/archive", queue / "conflicts", queue / "conflicts/archive"):
        for path in folder.glob(f"*.{sess}.{slugify(slug)}.*.registry.md"):
            delta = _parse_delta(path)
            if (delta.sess, delta.action, delta.slug, delta.line, delta.agent) == (sess, action, slugify(slug), line.strip(), resolve_agent(agent)):
                return path
    return None


APPLIED_KEEP = 100
"""How many drained delta files to retain in applied/ as a provenance audit trail.
Older receipts move to archive/ and remain available for replay checks."""


def prune_applied(applied_dir: Path, keep: int = APPLIED_KEEP) -> int:
    """Archive all but the newest `keep` receipts; preserve replay evidence."""
    if not applied_dir.exists():
        return 0
    files = [p for p in applied_dir.glob("*.registry.md") if p.is_file()]
    if len(files) <= keep:
        return 0
    files.sort(key=lambda p: (p.stat().st_mtime, p.name))
    removed = 0
    for p in files[: len(files) - keep]:
        try:
            target = applied_dir / "archive" / p.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise FileExistsError(f"receipt archive collision: {target}")
            p.replace(target)
            removed += 1
        except FileNotFoundError:
            pass
    return removed


CONFLICT_HOT_DAYS = 30
CONFLICT_HOT_MAX = 200


def conflict_archive_candidates(
    root: Path,
    *,
    days: int = CONFLICT_HOT_DAYS,
    max_hot: int = CONFLICT_HOT_MAX,
) -> list[Path]:
    conflict_dir = paths_for(root).queue / "conflicts"
    files = sorted(
        (path for path in conflict_dir.glob("*.registry.md") if path.is_file()),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    cutoff = time.time() - days * 86400
    by_age = {path for path in files if path.stat().st_mtime < cutoff}
    excess = set(files[: max(0, len(files) - max_hot)]) if max_hot > 0 else set(files)
    return sorted(by_age | excess, key=lambda path: (path.stat().st_mtime, path.name))


def archive_registry_conflicts(
    root: Path,
    *,
    days: int = CONFLICT_HOT_DAYS,
    max_hot: int = CONFLICT_HOT_MAX,
    assume_locked: bool = False,
) -> int:
    paths = paths_for(root)

    def _do() -> int:
        candidates = conflict_archive_candidates(paths.root, days=days, max_hot=max_hot)
        archive = paths.queue / "conflicts/archive"
        for source in candidates:
            destination = archive / source.name
            if destination.exists():
                raise FileExistsError(destination)
        archive.mkdir(parents=True, exist_ok=True)
        for source in candidates:
            os.replace(source, archive / source.name)
        return len(candidates)

    if assume_locked:
        return _do()
    with memory_lock(paths.root):
        return _do()


def drain(root: Path, timeout: float = 10.0, *, rebuild_indexes: bool = True) -> DrainResult:
    paths = paths_for(root)
    applied = 0
    conflicts = 0
    errors: list[str] = []
    try:
        with memory_lock(paths.root, timeout=timeout):
            generated = build_generated_files(paths.root) if rebuild_indexes else {}
            while True:
                queue_files = sorted(paths.queue.glob("*.registry.md"), key=lambda path: path.name)
                if not queue_files:
                    break
                deltas = []
                for path in queue_files:
                    try:
                        deltas.append(_parse_delta(path))
                    except ValueError as exc:
                        errors.append(str(exc))
                if errors:
                    break
                try:
                    entries = _parse_registry(paths.registry)
                except ValueError as exc:
                    errors.append(str(exc))
                    break
                winners, losers = _choose_winners(deltas)
                try:
                    for delta in winners:
                        _check_expected(entries.get(delta.slug), delta.expected_sha256, delta.sess, delta.action, delta.line)
                except ValueError as exc:
                    errors.append(str(exc))
                    break
                for delta in winners:
                    entries[delta.slug] = _entry_from_delta(delta, losers_by_slug=losers)
                    applied += 1
                _write_registry(paths.registry, entries)
                for path, text in generated.items():
                    if not path.exists() or path.read_text(encoding="utf-8") != text:
                        _atomic_write(path, text)
                for delta in winners:
                    _move_delta(delta.path, paths.queue / "applied")
                for loser in [delta for group in losers.values() for delta in group]:
                    _move_delta(loser.path, paths.queue / "conflicts")
                    conflicts += 1
            if not errors:
                prune_applied(paths.queue / "applied")  # bound the provenance audit trail
                archive_registry_conflicts(paths.root, assume_locked=True)
    except LockTimeout:
        return DrainResult(skipped=True)
    return DrainResult(applied=applied, conflicts=conflicts, errors=tuple(errors))


def _choose_winners(deltas: list[RegistryDelta]) -> tuple[list[RegistryDelta], dict[str, list[RegistryDelta]]]:
    by_slug: dict[str, list[RegistryDelta]] = {}
    for delta in deltas:
        by_slug.setdefault(delta.slug, []).append(delta)
    winners: list[RegistryDelta] = []
    losers: dict[str, list[RegistryDelta]] = {}
    for slug, items in by_slug.items():
        ordered = sorted(items, key=lambda item: (item.ts, item.path.name))
        winners.append(ordered[-1])
        if len(ordered) > 1:
            losers[slug] = ordered[:-1]
    return sorted(winners, key=lambda item: (item.ts, item.path.name)), losers


def _parse_delta(path: Path) -> RegistryDelta:
    text = path.read_text(encoding="utf-8")
    match = _DELTA_RE.search(text)
    if not match:
        raise ValueError(f"unreadable registry delta header: {path}")
    attrs = _parse_attrs(match.group("attrs"))
    line = text[match.end() :].strip()
    missing = [key for key in ("sess", "action", "slug", "agent", "ts") if not attrs.get(key)]
    if missing or attrs.get("action") not in _ACTIONS or not line:
        detail = ", ".join(missing) if missing else "invalid action or empty line"
        raise ValueError(f"invalid registry delta {path}: {detail}")
    validate_registry_delta(attrs["sess"], attrs["action"], attrs["slug"], line)
    expected = attrs.get("expected_sha256")
    if expected is not None and not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError(f"invalid expected hash: {path}")
    return RegistryDelta(
        path=path,
        sess=attrs.get("sess", ""),
        action=attrs.get("action", ""),
        slug=slugify(attrs.get("slug", "")),
        agent=attrs.get("agent", "unknown"),
        ts=attrs.get("ts", ""),
        line=line,
        expected_sha256=expected,
    )


def _parse_registry(path: Path) -> dict[str, RegistryEntry]:
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: dict[str, RegistryEntry] = {}
    index = 0
    comments: list[str] = []
    while index < len(lines):
        raw = lines[index].strip()
        index += 1
        if not raw or (raw == "# Registry" and not any(line.strip() for line in lines[:index - 1])):
            continue
        if re.fullmatch(r"<!--\s*registry-conflict\s+[^<>]*\s*-->", raw):
            comments.append(raw)
            continue
        match = _ENTRY_RE.fullmatch(raw)
        if match is None or index == len(lines):
            raise ValueError(f"unreadable registry entry at line {index}: {path}")
        attrs = _parse_attrs(match.group("attrs"))
        tokens = match.group("attrs").split()
        if (not attrs.get("slug") or len(tokens) != len(attrs)
                or any(not re.fullmatch(r"[a-zA-Z_][\w-]*=[^\s<>]+", token) for token in tokens)
                or set(attrs) - {"slug", "status", "updated", "agent", "sess"}
                or attrs.get("status", "active") not in ("active", "archived")):
            raise ValueError(f"invalid registry entry at line {index}: {path}")
        slug = slugify(attrs.get("slug", ""))
        line = lines[index].strip()
        index += 1
        if slug in entries or not line or re.search(r"<!--\s*registry-", line):
            raise ValueError(f"duplicate or malformed registry entry at line {index}: {path}")
        entries[slug] = RegistryEntry(
            slug=slug,
            status=attrs.get("status", "active"),
            updated=attrs.get("updated", ""),
            agent=attrs.get("agent", "unknown"),
            sess=attrs.get("sess", ""),
            line=line,
            conflict_comment="\n".join(comments),
        )
        comments.clear()
    if comments:
        raise ValueError(f"registry conflict has no entry: {path}")
    return entries


def _entry_from_delta(delta: RegistryDelta, *, losers_by_slug: dict[str, list[RegistryDelta]]) -> RegistryEntry:
    status = "archived" if delta.action == "archive" else "active"
    line = _archive_line(delta.line) if delta.action == "archive" else delta.line
    loser_comments = [
        f"<!-- registry-conflict slug={delta.slug} loser={loser.path.name} -->"
        for loser in losers_by_slug.get(delta.slug, [])
    ]
    return RegistryEntry(
        slug=delta.slug,
        status=status,
        updated=delta.ts,
        agent=delta.agent,
        sess=delta.sess,
        line=line,
        conflict_comment="\n".join(loser_comments),
    )


def _write_registry(path: Path, entries: dict[str, RegistryEntry]) -> None:
    lines = ["# Registry", ""]
    for slug in sorted(entries):
        entry = entries[slug]
        if entry.conflict_comment:
            lines.append(entry.conflict_comment)
        attrs = {"slug": entry.slug, "status": entry.status, "updated": entry.updated,
                 "agent": entry.agent, "sess": entry.sess}
        # Legacy entries may omit provenance; do not invent it or serialize an
        # empty attribute, which would make the next parse fail.
        header = " ".join(f"{key}={value}" for key, value in attrs.items() if value)
        lines.append(f"<!-- registry-entry {header} -->")
        lines.append(entry.line)
        lines.append("")
    _atomic_write(path, "\n".join(lines).rstrip() + "\n")


def _archive_line(line: str) -> str:
    prefix = line.rsplit(" - ", 1)[0] if " - " in line else line
    return f"{prefix} - archived"


def _move_delta(path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if target.exists():
        target = target_dir / f"{path.stem}.{uuid.uuid4().hex[:8]}{path.suffix}"
    shutil.move(str(path), str(target))


def _safe_ts(ts: str) -> str:
    return re.sub(r"[^0-9TZ]", "", ts).replace("T", "T")[:16] or "00000000T000000Z"


def _parse_attrs(text: str) -> dict[str, str]:
    return {key: value for key, value in re.findall(r"([a-zA-Z_][\w-]*)=([^\s>]+)", text)}


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
