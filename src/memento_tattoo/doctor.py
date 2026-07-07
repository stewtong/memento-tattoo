from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import paths_for, project_memory_path
from .retention import read_retention_events
from .rebuild import rebuild
from .registry import _DELTA_RE
from .session_store import load_sessions
from .tattoo_audit import audit_tattoos


def run_doctor(root: Path, projects: Optional[list[Path]] = None) -> tuple[bool, str]:
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

    if paths.project.exists():
        checks.append(("pass", "project", f"{paths.project.name} present"))
    else:
        checks.append(("warn", "project", f"{paths.project.name} missing; use adjacent project memory.md for new roots"))

    for project in project_list:
        path = project_memory_path(project)
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if "## Key Decisions" in text and "## State" in text:
                checks.append(("pass", "project-memory", f"{path.name} present for {Path(project).name}"))
            else:
                checks.append(("fail", "project-memory", f"{path.name} missing required sections for {Path(project).name}"))
        else:
            checks.append(("fail", "project-memory", f"{path.name} missing for {Path(project).name}"))

    if not paths.retention_log.exists():
        checks.append(("warn", "retention", "retention_log.jsonl missing"))
    else:
        try:
            events = read_retention_events(root=paths.root)
        except Exception as exc:
            checks.append(("fail", "retention", f"retention_log.jsonl unreadable: {exc}"))
        else:
            checks.append(("pass", "retention", _retention_detail(paths.root, events)))
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
    if conflicts:
        checks.append(("warn", "registry-conflicts", f"conflict files: {len(conflicts)}"))

    if paths.tattoos.exists():
        try:
            flagged_count = sum(1 for c in audit_tattoos(root=paths.root) if c.flagged)
        except Exception:
            flagged_count = 0
        if flagged_count:
            noun = "tattoo" if flagged_count == 1 else "tattoos"
            checks.append(("warn", "tattoo-lifecycle", f"{flagged_count} {noun} due for review (run tattoo-audit)"))

    ok = all(status != "fail" for status, _, _ in checks)
    lines = ["MEMENTO_TATTOO_DOCTOR"]
    lines.extend(f"{status.upper():5} {name}: {detail}" for status, name, detail in checks)
    return ok, "\n".join(lines)


RETENTION_RATE_MIN_EVENTS = 50
RETENTION_RATE_FLOOR = 0.05


def _retention_detail(root: Path, events: list[dict]) -> str:
    from .retention import recurrence_counts, repeat_correction_rate

    rate = repeat_correction_rate(root=root)
    counts = recurrence_counts(root=root)
    top = sorted(counts.items(), key=lambda item: -item[1])[:3]
    top_str = ", ".join(f"{note_id}:{count}" for note_id, count in top) if top else "none"
    detail = f"retention events: {len(events)}; repeat-correction rate {rate:.2f}; top recurring: {top_str}"
    if len(events) >= RETENTION_RATE_MIN_EVENTS and rate < RETENTION_RATE_FLOOR:
        detail += f"; repeat-correction rate under {RETENTION_RATE_FLOOR} at volume"
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
