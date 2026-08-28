from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .config import paths_for
from .lock import memory_lock


# Write vocabulary. Read-side helpers below still tolerate legacy events carrying
# existing-repaired or false-positive.
DECISIONS = ("new", "existing-missed")
_REPEAT_DECISIONS = ("existing-missed", "existing-repaired")
_HEALTH_DECISIONS = ("new", "existing-missed")
RETENTION_LOG_ROTATE_BYTES = 128 * 1024
RETENTION_LOG_KEEP_EVENTS = 50
DEFAULT_MIN_SCORE = 60
# A true same-lesson cover stands out above its vocabulary neighbors; a flat tie
# (several unrelated notes scoring alike on generic-word overlap) is NOT a cover.
# The top candidate must beat rank-2 by this factor to count as a cover...
DOMINANCE_RATIO = 1.5
# ...unless the top match is strong in ABSOLUTE terms. A high score means many
# distinct terms matched (recall scores ~10/term + boosts) = real topical overlap,
# not generic-word noise. A genuine cover can share a high score with a close
# neighbor (ratio ~1.0), so the dominance ratio alone wrongly rejects it. A strong
# absolute match is a cover regardless of a co-high neighbor. Kept conservative
# (well above the 60 floor and a small flat tie) so a borderline overlap still logs
# 'new' by default rather than reintroducing a false positive.
STRONG_COVER_SCORE = 120
CLUSTER_MEMBER_MIN = 85


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip("\n") + "\n")


def append_retention_event(event: dict, *, root: Path, assume_locked: bool = False) -> None:
    path = paths_for(root).retention_log
    line = json.dumps(event, ensure_ascii=False, sort_keys=True)
    if assume_locked:
        _append_line(path, line)
        rotate_retention_log(root=root, assume_locked=True)
        return
    with memory_lock(paths_for(root).root):
        _append_line(path, line)
        rotate_retention_log(root=root, assume_locked=True)


def rotate_retention_log(
    *,
    root: Path,
    rotate_bytes: int = RETENTION_LOG_ROTATE_BYTES,
    keep: int = RETENTION_LOG_KEEP_EVENTS,
    assume_locked: bool = False,
) -> int:
    paths = paths_for(root)
    hot = paths.retention_log
    if not hot.exists() or hot.stat().st_size <= rotate_bytes:
        return 0

    def _do() -> int:
        lines = [line for line in hot.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            return 0
        encoded = [(line + "\n").encode("utf-8") for line in lines]
        retained_bytes = 0
        retained_count = 0
        retain_from = len(lines)
        for index in range(len(lines) - 1, -1, -1):
            size = len(encoded[index])
            if retained_count >= keep or retained_bytes + size > rotate_bytes:
                break
            retained_bytes += size
            retained_count += 1
            retain_from = index
        if retain_from == len(lines):
            retain_from = len(lines) - 1
        old, recent = lines[:retain_from], lines[retain_from:]
        if not old:
            return 0
        for line in old:
            _append_line(paths.retention_archive, line)
        hot.write_text("\n".join(recent) + "\n", encoding="utf-8")
        return len(old)

    if assume_locked:
        return _do()
    with memory_lock(paths.root):
        return _do()


def read_retention_events(*, root: Path, include_archive: bool = True) -> list[dict]:
    paths = paths_for(root)
    sources = []
    if include_archive and paths.retention_archive.exists():
        sources.append(paths.retention_archive)
    if paths.retention_log.exists():
        sources.append(paths.retention_log)
    events = []
    for path in sources:
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if raw:
                events.append(json.loads(raw))
    return events


def recurrence_counts(*, root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in read_retention_events(root=root):
        if event.get("decision") in _REPEAT_DECISIONS:
            note_id = event.get("cover_note_id") or event.get("covered_note_id") or event.get("note_id")
            if note_id:
                counts[note_id] = counts.get(note_id, 0) + 1
    return counts


def retention_health_rate(*, root: Path) -> float:
    """Return the share of shipped retention events recorded as existing-missed.

    This is a note-write classification signal, not a measure of prevention,
    retrieval exposure, application, or recurrence against opportunities.
    Legacy ``existing-repaired`` events remain readable but are excluded from
    the shipped two-decision denominator.
    """
    counted = set(_HEALTH_DECISIONS)
    total = 0
    repeats = 0
    for event in read_retention_events(root=root):
        decision = event.get("decision")
        if decision in counted:
            total += 1
            if decision == "existing-missed":
                repeats += 1
    return repeats / total if total else 0.0


def repeat_correction_rate(*, root: Path) -> float:
    """Compatibility alias for :func:`retention_health_rate`."""
    return retention_health_rate(root=root)


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
    strong = top >= STRONG_COVER_SCORE

    cluster_head = ""
    if len(candidates) > 1:
        high = [item for item in ranked if item.score >= CLUSTER_MEMBER_MIN]
        tag_sets = [{tag.strip().lower() for tag in item.note.tags if tag.strip()} for item in high]
        for index, item in enumerate(high):
            if not tag_sets[index]:
                continue
            if any(other != index and tag_sets[index] & tag_sets[other] for other in range(len(high))):
                cluster_head = item.note.note_id
                break
    clustered = bool(cluster_head)

    has_cover = bool(candidates) and top >= min_score and (dominant or strong or clustered)
    cover_note_id = ""
    if has_cover:
        cover_note_id = candidates[0]["note_id"] if (dominant or strong) else cluster_head
    return {
        "candidates": candidates,
        "has_cover": has_cover,
        "suggested_decision": "existing-missed" if has_cover else "new",
        "cover_note_id": cover_note_id,
    }
