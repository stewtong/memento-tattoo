"""Arms for the repeated-correction benchmark (spec: README.md in this directory).

Retrieval arms rank the lessons a query may see. Agent-level context builders
turn an arm's choice into the text an agent reads. Nothing here calls a model
except the optional embedding arm, which runs a local embedding model.

Data contract (files in a private cache directory; comment text stays there):

- ``lessons.jsonl``: id, pr, created_at, path, paths_glob, text, situation, edits
  (a list of {edited_at, previous_text}).
- ``queries.jsonl``: id, pr, pr_opened_at, path, diff_hunk, reference_text,
  relevant (lesson ids), post_cutoff.
- ``clusters.json``: clusters {cluster_id: [comment ids]}, member_pr, member_created.
"""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for _p in (_HERE.parent, _HERE.parents[1] / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from memento_bench import rankers  # noqa: E402

CURATED_BUDGET_TOKENS = 2000
# The long-file arm: Codex's default cap on AGENTS.md content (project_doc_max_bytes, 32 KiB).
LONG_FILE_BYTES = 32 * 1024
TOP_K = 5


class ArmUnavailable(RuntimeError):
    """The arm cannot run in this environment or is not built yet."""


# Loading

def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_dataset(cache: Path) -> tuple[list[dict], list[dict], dict]:
    return (load_jsonl(cache / "lessons.jsonl"), load_jsonl(cache / "queries.jsonl"),
            json.loads((cache / "clusters.json").read_text(encoding="utf-8")))


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# Point in time

def text_at(lesson: dict, when: str) -> str | None:
    """The lesson's text as it stood at ``when``, or None when it cannot be known.

    If the lesson was edited after ``when``, its text then is the
    ``previous_text`` of the earliest such edit. An edit recorded with
    ``previous_text`` None means the earlier text could not be retrieved, so
    the text at ``when`` is unknown.
    """
    cutoff = _ts(when)
    later = sorted((e for e in lesson.get("edits") or [] if _ts(e["edited_at"]) > cutoff),
                   key=lambda e: _ts(e["edited_at"]))
    return later[0]["previous_text"] if later else lesson["text"]


def visible_lessons_counted(query: dict, lessons: list[dict]) -> tuple[list[dict], int]:
    """Visible lessons plus the number excluded because their text at query time is unknown."""
    opened = _ts(query["pr_opened_at"])
    out, unknown = [], 0
    for lesson in lessons:
        if lesson["pr"] == query["pr"] or _ts(lesson["created_at"]) >= opened:
            continue
        text = text_at(lesson, query["pr_opened_at"])
        if text is None:
            unknown += 1
            continue
        out.append({**lesson, "text": text})
    return out, unknown


def visible_lessons(query: dict, lessons: list[dict]) -> list[dict]:
    """Lessons from other PRs created strictly before the query PR opened, as they read then.

    A lesson edited after the query PR opened, with no recorded earlier text,
    is excluded; ``visible_lessons_counted`` reports how many.
    """
    return visible_lessons_counted(query, lessons)[0]


def query_text(query: dict) -> str:
    return f"{query['path']}\n{query['diff_hunk']}"


# Rendering and size

def estimate_tokens(text: str) -> int:
    """Fixed rule, no tokenizer dependency: one token per four characters, rounded up."""
    return math.ceil(len(text) / 4)


def render_lesson(lesson: dict) -> str:
    """Neutral form: no comment ID, no author, no PR number."""
    lines = []
    if lesson.get("situation"):
        lines.append(f"Situation: {lesson['situation']}")
    lines.append(f"Applies to: {lesson['paths_glob']}")
    lines.append(f"Lesson: {lesson['text'].strip()}")
    return "\n".join(lines)


def render_lessons(lessons: list[dict]) -> str:
    return "\n\n".join(f"- {render_lesson(l)}".replace("\n", "\n  ") for l in lessons)


# Retrieval arms

def _as_notes(lessons: list[dict]) -> list[dict]:
    return [{"note_id": l["id"], "situation": l.get("situation") or "", "note": l["text"], "why": "",
             "aliases": [], "tags": [], "superseded_by": "", "tier": "archive"} for l in lessons]


def memento_lexical(query: dict, visible: list[dict], limit: int = 50) -> list[str]:
    """The shipped package ranker, through the bench's ``a0_package`` wrapper."""
    return rankers.a0_package(query_text(query), _as_notes(visible), limit=limit)


# Plain BM25: every field weighted equally and no superseded penalty, so it differs from
# memento's shipped ranker (field-weighted BM25F) by exactly memento's field choices.
PLAIN_BM25 = rankers.BM25FConfig(weights={f: 1.0 for f in rankers.FIELDS}, superseded_factor=1.0)


def bm25(query: dict, visible: list[dict], limit: int = 50) -> list[str]:
    return rankers.BM25FIndex(_as_notes(visible)).rank(query_text(query), PLAIN_BM25, limit=limit)


_EMBED = {}


def embeddings(query: dict, visible: list[dict], limit: int = 50, cache_dir: Path | None = None) -> list[str]:
    try:
        from memento_bench.embed import EmbeddingArm
        key = str(cache_dir)
        if key not in _EMBED:
            _EMBED[key] = EmbeddingArm(cache_dir or _HERE / ".embed-cache")
    except ImportError as exc:
        raise ArmUnavailable(f"embeddings need fastembed in this interpreter ({exc})") from exc
    arm = _EMBED[key]
    ranked = arm.rank(query_text(query), _as_notes(visible), limit=limit)
    arm.save()
    return ranked


def memento_paths(query: dict, visible: list[dict], limit: int = 50) -> list[str]:
    raise ArmUnavailable("paths scoping not built yet (Phase 3)")


RETRIEVAL_ARMS = {"memento_lexical": memento_lexical, "memento_paths": memento_paths, "bm25": bm25,
                  "embeddings": embeddings}


# Agent-level context

@dataclass
class Context:
    arm: str
    text: str
    tokens: int
    lesson_ids: list[str]


def top_k_context(arm: str, query: dict, visible: list[dict], k: int = TOP_K, **kwargs) -> Context:
    ranked = RETRIEVAL_ARMS[arm](query, visible, limit=k, **kwargs)
    by_id = {l["id"]: l for l in visible}
    chosen = [by_id[i] for i in ranked[:k]]
    text = render_lessons(chosen)
    return Context(arm, text, estimate_tokens(text), [l["id"] for l in chosen])


def recurrence(lesson_id: str, query: dict, clusters: dict) -> int:
    """Distinct PRs, other than the query's, among the lesson's cluster members created before the query PR opened."""
    opened = _ts(query["pr_opened_at"])
    member_pr, member_created = clusters.get("member_pr", {}), clusters.get("member_created", {})
    prs = set()
    for members in clusters.get("clusters", {}).values():
        if lesson_id not in members:
            continue
        for m in members:
            if m in member_created and _ts(member_created[m]) < opened and member_pr.get(m) != query["pr"]:
                prs.add(member_pr.get(m))
    return max(len(prs), 1)


def curated_context(query: dict, visible: list[dict], clusters: dict,
                    budget: int = CURATED_BUDGET_TOKENS) -> Context:
    """Most-recurred lessons first (ties to the most recent), kept while they fit the budget."""
    ranked = sorted(visible, key=lambda l: (-recurrence(l["id"], query, clusters), -_ts(l["created_at"]).timestamp(), l["id"]))
    chosen: list[dict] = []
    for lesson in ranked:
        # Measure the rendered file itself, so per-item rounding cannot push it over the budget.
        if estimate_tokens(render_lessons(chosen + [lesson])) > budget:
            break
        chosen.append(lesson)
    text = render_lessons(chosen)
    return Context("curated_file", text, estimate_tokens(text), [l["id"] for l in chosen])


def whole_set_context(query: dict, visible: list[dict], cap: int | None = None) -> Context:
    """Every visible lesson. With ``cap`` set, an oversized set raises instead of being truncated."""
    ordered = sorted(visible, key=lambda l: (_ts(l["created_at"]).timestamp(), l["id"]))
    text = render_lessons(ordered)
    tokens = estimate_tokens(text)
    if cap is not None and tokens > cap:
        raise ArmUnavailable(f"whole lesson set is {tokens} tokens, over the cap of {cap}")
    return Context("whole_set", text, tokens, [l["id"] for l in ordered])


def long_file_context(query: dict, visible: list[dict], max_bytes: int = LONG_FILE_BYTES) -> Context:
    """The newest lessons, uncurated, while the rendered file fits ``max_bytes``.

    Stands in for an instruction file that collects lessons without choosing
    among them, at the largest size a common harness loads by default. The
    every-lesson file it replaces did not fit any context window (pilot).
    """
    ordered = sorted(visible, key=lambda l: (-_ts(l["created_at"]).timestamp(), l["id"]))
    chosen: list[dict] = []
    for lesson in ordered:
        if len(render_lessons(chosen + [lesson]).encode("utf-8")) > max_bytes:
            break
        chosen.append(lesson)
    text = render_lessons(chosen)
    return Context("long_file", text, estimate_tokens(text), [l["id"] for l in chosen])


def no_memory_context(query: dict, visible: list[dict]) -> Context:
    return Context("no_memory", "", 0, [])


AGENT_ARMS = ("memento_lexical", "memento_paths", "bm25", "embeddings", "curated_file", "long_file", "no_memory")


def build_context(arm: str, query: dict, visible: list[dict], clusters: dict, *,
                  whole_cap: int | None = None, embed_cache: Path | None = None) -> Context:
    if arm in RETRIEVAL_ARMS:
        kwargs = {"cache_dir": embed_cache} if arm == "embeddings" else {}
        return top_k_context(arm, query, visible, **kwargs)
    if arm == "curated_file":
        return curated_context(query, visible, clusters)
    if arm == "long_file":
        return long_file_context(query, visible)
    if arm == "whole_set":
        return whole_set_context(query, visible, cap=whole_cap)
    if arm == "no_memory":
        return no_memory_context(query, visible)
    raise KeyError(arm)
