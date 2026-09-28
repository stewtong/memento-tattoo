from __future__ import annotations

import math
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .entries import PAIR, canonical_block, digest, split_history, allowed_sources
from .agent import parse_delta_marker
from .config import paths_for, project_memory_path


TERM_STOPLIST = {"the", "and", "for", "that", "this", "with", "memory", "memento"}
_WORD = re.compile(r"[a-z0-9]+")
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
    why: str = ""
    tags: list[str] = None
    superseded_by: str = ""
    source_path: str = ""
    entry_id: str = ""
    content_sha256: str = ""
    excerpt_incomplete: bool = False

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


@dataclass
class RankedMementoNote:
    note: MementoNote
    score: float
    reasons: list[str]
    superseded: bool = False

    @property
    def source_name(self) -> str:
        return self.note.source_name


@dataclass(frozen=True)
class AliasCoverage:
    aliased: int
    total: int


def alias_coverage_summary(root: Path) -> dict[str, AliasCoverage]:
    """Summarize aliases on valid hot and archived note records."""
    paths = paths_for(root)
    hot = _load_notes_file(paths.notes)
    archive = _load_notes_file(paths.notes_archive, "notes_archive.md")
    return {
        "hot": AliasCoverage(aliased=sum(bool(note.aliases) for note in hot), total=len(hot)),
        "archive": AliasCoverage(aliased=sum(bool(note.aliases) for note in archive), total=len(archive)),
    }


def load_memento_notes(root: Path, projects: Optional[list[Path]] = None) -> list[MementoNote]:
    paths = paths_for(root)
    allowed_sources(root, projects)  # Validate declared source boundaries before reads.
    notes: list[MementoNote] = []
    notes.extend(_load_notes_file(paths.notes))
    # Rotated-out notes live in the cold archive but must still rank and cover repeats,
    # otherwise rotation would silently drop lessons from retrieval.
    notes.extend(_load_notes_file(paths.notes_archive, "notes_archive.md"))
    notes.extend(_load_project_file(paths.project))
    for project in projects or []:
        notes.extend(_load_project_file(project_memory_path(project), source_name=f"{Path(project).name}/memory.md"))
    notes.extend(_load_tattoos_file(paths.tattoos))
    return notes


# BM25F settings, from the Phase 0 evaluation of past corrections: Lucene's k1 and b,
# and per-field weights applied to term frequency before saturation.
BM25_K1 = 1.2
BM25_B = 0.75
FIELD_WEIGHTS = {"situation": 3.0, "aliases": 2.0, "note": 1.5, "why": 1.0, "tags": 0.5}
SUPERSEDED_FACTOR = 0.5


def rank_memento_notes(
    query: str,
    *,
    root: Path,
    limit: int = 8,
    projects: Optional[list[Path]] = None,
    scoring: str = "bm25f",
) -> list[RankedMementoNote]:
    """Rank lessons for a query.

    ``bm25f`` (the default, used by ``load``) weights rare words above common
    ones. ``bonus`` is the earlier fixed-bonus scoring, kept for the retention
    classifier, whose cover thresholds are calibrated to its scale.
    """
    notes = load_memento_notes(root, projects=projects)
    if scoring == "bm25f":
        return rank_notes(notes, query, limit=limit)
    if scoring != "bonus":
        raise ValueError(f"unknown scoring {scoring!r}")
    terms = _terms(query)
    if not terms:
        return []

    ranked: list[RankedMementoNote] = []
    for note in notes:
        score, reasons = _score_note(note, terms)
        if score <= 0:
            continue
        superseded = bool(note.superseded_by)
        if superseded:
            score -= 30
            reasons.append(f"superseded by {note.superseded_by}")
        ranked.append(RankedMementoNote(note=note, score=score, reasons=reasons, superseded=superseded))
    return sorted(ranked, key=lambda item: (-item.score, item.note.source_name, item.note.note_id))[:limit]


def _note_fields(note: MementoNote) -> dict[str, list[str]]:
    return {
        "situation": _words(note.situation),
        "aliases": _words(" ".join(note.aliases)),
        "note": _words(note.note),
        "why": _words(getattr(note, "why", "") or ""),
        "tags": _words(" ".join(note.tags or [])),
    }


def rank_notes(notes: list[MementoNote], query: str, *, limit: int = 8) -> list[RankedMementoNote]:
    """BM25F over the given notes, computed at query time with no persistent index.

    Each field's term frequency is length-normalized and weighted, then summed
    before saturation, so a word repeated across fields is not counted twice at
    full strength. Superseded notes keep half their score.
    """
    terms = _terms(query)
    if not terms or not notes:
        return []
    fields = [_note_fields(note) for note in notes]
    lengths = [{f: len(words) for f, words in per.items()} for per in fields]
    count = len(notes)
    avg = {f: (sum(l[f] for l in lengths) / count) or 1.0 for f in FIELD_WEIGHTS}
    df = {term: 0 for term in terms}
    counters = []
    for per in fields:
        present: dict[str, dict[str, int]] = {}
        for f, words in per.items():
            for word in words:
                if word in df:
                    present.setdefault(word, {}).setdefault(f, 0)
                    present[word][f] += 1
        for term in present:
            df[term] += 1
        counters.append(present)
    idf = {t: math.log(1 + (count - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    ranked: list[RankedMementoNote] = []
    for note, present, length in zip(notes, counters, lengths):
        if not present:
            continue
        score = 0.0
        for term, per_field in present.items():
            pseudo = sum(FIELD_WEIGHTS[f] * tf / (1 - BM25_B + BM25_B * length[f] / avg[f]) for f, tf in per_field.items())
            score += idf[term] * pseudo / (BM25_K1 + pseudo)
        matched = sorted(present)
        reasons = [f"matched terms: {', '.join(matched[:5])}"]
        in_situation = [t for t in terms if "situation" in present.get(t, {})]
        if in_situation:
            reasons.append(f"situation match: {', '.join(in_situation[:3])}")
        superseded = bool(note.superseded_by)
        if superseded:
            score *= SUPERSEDED_FACTOR
            reasons.append(f"superseded by {note.superseded_by}")
        ranked.append(RankedMementoNote(note=note, score=round(score, 4), reasons=reasons, superseded=superseded))
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
    lines[2:2] = [
        "scope: root notes, archive, project.md, tattoos, and explicitly supplied project paths",
        f"limit: {limit}",
        f"shown: {len(ranked)}",
        "completeness: bounded ranking; missing matches do not establish absence",
    ]
    state_paths = [paths_for(root).project, *[project_memory_path(project) for project in projects or []]]
    states = [(path, _current_state(path)) for path in dict.fromkeys(state_paths)]
    states = [(path, state) for path, state in states if state]
    if states:
        lines.insert(-1, "authority: current source and user direction outrank memory; apply lessons only within their situation")
        lines.insert(-1, "current_project_state:")
        for path, state in states[:5]:
            lines.insert(-1, f"- source: {path}")
            lines.insert(-1, f"  excerpt: {_one_line(state, limit=930)}")
            lines.insert(-1, f"  excerpt_clipped: {str('[excerpt truncated]' in state).lower()}")
            lines.insert(-1, f"  read_reference: {_read_reference(root, 'project-file:' + digest(path.read_bytes().decode('utf-8')), path, projects)}")
        if len(states) > 5:
            lines.insert(-1, f"  omitted_project_states: {len(states) - 5}")
    if not ranked:
        lines.append("- none")
    for item in ranked:
        lines.extend(
            [
                f"- note_id: {item.note.note_id}",
                f"  source: {item.note.source_name}",
                f"  source_path: {item.note.source_path}",
                f"  entry_id: {item.note.entry_id or item.note.note_id}",
                f"  content_sha256: {item.note.content_sha256}",
                f"  excerpt_clipped: {str(item.note.excerpt_incomplete or _clipped(item.note.situation) or _clipped(item.note.note)).lower()}",
                f"  read_reference: {_read_reference(root, item.note.entry_id or item.note.note_id, Path(item.note.source_path), projects)}",
                f"  score: {item.score}",
                f"  superseded_by: {item.note.superseded_by or ''}",
                f"  situation: {_one_line(item.note.situation)}",
                f"  note: {_one_line(item.note.note)}",
                f"  reasons: {'; '.join(item.reasons)}",
            ]
        )
    return "\n".join(lines)


def _current_state(path: Path) -> str:
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    ordered = sorted(enumerate(lines), key=lambda pair: not bool(re.match(r"^##\s+current\b", pair[1], re.I)))
    for index, line in ordered:
        if re.match(r"^##\s+(?:current(?:\s+state|\s+status)?|state|status)\s*(?:\([^)]*\))?\s*$", line, re.I):
            end = next((j for j in range(index + 1, len(lines)) if lines[j].startswith("## ")), len(lines))
            text = " ".join(x for x in lines[index + 1:end] if not x.startswith("<!--"))
            if not text.strip():
                continue  # an empty heading must not hide a filled current-state section
            return text[:900] + (" [excerpt truncated]" if len(text) > 900 else "")
    return ""


def _load_notes_file(path: Path, source_name: str = "notes.md") -> list[MementoNote]:
    if not path.exists():
        return []
    text = path.read_bytes().decode("utf-8")
    blocks = re.split(r"(?m)(?=^<!--\s*delta:)", text)
    notes = []
    for block in blocks:
        parsed = _parse_delta_note(block.strip(), source_name)
        if parsed is not None:
            parsed.source_path = str(path.resolve())
            parsed.entry_id = parsed.note_id
            parsed.content_sha256 = digest(canonical_block(block.strip()))
            notes.append(parsed)
    return notes


def _load_project_file(path: Path, source_name: str = "project.md") -> list[MementoNote]:
    if not path.exists():
        return []
    text = path.read_bytes().decode("utf-8")
    notes: list[MementoNote] = []
    pairs = list(PAIR.finditer(text.replace("\r\n", "\n")))
    for index, pair in enumerate(pairs, start=1):
        situation, note = pair.groups()
        notes.append(
            MementoNote(
                note_id=f"project:memory.md:{index}" if source_name.endswith("memory.md") else f"project.md:{index}",
                source_name=source_name,
                situation=situation.strip(),
                note=note.strip(),
                aliases=[],
                source_path=str(path.resolve()),
                entry_id="project-file:" + digest(text),
                content_sha256=digest(text),
                excerpt_incomplete=True,
            )
        )
    return notes


def _load_tattoos_file(path: Path) -> list[MementoNote]:
    if not path.exists():
        return []
    text = path.read_bytes().decode("utf-8")
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
                    source_path=str(path.resolve()),
                    entry_id=marker.note_id,
                    content_sha256=digest(canonical_block(chunk.strip())),
                )
            )
            fallback += 1
    return notes


def _parse_delta_note(block: str, source_name: str) -> Optional[MementoNote]:
    marker = parse_delta_marker(block)
    marker_match = _DELTA_MARKER_RE.search(block)
    if marker is None or marker_match is None:
        return None
    try:
        body, _ = split_history(block[marker_match.end() :].strip())
    except ValueError as exc:
        raise ValueError(f"{source_name}: note {marker.note_id}: {exc}") from exc
    return MementoNote(
        note_id=marker.note_id,
        source_name=source_name,
        situation=_extract_field(body, "Situation"),
        note=_extract_field(body, "Note"),
        why=_extract_field(body, "Why"),
        aliases=_csv(_extract_field(body, "aliases")),
        tags=_csv(_extract_field(body, "tags")),
        review_after=_extract_field(body, "review_after"),
        superseded_by=_extract_field(body, "Superseded-by"),
    )


def _extract_field(body: str, field_name: str) -> str:
    pattern = re.compile(
        rf"^{re.escape(field_name)}:[ \t]*(.*?)(?=\n(?:{_FIELD_NAMES}):|\Z)",
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
    situation_hits = _field_hits(note.situation, terms)
    note_hits = _field_hits(note.note, terms)
    alias_hits = _field_hits(" ".join(note.aliases), terms)
    tag_hits = _field_hits(" ".join(note.tags or []), terms)
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


def _field_hits(text: str, terms: list[str]) -> list[str]:
    """Terms that occur in ``text`` as whole words, after plural folding.

    Same result as comparing against ``_words(text)``, computed faster: a word
    folds to a term only if it is the term itself, the term plus "s", or, for
    a term ending in "y", the "ies" form. So check those spellings among the
    raw words instead of folding every word.
    """
    lowered = text.lower()
    if not any(term in lowered or (term.endswith("y") and term[:-1] + "ies" in lowered) for term in terms):
        return []
    raw = set(_WORD.findall(lowered))
    hits = []
    for term in terms:
        spellings = (term, term + "s", term[:-1] + "ies") if term.endswith("y") else (term, term + "s")
        if any(word in raw and _kept(word) and _fold_plural(word) == term for word in spellings):
            hits.append(term)
    return hits


def _kept(word: str) -> bool:
    return word not in TERM_STOPLIST and (len(word) >= 3 or any(c.isdigit() for c in word))


def _terms(text: str) -> list[str]:
    """Distinct query words, in order, normalized as `_words` does."""
    return list(dict.fromkeys(_words(text)))


def _words(text: str) -> list[str]:
    """Whole words, lowercased, with plurals folded.

    Matching compares whole words, so "art" does not match "start" and "log"
    does not match "login". Words shorter than three characters are dropped
    unless they contain a digit, and stoplisted words are dropped.
    """
    words = []
    for word in _WORD.findall(text.lower()):
        if _kept(word):
            words.append(_fold_plural(word))
    return words


def _fold_plural(word: str) -> str:
    """Harman's S-stemmer: fold a plural with the first matching rule.

    "ies" becomes "y" (not after "e" or "a"), "es" becomes "e" (not after
    "a", "e" or "o"), and a final "s" is dropped (not after "u" or "s").
    Words of three letters or fewer are unchanged.
    """
    if len(word) <= 3:
        return word
    if word.endswith("ies") and not word.endswith(("eies", "aies")):
        return word[:-3] + "y"
    if word.endswith("es") and not word.endswith(("aes", "ees", "oes")):
        return word[:-1]
    if word.endswith("s") and not word.endswith(("us", "ss")):
        return word[:-1]
    return word


def _csv(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()] if text else []


def _one_line(text: str, limit: int = 160) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def _clipped(text: str) -> bool:
    return len(re.sub(r"\s+", " ", text).strip()) > 160


def _read_reference(root: Path, entry_id: str, path: Path, projects: Optional[list[Path]]) -> str:
    arguments = ["memento-tattoo", "--root", str(paths_for(root).root), "entry-read", "--id", entry_id, "--source", str(path.resolve())]
    for project in projects or []:
        arguments.extend(["--project", str(project.expanduser().resolve())])
    return shlex.join(arguments)
