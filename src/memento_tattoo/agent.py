from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from ._time import now_iso


@dataclass(frozen=True)
class DeltaMarker:
    note_id: str
    sess: str
    kind: str
    hash: str
    agent: str = "unknown"
    ts: str = ""


_MARKER_RE = re.compile(r"<!--\s*delta:(?P<note_id>[^\s>]+)(?P<attrs>.*?)\s*-->")


def normalize_agent(value: Optional[str]) -> str:
    raw = (value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_-]+", "-", raw)
    raw = re.sub(r"-{2,}", "-", raw).strip("-")
    return raw or "unknown"


def resolve_agent(value: Optional[str] = None) -> str:
    if value:
        return normalize_agent(value)
    return normalize_agent(os.environ.get("MEMENTO_AGENT"))


def format_delta_marker(note_id: str, *, agent: str, ts: Optional[str] = None) -> str:
    return f"<!-- delta:{note_id} agent={normalize_agent(agent)} ts={ts or now_iso()} -->"


def parse_delta_marker(marker_text: str) -> DeltaMarker | None:
    match = _MARKER_RE.search(marker_text)
    if not match:
        return None
    note_id = match.group("note_id").strip()
    attrs = _parse_attrs(match.group("attrs"))
    parts = note_id.split(".")
    return DeltaMarker(
        note_id=note_id,
        sess=parts[0] if len(parts) >= 1 else "",
        kind=parts[1] if len(parts) >= 2 else "",
        hash=parts[2] if len(parts) >= 3 else "",
        agent=normalize_agent(attrs.get("agent")),
        ts=attrs.get("ts", ""),
    )


def _parse_attrs(text: str) -> dict[str, str]:
    return {key: value for key, value in re.findall(r"([a-zA-Z_][\w-]*)=([^\s>]+)", text)}
