"""Tattoo sunset: the read-only exit ramp of the tattoo lifecycle.

`tattoo_add` is the entry side (promote a lesson into `tattoos.md`). This module is
the exit side: a deterministic audit that flags promoted tattoos due for review, so
the set has a review ramp instead of growing without bound.

This is a Tier-1 gate only: age + watermark. It does not compute recurrence and it
does not write or demote anything. The keep / demote / cut verdict is a Tier-2
semantic call left to a human or an LLM reading the report.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .agent import parse_delta_marker
from .config import PathLike, paths_for
from .session_store import load_sessions

DEFAULT_WINDOW_DAYS = 30

_REVIEWED_RE = re.compile(r"reviewed:(sess_[0-9A-Za-z]+)")
_COMMENT_RE = re.compile(r"<!--.*?-->")


@dataclass
class TattooCandidate:
    text: str
    origin_sess: Optional[str]
    reviewed_sess: Optional[str]
    age_days: Optional[int]
    flagged: bool
    reason: str


@dataclass
class _RawTattoo:
    text: str
    origin_sess: Optional[str]
    reviewed_sess: Optional[str]
    ts_date: Optional[date]


def _parse_ts(ts: str) -> Optional[date]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_session_date(raw: str) -> Optional[date]:
    try:
        return date.fromisoformat((raw or "").strip()[:10])
    except ValueError:
        return None


def _parse_tattoos(text: str) -> list[_RawTattoo]:
    """Pair every top-level ``- `` bullet with its nearest preceding marker line.

    Markers sit on their own line above the bullet. A marker is consumed by the
    first bullet that follows it; blank or header lines do not clear it.
    """
    out: list[_RawTattoo] = []
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            marker = current
            current = None
            body = stripped[2:]
            origin = marker.sess if (marker and marker.sess) else None
            ts_date = _parse_ts(marker.ts) if marker else None
            reviewed = m.group(1) if (m := _REVIEWED_RE.search(body)) else None
            clean = _REVIEWED_RE.sub("", _COMMENT_RE.sub("", body)).strip()
            out.append(_RawTattoo(text=clean, origin_sess=origin, reviewed_sess=reviewed, ts_date=ts_date))
        elif stripped.startswith("<!--") and (marker := parse_delta_marker(stripped)):
            current = marker
    return out


def audit_tattoos(
    root: Optional[PathLike] = None,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    now: Optional[date] = None,
) -> list[TattooCandidate]:
    paths = paths_for(root)
    text = paths.tattoos.read_text(encoding="utf-8", errors="replace") if paths.tattoos.exists() else ""
    raw = _parse_tattoos(text)

    session_dates: dict[str, date] = {}
    for record in load_sessions(paths.root):
        if d := _parse_session_date(record.date):
            session_dates[record.sess] = d

    known_dates = set(session_dates.values())
    known_dates.update(r.ts_date for r in raw if r.ts_date)
    anchor = now or (max(known_dates) if known_dates else None)

    candidates: list[TattooCandidate] = []
    for r in raw:
        review_unresolved = r.reviewed_sess is not None and r.reviewed_sess not in session_dates

        # Reference-date precedence: resolvable review -> marker ts -> origin session -> None.
        if r.reviewed_sess and r.reviewed_sess in session_dates:
            ref_date, basis = session_dates[r.reviewed_sess], "last reviewed"
        elif r.ts_date:
            ref_date, basis = r.ts_date, "added"
        elif r.origin_sess and r.origin_sess in session_dates:
            ref_date, basis = session_dates[r.origin_sess], "added"
        else:
            ref_date, basis = None, "added"

        age_days = (anchor - ref_date).days if (anchor and ref_date) else None
        flagged = review_unresolved or age_days is None or age_days > window_days

        if review_unresolved:
            reason = f"reviewed: marker references unknown session {r.reviewed_sess}, review first"
        elif age_days is None:
            reason = "no resolvable provenance marker, review first"
        elif age_days > window_days:
            reason = f"{age_days}d since {basis}, past {window_days}d window"
        else:
            reason = f"{basis} {age_days}d ago (within {window_days}d window)"

        candidates.append(
            TattooCandidate(
                text=r.text,
                origin_sess=r.origin_sess,
                reviewed_sess=r.reviewed_sess,
                age_days=age_days,
                flagged=flagged,
                reason=reason,
            )
        )
    return candidates


def tattoo_audit_report(
    root: Optional[PathLike] = None,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> str:
    candidates = audit_tattoos(root, window_days=window_days)
    flagged = [c for c in candidates if c.flagged]
    past = [c for c in flagged if c.age_days is not None and c.age_days > window_days]
    unknown = [c for c in flagged if not (c.age_days is not None and c.age_days > window_days)]

    lines = [
        f"Tattoo audit: {len(candidates)} tattoos, {len(flagged)} due for review "
        f"({len(past)} past {window_days}d window, {len(unknown)} unknown provenance)."
    ]
    if not flagged:
        lines.append("Nothing due for review.")
        return "\n".join(lines)

    lines.append("")
    lines.append("DUE FOR REVIEW — Tier-2 verdict each keep / demote / cut:")
    for i, c in enumerate(flagged, 1):
        age = "no marker" if c.age_days is None else f"{c.age_days}d"
        lines.append(f"{i}. [{age}] {c.text}")
        lines.append(f"   {c.reason}")
    return "\n".join(lines)
