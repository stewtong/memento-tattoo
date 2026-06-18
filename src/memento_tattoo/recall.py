from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .agent import parse_delta_marker
from .config import paths_for, project_memory_path


TERM_STOPLIST = {"the", "and", "for", "that", "this", "with", "memory", "memento"}
_DELTA_MARKER_RE = re.compile(r"<!--\s*delta:[^\n]*?-->")
_FIELD_NAMES = "Situation|Note|Why|How to apply|tags|aliases|Superseded-by|review_after"


@dataclass
class MementoNote:
    note_id: str
    source_name: str
    situation: str
    note: str
    aliases: list[str]
    review_after: str = ""
    tags: list[str] = None
    superseded_by: str = ""

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


@dataclass
class RankedMementoNote:
    note: MementoNote
    score: int
    reasons: list[str]
    superseded: bool = False

    @property
    def source_name(self) -> str:
        return self.note.source_name


def load_memento_notes(root: Path, projects: Optional[list[Path]] = None) -> list[MementoNote]:
    paths = paths_for(root)
    notes: list[MementoNote] = []
    notes.extend(_load_notes_file(paths.notes))
    notes.extend(_load_project_file(paths.project))
    for project in projects or []:
        notes.extend(_load_project_file(project_memory_path(project), source_name=f"{Path(project).name}/memory.md"))
    notes.extend(_load_tattoos_file(paths.tattoos))
    return notes


def rank_memento_notes(
    query: str,
    *,
    root: Path,
    limit: int = 8,
    projects: Optional[list[Path]] = None,
) -> list[RankedMementoNote]:
    terms = _terms(query)
    if not terms:
        return []

    ranked: list[RankedMementoNote] = []
    for note in load_memento_notes(root, projects=projects):
        score, reasons = _score_note(note, terms)
        if score <= 0:
            continue
        superseded = bool(note.superseded_by)
        if superseded:
            score -= 30
            reasons.append(f"superseded by {note.superseded_by}")
        ranked.append(RankedMementoNote(note=note, score=score, reasons=reasons, superseded=superseded))
    return sorted(ranked, key=lambda item: (-item.score, item.note.source_name, item.note.note_id))[:limit]


def render_ranked_notes(
    query: str,
    *,
    root: Path,
    limit: int = 8,
    projects: Optional[list[Path]] = None,
) -> str:
    lines = ["MEMENTO_TATTOO_LOAD", f"query: {query}", "matches:"]
    ranked = rank_memento_notes(query, root=root, limit=limit, projects=projects)
    if not ranked:
        lines.append("- none")
    for item in ranked:
        lines.extend(
            [
                f"- note_id: {item.note.note_id}",
                f"  source: {item.note.source_name}",
                f"  score: {item.score}",
                f"  situation: {_one_line(item.note.situation)}",
                f"  note: {_one_line(item.note.note)}",
                f"  reasons: {'; '.join(item.reasons)}",
            ]
        )
    return "\n".join(lines)


def _load_notes_file(path: Path) -> list[MementoNote]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"(?m)(?=^<!--\s*delta:)", text)
    notes = []
    for block in blocks:
        parsed = _parse_delta_note(block.strip(), "notes.md")
        if parsed is not None:
            notes.append(parsed)
    return notes


def _load_project_file(path: Path, source_name: str = "project.md") -> list[MementoNote]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    notes: list[MementoNote] = []
    pairs = re.findall(r"(?mi)^\s*-\s*Situation:\s*(.+?)\s*$\n^\s*-\s*Note:\s*(.+?)\s*$", text)
    for index, (situation, note) in enumerate(pairs, start=1):
        notes.append(
            MementoNote(
                note_id=f"project:memory.md:{index}" if source_name.endswith("memory.md") else f"project.md:{index}",
                source_name=source_name,
                situation=situation.strip(),
                note=note.strip(),
                aliases=[],
            )
        )
    return notes


def _load_tattoos_file(path: Path) -> list[MementoNote]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    notes: list[MementoNote] = []
    chunks = re.split(r"(?m)(?=^<!--\s*delta:)", text)
    fallback = 1
    for chunk in chunks:
        marker = parse_delta_marker(chunk)
        marker_match = _DELTA_MARKER_RE.search(chunk)
        if marker is None or marker_match is None:
            continue
        body = chunk[marker_match.end() :].strip()
        bullet = _first_bullet(body)
        if bullet:
            notes.append(
                MementoNote(
                    note_id=marker.note_id,
                    source_name="tattoos.md",
                    situation="tattoo",
                    note=bullet,
                    aliases=[],
                )
            )
            fallback += 1
    return notes


def _parse_delta_note(block: str, source_name: str) -> Optional[MementoNote]:
    marker = parse_delta_marker(block)
    marker_match = _DELTA_MARKER_RE.search(block)
    if marker is None or marker_match is None:
        return None
    body = block[marker_match.end() :].strip()
    return MementoNote(
        note_id=marker.note_id,
        source_name=source_name,
        situation=_extract_field(body, "Situation"),
        note=_extract_field(body, "Note"),
        aliases=_csv(_extract_field(body, "aliases")),
        tags=_csv(_extract_field(body, "tags")),
        review_after=_extract_field(body, "review_after"),
        superseded_by=_extract_field(body, "Superseded-by"),
    )


def _extract_field(body: str, field_name: str) -> str:
    pattern = re.compile(
        rf"^{re.escape(field_name)}:\s*(.*?)(?=\n(?:{_FIELD_NAMES}):|$)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def _first_bullet(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            return stripped[2:].strip()
    return text.strip().splitlines()[0].strip() if text.strip() else ""


def _score_note(note: MementoNote, terms: list[str]) -> tuple[int, list[str]]:
    situation_lower = note.situation.lower()
    note_lower = note.note.lower()
    aliases_lower = " ".join(note.aliases).lower()
    tags_lower = " ".join(note.tags or []).lower()

    situation_hits = [term for term in terms if term in situation_lower]
    note_hits = [term for term in terms if term in note_lower]
    alias_hits = [term for term in terms if term in aliases_lower]
    tag_hits = [term for term in terms if term in tags_lower]
    all_hits = set(situation_hits + note_hits + alias_hits + tag_hits)
    if not all_hits:
        return 0, []

    score = 10 * len(all_hits)
    reasons = [f"matched terms: {', '.join(sorted(all_hits)[:5])}"]
    if situation_hits:
        score += 15
        reasons.append(f"situation match: {', '.join(situation_hits[:3])}")
    if note_hits:
        score += 8
        reasons.append(f"note match: {', '.join(note_hits[:3])}")
    alias_only = set(alias_hits) - set(situation_hits) - set(note_hits) - set(tag_hits)
    if alias_only:
        score += 20
        reasons.append(f"alias match: {', '.join(sorted(alias_only)[:3])}")
    if len(all_hits) >= 3:
        score += 10
        reasons.append("broad term coverage")
    return score, reasons


def _terms(text: str) -> list[str]:
    return [
        term.lower()
        for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", text)
        if term.lower() not in TERM_STOPLIST
    ]


def _csv(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()] if text else []


def _one_line(text: str, limit: int = 160) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."
