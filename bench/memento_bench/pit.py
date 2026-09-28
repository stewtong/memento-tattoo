"""Point-in-time reconstruction of a note store.

A benchmark query made at time ``ts`` must only see what existed at ``ts``:
notes created earlier, with the wording they had then, and supersession marks
that had already been made. Timestamps are ISO strings at minute precision
(``YYYY-MM-DDTHH:MM``) or date precision (``YYYY-MM-DD``). Every tie resolves
toward the earlier state, so an ambiguous time never leaks later knowledge.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_ISO_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_NOTE_ID = re.compile(r"\bsess_[0-9a-z]+(?:\.note\.[0-9a-f]{8})?\b")


@dataclass(frozen=True)
class Revision:
    """An amendment made at ``timestamp``; ``previous`` is the state before it."""

    timestamp: str
    previous: dict


@dataclass(frozen=True)
class NoteRecord:
    note_id: str
    created: str  # "" when unknown
    created_source: str
    current: dict  # parsed fields of the current active body
    revisions: tuple[Revision, ...] = ()
    tier: str = ""
    meta: dict = field(default_factory=dict)


def strictly_before(a: str, b: str) -> bool:
    """True only when ``a`` is certainly earlier than ``b``.

    Compared at the coarser of the two precisions, so a date-only value on the
    same day as a minute value counts as not earlier.
    """
    if not a or not b:
        return False
    width = min(len(a), len(b))
    return a[:width] < b[:width]


def state_at(record: NoteRecord, ts: str) -> dict:
    """The note's fields as they stood at ``ts``.

    The active body at ``ts`` is the ``previous`` state of the first revision
    not certainly before ``ts``; if every revision is earlier, it is the
    current body.
    """
    for revision in sorted(record.revisions, key=lambda r: r.timestamp):
        if not strictly_before(revision.timestamp, ts):
            return dict(revision.previous)
    return dict(record.current)


def supersession_time(value: str, created_by_id: dict[str, str]) -> str:
    """When a ``Superseded-by:`` mark was made, as far as the text shows.

    Prefers the creation time of a referenced note; falls back to a date
    written in the text; returns "" when neither is available.
    """
    times = [created_by_id[m] for m in _NOTE_ID.findall(value) if created_by_id.get(m)]
    if not times:
        # A bare session ID refers to any note from that session.
        for token in _NOTE_ID.findall(value):
            times.extend(t for nid, t in created_by_id.items() if nid.startswith(token + ".") and t)
    if times:
        return min(times)
    dates = _ISO_DATE.findall(value)
    return min(dates) if dates else ""


def corpus_at(records: list[NoteRecord], ts: str, *, exclude: set[str] = frozenset()) -> tuple[list[dict], dict]:
    """Every note visible at ``ts``, with its state then, plus exclusion counts.

    A supersession mark without a revision record is kept only when the text
    dates it certainly before ``ts``; otherwise it is dropped, because showing
    it could leak later knowledge.
    """
    created_by_id = {r.note_id: r.created for r in records}
    visible: list[dict] = []
    counts = {"no_creation_time": 0, "not_yet_created": 0, "excluded_by_caller": 0,
              "supersession_dropped": 0, "reconstructed_from_revision": 0}
    for record in records:
        if record.note_id in exclude:
            counts["excluded_by_caller"] += 1
            continue
        if not record.created:
            counts["no_creation_time"] += 1
            continue
        if not strictly_before(record.created, ts):
            counts["not_yet_created"] += 1
            continue
        state = state_at(record, ts)
        if state != record.current:
            counts["reconstructed_from_revision"] += 1
        mark = state.get("superseded_by") or ""
        if mark:
            made = supersession_time(mark, created_by_id)
            if not strictly_before(made, ts):
                state["superseded_by"] = ""
                counts["supersession_dropped"] += 1
        state["note_id"] = record.note_id
        state["created"] = record.created
        state["tier"] = record.tier
        visible.append(state)
    return visible, counts
