"""Write the benchmark's publishable files (spec: README.md, "Publishing").

Reads a build and scoring cache and writes only identifiers, hashes, labels,
grades and aggregate results. Comment text, diff hunks and model outputs stay
in the cache.

Per repository (directory named owner__repo):
  comments.csv     every collected comment: id, pull request, created_at,
                   whether it is a top-level human comment, SHA-256 of its body
  pairs.csv        every candidate pair: earlier and later comment id, BM25
                   score, first-stage decision, final label
  queries.csv      every query: id, pull request, opened_at, whether it is
                   after the agent's cutoff, and its relevant lesson ids
  retrieval_runs.json  each retrieval arm's ranked lesson ids per query
  label_checks/    every label check round, including rounds for label sets
                   that were not used (pair ids and scores only)

At the output root:
  sample.json, agent_results.jsonl, results.json, results.md

Usage:
  python publish.py --cache CACHE_ROOT --out OUT_DIR [--superseded-checks DIR ...]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

ROOT_FILES = ("sample.json", "agent_results.jsonl", "results.json", "results.md")
TEXT_KEYS = {"body", "diff_hunk", "reference_text", "output", "situation", "text", "note"}


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


MAX_STRING = 100  # ids, hashes, timestamps, versions and short author notes fit; comment or review text does not


def _no_text(value, where: str) -> None:
    """Refuse to publish a structure that carries text: a text-named field, or any long string."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in TEXT_KEYS and isinstance(item, str) and len(item) > 60:
                raise SystemExit(f"{where}: field {key!r} holds text; not publishing")
            _no_text(key, where)
            _no_text(item, where)
    elif isinstance(value, list):
        for item in value:
            _no_text(item, where)
    elif isinstance(value, str) and len(value) > MAX_STRING:
        raise SystemExit(f"{where}: a {len(value)}-character string looks like text; not publishing")


def _write_csv(path: Path, header: list[str], rows) -> int:
    count = 0
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def publish_repo(cache: Path, out: Path, superseded: list[Path]) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    comments = _jsonl(cache / "comments.jsonl")
    n_comments = _write_csv(out / "comments.csv", ["id", "pr", "created_at", "top_level_human", "body_sha256"], (
        [c["id"], c["pr"], c["created_at"], int(not c.get("in_reply_to_id") and not c.get("is_bot")),
         hashlib.sha256(c["body"].encode()).hexdigest()] for c in comments))

    labels = json.loads((cache / "labels.json").read_text())
    final = labels["decisions"]
    stage_one = _first_stage(cache, labels)
    pairs = _jsonl(cache / "pairs.jsonl")
    missing = [p["id"] for p in pairs if p["id"] not in final]
    if missing:
        raise SystemExit(f"{len(missing)} candidate pairs have no final label; not publishing")
    n_pairs = _write_csv(out / "pairs.csv", ["earlier", "later", "bm25", "first_stage_same", "same"], (
        [p["earlier"], p["later"], p["bm25"], int(stage_one[p["id"]]), int(final[p["id"]])] for p in pairs))

    queries = _jsonl(cache / "queries.jsonl")
    n_queries = _write_csv(out / "queries.csv", ["id", "pr", "pr_opened_at", "post_cutoff", "relevant"], (
        [q["id"], q["pr"], q["pr_opened_at"], int(q["post_cutoff"]), ";".join(q["relevant"])] for q in queries))

    runs = json.loads((cache / "retrieval_runs.json").read_text())
    _no_text(runs, "retrieval_runs.json")
    (out / "retrieval_runs.json").write_text(json.dumps(runs, sort_keys=True) + "\n")

    checks = out / "label_checks"
    checks.mkdir(exist_ok=True)
    for path in sorted(cache.glob("label_check_round*.json")) + superseded:
        data = json.loads(path.read_text())
        _no_text(data, str(path))
        (checks / path.name).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    return {"comments": n_comments, "pairs": n_pairs, "same": sum(final.values()), "queries": n_queries,
            "label_checks": sorted(p.name for p in checks.iterdir())}


def _first_stage(cache: Path, labels: dict) -> dict[str, bool]:
    """First-stage decisions, read back from the decision cache with every model call disabled.

    Also checks that the published labels are exactly "first stage same and
    confirmed", so a stale or hand-edited labels.json is refused.
    """
    import build

    def refuse(*_args, **_kwargs):
        raise SystemExit("publish: a decision is missing from the cache; a model call would be needed")

    build._tf_call = build._codex_call = build._grader_call = refuse
    pairs = _jsonl(cache / "pairs.jsonl")
    by_id = {r["id"]: r for r in build._lesson_rows(cache)}
    first = build._decide_all(cache, labels["labeler"], pairs, by_id, "publish")
    positives = [p for p in pairs if first.get(p["id"])]
    second = build._decide_all(cache, labels["confirmer"], positives, by_id, "publish")
    rebuilt = {k: bool(v and second.get(k)) for k, v in first.items()}
    if rebuilt != labels["decisions"]:
        raise SystemExit("publish: labels.json does not match the cached decisions")
    return first


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--superseded-checks", type=Path, nargs="*", default=[])
    args = p.parse_args(argv)
    results = json.loads((args.cache / "results.json").read_text())
    summary = {}
    for repo in results["repositories"]:
        summary[repo] = publish_repo(args.cache / repo.replace("/", "__"), args.out / repo.replace("/", "__"),
                                     [c for c in args.superseded_checks if repo.replace("/", "__") in str(c)])
    for name in ROOT_FILES:
        src = args.cache / name
        if name.endswith(".json"):
            _no_text(json.loads(src.read_text()), name)
        elif name.endswith(".jsonl"):
            _no_text(_jsonl(src), name)
        shutil.copy2(src, args.out / name)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
