"""Ranked arms over a point-in-time corpus.

Each ranker takes a query and a corpus (a list of note dicts with at least
``note_id``, ``situation``, ``note``, ``why``, ``aliases``, ``tags``,
``superseded_by``) and returns note IDs, best first.

- ``a0_substring``: A0, the 0.4.0 package ranker (substring matching, fixed
  bonuses), frozen here so the baseline does not move when the package changes.
- ``a0_package``: the package's shipped ranker (BM25F since 0.5.0), called directly.
- ``bm25f``: A1, whole-word BM25F computed at query time.
- ``rrf``: reciprocal-rank fusion, which turns several A1 lists into A2.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from types import SimpleNamespace

from .text import tokens

FIELDS = ("situation", "aliases", "note", "why", "tags")


def _field_text(note: dict, name: str) -> str:
    value = note.get(name) or ""
    return " ".join(value) if isinstance(value, (list, tuple)) else value


_A0_STOPLIST = frozenset({"the", "and", "for", "that", "this", "with", "memory", "memento"})


def _a0_terms(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", text) if t.lower() not in _A0_STOPLIST]


def _a0_score(note: dict, terms: list[str]) -> int:
    """memento-tattoo 0.4.0 ``recall._score_note``, copied verbatim in behavior."""
    situation = (note.get("situation") or "").lower()
    body = (note.get("note") or "").lower()
    aliases = " ".join(note.get("aliases") or []).lower()
    tags = " ".join(note.get("tags") or []).lower()
    situation_hits = [t for t in terms if t in situation]
    note_hits = [t for t in terms if t in body]
    alias_hits = [t for t in terms if t in aliases]
    tag_hits = [t for t in terms if t in tags]
    all_hits = set(situation_hits + note_hits + alias_hits + tag_hits)
    if not all_hits:
        return 0
    score = 10 * len(all_hits)
    if situation_hits:
        score += 15
    if note_hits:
        score += 8
    if set(alias_hits) - set(situation_hits) - set(note_hits) - set(tag_hits):
        score += 20
    if len(all_hits) >= 3:
        score += 10
    return score


def _rank_by(score_fn, terms, corpus: list[dict], limit: int) -> list[str]:
    scored = []
    for note in corpus:
        score = score_fn(note, terms)
        if score <= 0:
            continue
        if note.get("superseded_by"):
            score -= 30
        source_name = "notes.md" if note.get("tier") == "hot" else "notes_archive.md"
        scored.append((-score, source_name, note["note_id"]))
    scored.sort()
    return [nid for _, _, nid in scored[:limit]]


def a0_substring(query: str, corpus: list[dict], limit: int = 50) -> list[str]:
    """A0: the 0.4.0 package ranker (substring matching, fixed bonuses).

    Frozen copy, including the superseded penalty and tie-break order, so
    every evaluation compares against the same baseline.
    """
    terms = _a0_terms(query)
    return _rank_by(_a0_score, terms, corpus, limit) if terms else []


def a0_package(query: str, corpus: list[dict], limit: int = 50) -> list[str]:
    """The package's shipped ranker (``recall.rank_notes``, BM25F since 0.5.0) on a corpus."""
    from memento_tattoo import recall

    notes = [recall.MementoNote(note_id=n["note_id"], source_name="notes.md" if n.get("tier") == "hot" else "notes_archive.md",
                                situation=n.get("situation") or "", note=n.get("note") or "", why=n.get("why") or "",
                                aliases=list(n.get("aliases") or []), tags=list(n.get("tags") or []),
                                superseded_by=n.get("superseded_by") or "") for n in corpus]
    return [item.note.note_id for item in recall.rank_notes(notes, query, limit=limit)]


@dataclass
class BM25FConfig:
    k1: float = 1.2
    b: float = 0.75
    weights: dict = field(default_factory=lambda: {
        "situation": 3.0, "aliases": 2.0, "note": 1.5, "why": 1.0, "tags": 0.5})
    superseded_factor: float = 0.5

    def key(self) -> str:
        w = ",".join(f"{k}={self.weights[k]:g}" for k in FIELDS)
        return f"bm25f(k1={self.k1:g},b={self.b:g},{w},sup={self.superseded_factor:g})"


class BM25FIndex:
    """Per-corpus statistics, built at query time. No persistent index."""

    def __init__(self, corpus: list[dict]):
        self.ids = [n["note_id"] for n in corpus]
        self.superseded = [bool(n.get("superseded_by")) for n in corpus]
        self.field_tf: list[dict[str, Counter]] = []
        self.field_len: list[dict[str, int]] = []
        df: Counter = Counter()
        totals = {f: 0 for f in FIELDS}
        for note in corpus:
            per_field = {f: Counter(tokens(_field_text(note, f))) for f in FIELDS}
            lengths = {f: sum(c.values()) for f, c in per_field.items()}
            for f in FIELDS:
                totals[f] += lengths[f]
            df.update(set().union(*(c.keys() for c in per_field.values())))
            self.field_tf.append(per_field)
            self.field_len.append(lengths)
        n = max(len(corpus), 1)
        self.avg_len = {f: (totals[f] / n) or 1.0 for f in FIELDS}
        self.idf = {t: math.log(1 + (len(corpus) - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def rank(self, query: str, config: BM25FConfig, limit: int = 50) -> list[str]:
        terms = [t for t in dict.fromkeys(tokens(query)) if t in self.idf]
        if not terms:
            return []
        scored = []
        for i, per_field in enumerate(self.field_tf):
            score = 0.0
            for term in terms:
                pseudo_tf = 0.0
                for f in FIELDS:
                    tf = per_field[f].get(term)
                    if tf:
                        norm = 1 - config.b + config.b * self.field_len[i][f] / self.avg_len[f]
                        pseudo_tf += config.weights[f] * tf / norm
                if pseudo_tf:
                    score += self.idf[term] * pseudo_tf / (config.k1 + pseudo_tf)
            if score > 0:
                if self.superseded[i]:
                    score *= config.superseded_factor
                scored.append((-score, self.ids[i]))
        scored.sort()
        return [nid for _, nid in scored[:limit]]


def rrf(lists: list[list[str]], k: int = 60, limit: int = 50) -> list[str]:
    """Reciprocal-rank fusion (Cormack et al., 2009): sum 1/(k + rank)."""
    scores: dict[str, float] = {}
    first_seen: dict[str, tuple[int, int]] = {}
    for li, ranked in enumerate(lists):
        for rank, nid in enumerate(ranked, 1):
            scores[nid] = scores.get(nid, 0.0) + 1.0 / (k + rank)
            first_seen.setdefault(nid, (rank, li))
    order = sorted(scores, key=lambda nid: (-scores[nid], first_seen[nid]))
    return order[:limit]
