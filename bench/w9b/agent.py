"""Agent-level review and blind grading for the repeated-correction benchmark.

The agent sees a pull request's file path, the diff hunk a reviewer commented
on, and the lessons an arm supplies. It never sees the reviewer's comment or the
arm's name. The grader sees the reviewer's comment and the review, never the
arm. Every call goes through ``claude -p`` with tools disabled, and every output
is cached by a hash of (prompt version, model, prompt).

``plumbing`` runs each arm on a few queries and reports only whether reviews
and grades completed and parsed, with context sizes. It computes no score:
the pilot must not inspect arm results.

``run`` is the scored run: every query in sample.json (see sample.py) times
every runnable agent arm, one review and one grade each, appended to
agent_results.jsonl at the cache root. It is resumable and prints counts
only; score.py computes the results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import arms  # noqa: E402

MODEL = "opus"
REVIEW_VERSION = "r1"
GRADE_VERSION = "gr1"
MAX_CONCURRENT = 2

REVIEW_SYSTEM = "You are an experienced code reviewer for this repository. Reply with review comments only."
REVIEW_PROMPT = """Review this change to `{path}`.

Diff hunk:
```
{diff_hunk}
```

{lessons_block}Write the review comments you would leave on this hunk. Be specific and brief. If you have no comment, say so."""
LESSONS_BLOCK = """Lessons from earlier reviews in this repository (they may or may not apply):

{lessons}

"""

GRADE_SYSTEM = "You grade code reviews against a reference review comment. Reply with JSON only."
GRADE_PROMPT = """Reference comment, written by the human reviewer of this change:
<<<
{reference}
>>>

Candidate review, written by someone who did not see the reference:
<<<
{review}
>>>

Answer three questions:
1. raised_point: does the candidate raise the same point as the reference (the same problem or requested change), even in different words?
2. reference_states_reason: does the reference comment give a reason for its point?
3. reason_compatible: if the reference states a reason and the candidate raised the point, does the candidate give a compatible reason? Use null when the reference states no reason or the point was not raised.

Reply with exactly one JSON object: {{"raised_point": true|false, "reference_states_reason": true|false, "reason_compatible": true|false|null}}"""


def review_prompt(query: dict, context: arms.Context) -> str:
    block = LESSONS_BLOCK.format(lessons=context.text) if context.text else ""
    return REVIEW_PROMPT.format(path=query["path"], diff_hunk=query["diff_hunk"], lessons_block=block)


def grade_prompt(reference_text: str, review_text: str) -> str:
    return GRADE_PROMPT.format(reference=reference_text.strip(), review=review_text.strip())


# Model calls and cache

def _cache_key(version: str, prompt: str, system: str) -> str:
    return hashlib.sha256(json.dumps([version, MODEL, system, prompt]).encode("utf-8")).hexdigest()


def _run_claude(prompt: str, system: str, cwd: Path) -> str:
    cwd.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["claude", "-p", "--model", MODEL, "--tools", "", "--strict-mcp-config",
                           "--no-session-persistence", "--system-prompt", system, "--output-format", "json"],
                          input=prompt, capture_output=True, text=True, timeout=600, cwd=cwd)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:200]}")
    return json.loads(proc.stdout).get("result", "")


_key_locks: dict[str, "threading.Lock"] = {}
_key_locks_guard = None


def _lock_for(key: str):
    global _key_locks_guard
    if _key_locks_guard is None:
        _key_locks_guard = threading.Lock()
    with _key_locks_guard:
        return _key_locks.setdefault(key, threading.Lock())


def cached_call(cache: Path, version: str, prompt: str, system: str, runner=_run_claude) -> str:
    """Cached model call. Identical prompts in flight share one call; writes are atomic."""
    key = _cache_key(version, prompt, system)
    path = cache / "agent-cache" / version / f"{key}.json"
    with _lock_for(str(path)):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["output"]
        output = runner(prompt, system, cache / "agent-cwd")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".tmp{threading.get_ident()}")
        tmp.write_text(json.dumps({"version": version, "model": MODEL, "output": output}), encoding="utf-8")
        tmp.replace(path)
        return output


def review(query: dict, context: arms.Context, cache: Path, runner=_run_claude) -> str:
    return cached_call(cache, REVIEW_VERSION, review_prompt(query, context), REVIEW_SYSTEM, runner)


def parse_grade(text: str) -> dict:
    """Parse the grader's JSON, tolerating code fences and surrounding prose. Raises ValueError otherwise."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("no JSON object in grader output")
        candidate = text[start:end + 1]
    data = json.loads(candidate)
    if not isinstance(data.get("raised_point"), bool) or not isinstance(data.get("reference_states_reason"), bool):
        raise ValueError("grader output missing boolean fields")
    rc = data.get("reason_compatible")
    if rc is not None and not isinstance(rc, bool):
        raise ValueError("reason_compatible must be true, false or null")
    return {"raised_point": data["raised_point"], "reason_compatible": rc,
            "reference_states_reason": data["reference_states_reason"]}


def grade(reference_text: str, review_text: str, cache: Path, runner=_run_claude) -> dict:
    return parse_grade(cached_call(cache, GRADE_VERSION, grade_prompt(reference_text, review_text), GRADE_SYSTEM, runner))


# Plumbing check

def plumbing(cache: Path, n: int = 5, seed: int = 20260927, whole_cap: int | None = None,
             runner=_run_claude, max_workers: int = MAX_CONCURRENT) -> dict:
    """Run every arm on ``n`` queries; report completion and sizes only, never a score."""
    lessons, queries, clusters = arms.load_dataset(cache)
    eligible = sorted((q for q in queries if q.get("relevant")), key=lambda q: q["id"])
    picked = random.Random(seed).sample(eligible, min(n, len(eligible)))
    report = {"queries": len(picked), "arms": {}}
    jobs = []
    for q in picked:
        visible, unknown = arms.visible_lessons_counted(q, lessons)
        for arm in arms.AGENT_ARMS:
            entry = report["arms"].setdefault(arm, {"contexts": 0, "reviews_ok": 0, "grades_ok": 0, "errors": [],
                                                    "context_tokens": [], "unavailable": None,
                                                    "excluded_unknown_text": 0})
            entry["excluded_unknown_text"] += unknown
            try:
                ctx = arms.build_context(arm, q, visible, clusters, whole_cap=whole_cap,
                                         embed_cache=cache / "embed-cache")
            except arms.ArmUnavailable as exc:
                entry["unavailable"] = str(exc)
                continue
            entry["contexts"] += 1
            entry["context_tokens"].append(ctx.tokens)
            jobs.append((arm, q, ctx))

    def run(job):
        arm, q, ctx = job
        try:
            text = review(q, ctx, cache, runner)
        except Exception as exc:  # reported, not raised
            return arm, False, False, f"review: {exc}"
        try:
            grade(q["reference_text"], text, cache, runner)  # cached raw; never summarized here
        except Exception as exc:
            return arm, True, False, f"grade: {exc}"
        return arm, True, True, ""

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for arm, review_ok, grade_ok, err in pool.map(run, jobs):
            entry = report["arms"][arm]
            entry["reviews_ok"] += review_ok
            entry["grades_ok"] += grade_ok
            if err:
                entry["errors"].append(err[:200])
    return report


# Scored run

NOT_RUN = {"memento_paths": "paths scoping not built yet; runs when it ships (spec changelog)"}
RUN_ARMS = tuple(a for a in arms.AGENT_ARMS if a not in NOT_RUN)


def require_embeddings() -> None:
    """Fail loudly before any model call if the embedding arm cannot run here."""
    try:
        import fastembed  # noqa: F401
        from memento_bench.embed import EmbeddingArm  # noqa: F401
    except ImportError as exc:
        raise SystemExit(f"the embeddings arm needs fastembed in this interpreter ({exc}); "
                         "run with the bench interpreter, for example ~/.cache/memento-bench/venv/bin/python")


def _done_jobs(results_path: Path) -> set[tuple[str, str, str]]:
    if not results_path.exists():
        return set()
    done = set()
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            done.add((r["repo"], r["query_id"], r["arm"]))
    return done


def run(cache_root: Path, runner=_run_claude, max_workers: int = MAX_CONCURRENT, arm_names=RUN_ARMS,
        progress_every: int = 25, check_embeddings: bool = True) -> dict:
    """Review and grade every sampled query under every runnable arm. Returns counts only."""
    if check_embeddings and "embeddings" in arm_names:
        require_embeddings()
    sample = json.loads((cache_root / "sample.json").read_text(encoding="utf-8"))
    results_path = cache_root / "agent_results.jsonl"
    done = _done_jobs(results_path)
    by_repo: dict[str, list[str]] = {}
    for entry in sample["sample"]:
        by_repo.setdefault(entry["repo"], []).append(entry["query_id"])

    jobs = []
    for repo, qids in sorted(by_repo.items()):
        cache = cache_root / repo.replace("/", "__")
        lessons, queries, clusters = arms.load_dataset(cache)
        qmap = {q["id"]: q for q in queries}
        for qid in qids:
            q = qmap[qid]
            visible, unknown = arms.visible_lessons_counted(q, lessons)
            for arm in arm_names:
                if (repo, qid, arm) in done:
                    continue
                ctx = arms.build_context(arm, q, visible, clusters, embed_cache=cache / "embed-cache")
                jobs.append((repo, cache, q, arm, ctx, unknown))

    lock = threading.Lock()
    counts = {"jobs": len(jobs), "already_done": len(done), "completed": 0, "failed": 0}

    def one(job):
        repo, cache, q, arm, ctx, unknown = job
        try:
            prompt = review_prompt(q, ctx)
            text = review(q, ctx, cache, runner)
            g = grade(q["reference_text"], text, cache, runner)
        except Exception as exc:  # counted and reported; the job reruns on the next invocation
            with lock:
                counts["failed"] += 1
                print(f"failed: {repo} {q['id']} {arm}: {str(exc)[:160]}", file=sys.stderr, flush=True)
            return
        row = {"repo": repo, "query_id": q["id"], "arm": arm, "context_tokens": ctx.tokens,
               "context_lesson_ids": ctx.lesson_ids, "excluded_unknown_text": unknown,
               "review_key": _cache_key(REVIEW_VERSION, prompt, REVIEW_SYSTEM),
               "review_version": REVIEW_VERSION, "grade_version": GRADE_VERSION, "grade": g}
        with lock:
            with results_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            counts["completed"] += 1
            finished = counts["completed"] + counts["failed"]
            if finished % progress_every == 0 or finished == counts["jobs"]:
                print(f"progress: {finished}/{counts['jobs']} jobs, {counts['failed']} failed", file=sys.stderr, flush=True)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(one, jobs))
    counts["not_run"] = NOT_RUN
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plumbing", help="run every arm on a few queries; completion and sizes only")
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--seed", type=int, default=20260927)
    p.add_argument("--whole-cap", type=int, default=None, help="token cap for the whole-set arm; over it the arm reports unavailable")
    r = sub.add_parser("run", help="scored run over sample.json; counts only, never a rate")
    r.add_argument("--cache", type=Path, required=True, help="cache root holding sample.json and one directory per repository")
    args = parser.parse_args(argv)
    if args.cmd == "run":
        counts = run(args.cache)
        print(json.dumps(counts, indent=1))
        return 1 if counts["failed"] else 0
    report = plumbing(args.cache, args.n, args.seed, args.whole_cap)
    print(json.dumps(report, indent=1))
    failed = any(e["errors"] for e in report["arms"].values())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
