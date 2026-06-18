from __future__ import annotations

import os
import re
import shutil
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
_ENTRY_RE = re.compile(r"<!--\s*registry-entry\s+(?P<attrs>.*?)\s*-->\n(?P<line>.*?)(?=\n<!--\s*registry-|$)", re.DOTALL)


@dataclass(frozen=True)
class RegistryDelta:
    path: Path
    sess: str
    action: str
    slug: str
    agent: str
    ts: str
    line: str


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
) -> Path:
    action = action.strip().lower()
    if action not in _ACTIONS:
        raise ValueError(f"registry action must be one of {', '.join(sorted(_ACTIONS))}")
    paths = paths_for(root)
    timestamp = ts or now_iso()
    safe_ts = _safe_ts(timestamp)
    normalized_slug = slugify(slug)
    token = uuid.uuid4().hex[:8]
    final = paths.queue / f"{safe_ts}.{sess}.{normalized_slug}.{token}.registry.md"
    partial = final.with_suffix(final.suffix + ".partial")
    final.parent.mkdir(parents=True, exist_ok=True)
    body = (
        f"<!-- registry-delta sess={sess} action={action} slug={normalized_slug} "
        f"agent={resolve_agent(agent)} ts={timestamp} -->\n"
        f"{line.rstrip()}\n"
    )
    partial.write_text(body, encoding="utf-8")
    partial.replace(final)
    return final


def drain(root: Path, timeout: float = 10.0) -> DrainResult:
    paths = paths_for(root)
    generated = build_generated_files(paths.root)
    applied = 0
    conflicts = 0
    errors: list[str] = []
    try:
        with memory_lock(paths.root, timeout=timeout):
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
                winners, losers = _choose_winners(deltas)
                entries = _parse_registry(paths.registry)
                for delta in winners:
                    entries[delta.slug] = _entry_from_delta(delta, losers_by_slug=losers)
                    applied += 1
                _write_registry(paths.registry, entries)
                for path, text in generated.items():
                    _atomic_write(path, text)
                for delta in winners:
                    _move_delta(delta.path, paths.queue / "applied")
                for loser in [delta for group in losers.values() for delta in group]:
                    _move_delta(loser.path, paths.queue / "conflicts")
                    conflicts += 1
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
    return RegistryDelta(
        path=path,
        sess=attrs.get("sess", ""),
        action=attrs.get("action", ""),
        slug=slugify(attrs.get("slug", "")),
        agent=attrs.get("agent", "unknown"),
        ts=attrs.get("ts", ""),
        line=line,
    )


def _parse_registry(path: Path) -> dict[str, RegistryEntry]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    entries: dict[str, RegistryEntry] = {}
    for match in _ENTRY_RE.finditer(text):
        attrs = _parse_attrs(match.group("attrs"))
        slug = slugify(attrs.get("slug", ""))
        entries[slug] = RegistryEntry(
            slug=slug,
            status=attrs.get("status", "active"),
            updated=attrs.get("updated", ""),
            agent=attrs.get("agent", "unknown"),
            sess=attrs.get("sess", ""),
            line=match.group("line").strip(),
        )
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
        lines.append(
            f"<!-- registry-entry slug={entry.slug} status={entry.status} "
            f"updated={entry.updated} agent={entry.agent} sess={entry.sess} -->"
        )
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
