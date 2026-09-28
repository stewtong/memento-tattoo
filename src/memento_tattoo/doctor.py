from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import paths_for, project_memory_path
from .retention import read_retention_events
from .rebuild import rebuild
from .registry import _DELTA_RE
from .session_store import duplicate_session_ids, load_sessions
from .tattoo_audit import audit_tattoos, parse_tattoos
from .write_through import HOT_NOTES_ROTATE_BYTES


RECOMMENDED_ALIAS_COVERAGE_PERCENT = 60
RECOMMENDED_TATTOO_COUNT = 25
RECOMMENDED_TATTOO_BYTES = 7_168
RECOMMENDED_TATTOO_LENGTH = 300
# Why-field and reason-clause coverage are report-only by default; 0 disables the warning.
DEFAULT_WHY_COVERAGE_WARN = 0
DEFAULT_TATTOO_REASON_WARN = 0
TATTOO_SAMPLE_LIMIT = 3
PROJECT_STATE_HEADINGS = ("## State", "## Current state")


def run_doctor(
    root: Path,
    projects: Optional[list[Path]] = None,
    *,
    alias_coverage_warn: float = RECOMMENDED_ALIAS_COVERAGE_PERCENT,
    tattoo_count_warn: int = RECOMMENDED_TATTOO_COUNT,
    tattoo_bytes_warn: int = RECOMMENDED_TATTOO_BYTES,
    tattoo_length_warn: int = RECOMMENDED_TATTOO_LENGTH,
    why_coverage_warn: float = DEFAULT_WHY_COVERAGE_WARN,
    tattoo_reason_warn: float = DEFAULT_TATTOO_REASON_WARN,
) -> tuple[bool, str]:
    paths = paths_for(root)
    checks: list[tuple[str, str, str]] = []
    project_list = projects or []
    has_project_scope = bool(project_list)

    for label, path in (
        ("notes", paths.notes),
        ("tattoos", paths.tattoos),
    ):
        if path.exists():
            checks.append(("pass", label, f"{path.name} present"))
        else:
            status = "warn" if has_project_scope else "fail"
            checks.append((status, label, f"{path.name} missing"))

    if paths.notes.exists():
        size = paths.notes.stat().st_size
        status = "warn" if size > HOT_NOTES_ROTATE_BYTES else "pass"
        checks.append((status, "notes-size", f"{size} bytes; target {HOT_NOTES_ROTATE_BYTES}"))

    try:
        checks.append(_check_alias_coverage(paths.root, alias_coverage_warn))
    except Exception as exc:
        checks.append(("fail", "alias-coverage", f"note sources unreadable: {exc}"))

    try:
        checks.append(_check_why_coverage(paths.root, why_coverage_warn))
    except Exception as exc:
        checks.append(("fail", "why-coverage", f"note sources unreadable: {exc}"))

    if paths.project.exists():
        checks.append(("pass", "project", f"{paths.project.name} present"))
    else:
        checks.append(("warn", "project", f"{paths.project.name} missing; use adjacent project memory.md for new roots"))

    for project in project_list:
        path = project_memory_path(project)
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if "## Key Decisions" in text and _has_state_heading(text):
                checks.append(("pass", "project-memory", f"{path.name} present for {_project_label(project)}"))
            else:
                checks.append(("fail", "project-memory", f"{path.name} missing required sections for {_project_label(project)}"))
        else:
            checks.append(("fail", "project-memory", f"{path.name} missing for {_project_label(project)}"))

    if not paths.retention_log.exists():
        checks.append(("warn", "retention", "retention_log.jsonl missing"))
    else:
        try:
            events = read_retention_events(root=paths.root)
        except Exception as exc:
            checks.append(("fail", "retention", f"retention_log.jsonl unreadable: {exc}"))
        else:
            hot_bytes = paths.retention_log.stat().st_size
            status = "warn" if hot_bytes > 128 * 1024 else "pass"
            checks.append((status, "retention", _retention_detail(paths.root, events) + f"; hot bytes {hot_bytes}"))
            checks.append(_check_recall_probes(paths.root))

    if not paths.sessions.exists():
        checks.append(("warn", "sessions", "sessions dir missing"))
    else:
        try:
            sessions = load_sessions(paths.root)
        except Exception as exc:
            checks.append(("warn", "sessions", f"session parse warning: {exc}"))
        else:
            checks.append(("pass", "sessions", f"session files: {len(sessions)}"))
            duplicates = duplicate_session_ids(paths.root)
            if duplicates:
                checks.append(("fail", "session-duplicates", f"conflicting ids: {', '.join(sorted(duplicates))}"))
            else:
                checks.append(("pass", "session-duplicates", "session ids unique"))
            ok_index, index_output = rebuild(paths.root, check=True)
            if ok_index:
                checks.append(("pass", "session-index", index_output))
            else:
                checks.append(("warn", "session-index", index_output))

    expired = _expired_reservations(paths.reserved_ids)
    if expired:
        checks.append(("warn", "reserved-ids", f"expired reservations: {len(expired)}"))

    queue_files = list(paths.queue.glob("*.registry.md")) if paths.queue.exists() else []
    bad_queue = [path for path in queue_files if not _DELTA_RE.search(path.read_text(encoding="utf-8"))]
    if bad_queue:
        checks.append(("fail", "registry-queue", f"unreadable queue files: {len(bad_queue)}"))
    elif queue_files:
        checks.append(("warn", "registry-queue", f"pending deltas: {len(queue_files)}"))
    else:
        checks.append(("pass", "registry-queue", "queue empty"))

    conflicts = list((paths.queue / "conflicts").glob("*.registry.md")) if (paths.queue / "conflicts").exists() else []
    archived_conflicts = list((paths.queue / "conflicts/archive").glob("*.registry.md")) if (paths.queue / "conflicts/archive").exists() else []
    if conflicts:
        oldest_days = int((datetime.now(timezone.utc).timestamp() - min(path.stat().st_mtime for path in conflicts)) / 86400)
        status = "warn" if len(conflicts) > 200 or oldest_days > 30 else "pass"
        checks.append((status, "registry-conflicts", f"hot {len(conflicts)}, archived {len(archived_conflicts)}, oldest hot {oldest_days}d"))
    elif archived_conflicts:
        checks.append(("pass", "registry-conflicts", f"hot 0, archived {len(archived_conflicts)}"))

    if paths.tattoos.exists():
        try:
            tattoo_text = paths.tattoos.read_text(encoding="utf-8")
            checks.append(
                _check_tattoo_pressure(
                    tattoo_text,
                    count_warn=tattoo_count_warn,
                    bytes_warn=tattoo_bytes_warn,
                    length_warn=tattoo_length_warn,
                )
            )
        except Exception as exc:
            checks.append(("fail", "tattoo-pressure", f"tattoos.md unreadable: {exc}"))
        else:
            checks.append(_check_tattoo_reasons(tattoo_text, tattoo_reason_warn))
        try:
            flagged_count = sum(1 for c in audit_tattoos(root=paths.root) if c.flagged)
        except Exception as exc:
            checks.append(("fail", "tattoo-lifecycle", f"audit failed: {exc}"))
            flagged_count = 0
        if flagged_count:
            noun = "tattoo" if flagged_count == 1 else "tattoos"
            checks.append(("warn", "tattoo-lifecycle", f"{flagged_count} {noun} due for review (run tattoo-audit)"))

    firing_path = paths.root / "tattoo_firing.json"
    if firing_path.exists():
        import json
        try:
            data = json.loads(firing_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("top-level value must be an object")
        except Exception as exc:
            checks.append(("fail", "tattoo-firing", f"tattoo_firing.json unreadable: {exc}"))

    from .garden import digest_counts
    try:
        counts = digest_counts(root=paths.root, today=now_iso_date())
    except Exception as exc:
        checks.append(("fail", "gardening", f"note sources unreadable: {exc}"))
    else:
        actionable = counts["stale"] + counts["repair"] + counts["promote"]
        status = "warn" if actionable else "pass"
        checks.append((status, "gardening", f"{counts['repair']} repair, {counts['stale']} stale, {counts['promote']} promotion candidates"))

    ok = all(status != "fail" for status, _, _ in checks)
    lines = ["MEMENTO_TATTOO_DOCTOR"]
    lines.extend(f"{status.upper():5} {name}: {detail}" for status, name, detail in checks)
    return ok, "\n".join(lines)


def now_iso_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


RETENTION_RATE_MIN_EVENTS = 50
RETENTION_RATE_FLOOR = 0.05


def _retention_detail(root: Path, events: list[dict]) -> str:
    from .retention import recurrence_counts, retention_health_rate

    rate = retention_health_rate(root=root)
    counts = recurrence_counts(root=root)
    top = sorted(counts.items(), key=lambda item: -item[1])[:3]
    top_str = ", ".join(f"{note_id}:{count}" for note_id, count in top) if top else "none"
    detail = (
        f"retention events: {len(events)}; retention health {rate:.2f} "
        f"(existing-missed / (new + existing-missed); note-write signal, not prevention/application); "
        f"top recurring: {top_str}"
    )
    if len(events) >= RETENTION_RATE_MIN_EVENTS and rate < RETENTION_RATE_FLOOR:
        detail += f"; retention health under {RETENTION_RATE_FLOOR} at volume"
    return detail


def _check_recall_probes(root: Path) -> tuple[str, str, str]:
    import json

    from .recall import rank_memento_notes

    path = paths_for(root).root / ".recall_probes.json"
    if not path.exists():
        return ("warn", "recall-probes", "no recall probes configured")
    try:
        probes = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return ("fail", "recall-probes", f"probes file unreadable: {exc}")
    misses: list[str] = []
    for probe in probes:
        top = int(probe.get("top", 3))
        ranked = rank_memento_notes(probe["query"], root=root, limit=top)
        ids = [item.note.note_id for item in ranked]
        if probe["expect"] not in ids:
            misses.append(f"{probe['expect']} not in top-{top} for '{probe['query'][:48]}'")
    if misses:
        return ("fail", "recall-probes", "; ".join(misses))
    return ("pass", "recall-probes", f"{len(probes)}/{len(probes)} probes hit")


def _expired_reservations(path: Path) -> list[str]:
    if not path.exists():
        return []
    now = datetime.now(timezone.utc)
    expired: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        parts = raw.split()
        if len(parts) < 2:
            continue
        try:
            expiry = datetime.fromisoformat(parts[1].replace("Z", "+00:00"))
        except ValueError:
            expired.append(parts[0])
            continue
        if expiry <= now:
            expired.append(parts[0])
    return expired


def _check_alias_coverage(root: Path, warn_percent: float) -> tuple[str, str, str]:
    from .recall import alias_coverage_summary

    coverage = alias_coverage_summary(root)
    hot = coverage["hot"]
    archive = coverage["archive"]
    detail = f"hot {hot.aliased}/{hot.total} aliased; archive {archive.aliased}/{archive.total} aliased"
    below = archive.total and archive.aliased * 100 < warn_percent * archive.total
    if warn_percent > 0 and below:
        detail += f"; archive coverage below {warn_percent:g}% review threshold"
        return "warn", "alias-coverage", detail
    return "pass", "alias-coverage", detail


def _project_label(project: Path) -> str:
    return Path(project).name or Path(project).resolve().name


def _has_state_heading(text: str) -> bool:
    import re

    return any(re.search(rf"(?m)^{re.escape(heading)}\s*$", text) for heading in PROJECT_STATE_HEADINGS)


@dataclass(frozen=True)
class WhyCoverage:
    with_why: int
    total: int


def why_coverage_summary(root: Path) -> dict[str, WhyCoverage]:
    """Count valid hot and archived note records that carry a nonempty ``Why:`` field.

    The population matches alias coverage: blocks that start with a delta marker and
    parse as notes. Records without ``Why:`` are counted, never rejected.
    """
    paths = paths_for(root)
    return {
        "hot": _why_counts(paths.notes, "notes.md"),
        "archive": _why_counts(paths.notes_archive, "notes_archive.md"),
    }


def _why_counts(path: Path, source_name: str) -> WhyCoverage:
    import re

    from .entries import split_history
    from .recall import _DELTA_MARKER_RE, _extract_field, _parse_delta_note

    if not path.exists():
        return WhyCoverage(with_why=0, total=0)
    text = path.read_bytes().decode("utf-8")
    total = 0
    with_why = 0
    for block in re.split(r"(?m)(?=^<!--\s*delta:)", text):
        block = block.strip()
        if _parse_delta_note(block, source_name) is None:
            continue
        total += 1
        marker = _DELTA_MARKER_RE.search(block)
        body, _ = split_history(block[marker.end():].strip())
        if _extract_field(body, "Why"):
            with_why += 1
    return WhyCoverage(with_why=with_why, total=total)


def _check_why_coverage(root: Path, warn_percent: float) -> tuple[str, str, str]:
    coverage = why_coverage_summary(root)
    hot = coverage["hot"]
    archive = coverage["archive"]
    detail = f"hot {hot.with_why}/{hot.total} with Why; archive {archive.with_why}/{archive.total} with Why"
    if warn_percent > 0:
        below = [
            name
            for name, item in (("hot", hot), ("archive", archive))
            if item.total and item.with_why * 100 < warn_percent * item.total
        ]
        if below:
            detail += f"; {' and '.join(below)} below {warn_percent:g}% review threshold"
            return "warn", "why-coverage", detail
    return "pass", "why-coverage", detail


def has_reason_clause(text: str) -> bool:
    """True when a tattoo follows the ``<action with its trigger>; <reason clause>.`` shape."""
    action, separator, reason = text.partition(";")
    return bool(separator and action.strip() and reason.strip(" .\t\n"))


def _check_tattoo_reasons(text: str, warn_percent: float) -> tuple[str, str, str]:
    tattoos = parse_tattoos(text)
    total = len(tattoos)
    with_reason = sum(1 for tattoo in tattoos if has_reason_clause(tattoo.text))
    detail = f"{with_reason}/{total} with a reason clause"
    if warn_percent > 0 and total and with_reason * 100 < warn_percent * total:
        detail += f"; below {warn_percent:g}% review threshold"
        return "warn", "tattoo-reasons", detail
    return "pass", "tattoo-reasons", detail


def _check_tattoo_pressure(
    text: str,
    *,
    count_warn: int,
    bytes_warn: int,
    length_warn: int,
) -> tuple[str, str, str]:
    tattoos = parse_tattoos(text)
    count = len(tattoos)
    byte_count = sum(len(tattoo.text.encode("utf-8")) for tattoo in tattoos)
    measured_length = length_warn or RECOMMENDED_TATTOO_LENGTH
    over_length = [tattoo for tattoo in tattoos if len(tattoo.text) > measured_length]
    detail = f"{count} tattoos; {byte_count} UTF-8 bytes; {len(over_length)} over {measured_length:g} characters"

    warnings: list[str] = []
    if count_warn > 0 and count > count_warn:
        warnings.append(f"count over {count_warn:g}")
    if bytes_warn > 0 and byte_count > bytes_warn:
        warnings.append(f"bytes over {bytes_warn:g}")
    if length_warn > 0 and over_length:
        sample = ", ".join(
            f"{len(tattoo.text)}ch:{_one_line(tattoo.text, 32)}"
            for tattoo in over_length[:TATTOO_SAMPLE_LIMIT]
        )
        warnings.append(f"length over {length_warn:g} ({sample})")
    if warnings:
        detail += "; " + "; ".join(warnings) + "; run tattoo-audit for keep, demote, or cut review"
        return "warn", "tattoo-pressure", detail
    return "pass", "tattoo-pressure", detail


def _one_line(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."
