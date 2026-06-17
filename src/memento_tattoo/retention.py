from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .config import paths_for
from .lock import memory_lock


DECISIONS = ("new", "existing-missed", "existing-repaired", "false-positive")
_REPEAT_DECISIONS = ("existing-missed", "existing-repaired")
DEFAULT_MIN_SCORE = 60
DOMINANCE_RATIO = 1.5


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip("\n") + "\n")


def append_retention_event(event: dict, *, root: Path, assume_locked: bool = False) -> None:
    path = paths_for(root).retention_log
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    if assume_locked:
        _append_line(path, line)
        return
    with memory_lock(paths_for(root).root):
        _append_line(path, line)


def read_retention_events(*, root: Path) -> list[dict]:
    path = paths_for(root).retention_log
    if not path.exists():
        return []
    events = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if raw:
            events.append(json.loads(raw))
    return events


def recurrence_counts(*, root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in read_retention_events(root=root):
        if event.get("decision") in _REPEAT_DECISIONS:
            note_id = event.get("note_id")
            if note_id:
                counts[note_id] = counts.get(note_id, 0) + 1
    return counts


def repeat_correction_rate(*, root: Path) -> float:
    counted = {"new", *_REPEAT_DECISIONS}
    total = 0
    repeats = 0
    for event in read_retention_events(root=root):
        decision = event.get("decision")
        if decision in counted:
            total += 1
            if decision in _REPEAT_DECISIONS:
                repeats += 1
    return repeats / total if total else 0.0


def classify(
    situation: str,
    *,
    root: Path,
    min_score: int = DEFAULT_MIN_SCORE,
    limit: int = 5,
) -> dict:
    from .recall import rank_memento_notes

    ranked = rank_memento_notes(situation, root=root, limit=limit)
    candidates = [
        {"note_id": item.note.note_id, "rank": index + 1, "score": item.score}
        for index, item in enumerate(ranked)
    ]
    top = candidates[0]["score"] if candidates else 0
    second = candidates[1]["score"] if len(candidates) > 1 else 0
    dominant = bool(candidates) and (len(candidates) == 1 or top >= DOMINANCE_RATIO * second)
    has_cover = bool(candidates) and top >= min_score and dominant
    return {
        "candidates": candidates,
        "has_cover": has_cover,
        "suggested_decision": "existing-missed" if has_cover else "new",
    }
