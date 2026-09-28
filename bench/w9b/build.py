"""Build the repeated-correction dataset for one repository (pilot and full run).

Stages, each cached under --cache so a rerun with unchanged inputs makes no
new API or model call:

  collect     review comments, pull request open dates, edit history (GitHub)
  candidates  5 earlier, lexically similar comments per comment (BM25, no model)
  bakeoff     both labelers decide the same 100 pairs; the grader judges them blind
  label       the chosen labeler decides every candidate pair; a second model
              re-decides the pairs it called the same
  check       the grader judges a stratified sample of the labeler's decisions
  situations  the labeler writes a one-line situation for every lesson
  yield       clusters, queries, and the post-cutoff query count

Comment text lives only in the cache directory, which must stay private.
Token Factory calls run at most 3 at a time; grader calls at most 2.

Usage: python build.py <stage> --repo owner/name --cache DIR [--labeler MODEL]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE / "feasibility"))

from count_review_comments import WINDOW_END, WINDOW_START, _get, _is_bot, _token  # noqa: E402
from memento_bench.text import tokens  # noqa: E402

API = "https://api.github.com"
TF_URL = "https://api.tokenfactory.us-north1.nebius.com/v1/chat/completions"
LABELERS = ("zai-org/GLM-5.3-Flash", "deepseek-ai/DeepSeek-V4.1-Flash")
CUTOFF = "2026-07-01T00:00:00Z"
CANDIDATES_PER_COMMENT = 5
BATCH = 20
TF_WORKERS = 3  # approved exception: at most 3 concurrent Token Factory calls
GRADER_WORKERS = 2
PAIR_VERSION = "pair-v3"  # grader and labeler share one question (v3 fixed the level of "same")
LABEL_VERSION = "pair-v3"
SITUATION_VERSION = "situation-v1"
SEED = 20260927
# Both labelers run at low reasoning effort: at default effort GLM-5.3-Flash spent the whole
# token budget reasoning on 20-pair batches and returned nothing (pilot, 2026-09-27).
TF_PARAMS = {"reasoning_effort": "low"}

PAIR_PROMPT = """You are labeling code review comments from one repository.

Each item below is a pair of review comments left on two different pull requests. Decide whether both comments make the same correction.

Two comments make the same correction when one reusable instruction covers both: an instruction a maintainer could write as a single line in the project's contributing guide, and that a contributor who had learned it from the first comment would have followed in the second case. Examples at the right level: "make repeated test cases table-driven", "delete unused code instead of leaving it", "code comments explain why, not what the code does", "write Remote-Write with a hyphen and its version number".

First write that shared instruction in at most 15 words. If no single instruction at that level covers both comments, the answer is false.

These are not the same correction:
- Two renames to different names, or two code suggestions that change different things, unless both apply the same written rule.
- The same general topic (performance, naming, tests, docs) with different instructions.
- A question, praise, a link without a request, or a reply to discussion.
- Two unrelated typo or wording fixes.

Return only JSON: {{"decisions": [{{"id": "<pair id>", "instruction": "<shared instruction or empty>", "same": true or false}}, ...]}} with exactly one entry for every pair id.

{items}"""

LABEL_PROMPT = PAIR_PROMPT

SITUATION_PROMPT = """You are writing retrieval cues for lessons learned from code review.

For each review comment below, write one line of at most 20 words describing the moment when the lesson applies, as a developer about to make that kind of change would recognize it. Describe the situation, not the correction, and do not quote the comment.

Return only JSON: {{"situations": [{{"id": "<comment id>", "situation": "<one line>"}}, ...]}} with exactly one entry for every id.

{items}"""

GRADER_SYSTEM = "You label pairs of code review comments. Reply with JSON only."

_tf_gate = threading.Semaphore(TF_WORKERS)


class EmptyReply(RuntimeError):
    """The model returned no content, usually because reasoning used the budget."""
_log_lock = threading.Lock()


# ----- small helpers -------------------------------------------------------

def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def _sha(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _clip(text: str, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + " [...]"


def _hunk_tail(hunk: str, lines: int = 12) -> str:
    return "\n".join((hunk or "").splitlines()[-lines:])


def _extract_json(text: str):
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start:end + 1])


def _log_call(cache: Path, row: dict) -> None:
    with _log_lock:
        with (cache / "calls.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


# ----- collect -------------------------------------------------------------

def _graphql(query: str, token: str) -> dict:
    body = json.dumps({"query": query}).encode()
    for attempt in range(6):
        req = urllib.request.Request(f"{API}/graphql", data=body, headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            if data.get("errors") and not data.get("data"):
                raise RuntimeError(str(data["errors"])[:300])
            return data.get("data") or {}
        except urllib.error.HTTPError as err:
            if err.code in (403, 429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt * 5, 120))
                continue
            raise
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    raise RuntimeError("graphql: giving up after retries")


def collect(repo: str, cache: Path) -> None:
    token = _token()
    out = cache / "comments.jsonl"
    if not out.exists():
        rows = []
        url = f"{API}/repos/{repo}/pulls/comments?since={WINDOW_START}&sort=created&direction=asc&per_page=100"
        while url:
            page, url = _get(url, token)
            for c in page:
                if not (WINDOW_START <= c["created_at"] < WINDOW_END):
                    continue
                rows.append({
                    "id": str(c["id"]), "node_id": c["node_id"],
                    "pr": int(c["pull_request_url"].rsplit("/", 1)[1]),
                    "created_at": c["created_at"], "updated_at": c["updated_at"],
                    "is_bot": _is_bot(c.get("user")), "path": c.get("path") or "",
                    "diff_hunk": c.get("diff_hunk") or "", "body": c.get("body") or "",
                    "in_reply_to_id": str(c["in_reply_to_id"]) if c.get("in_reply_to_id") else None,
                })
        _write_jsonl(out, rows)
    rows = _jsonl(out)

    pr_path = cache / "pr_opened.json"
    opened = _read(pr_path) if pr_path.exists() else {}
    owner, name = repo.split("/")
    missing = sorted({r["pr"] for r in rows} - {int(k) for k in opened})
    for i in range(0, len(missing), 50):
        chunk = missing[i:i + 50]
        fields = " ".join(f"p{n}: pullRequest(number: {n}) {{ createdAt }}" for n in chunk)
        data = _graphql(f'{{ repository(owner: "{owner}", name: "{name}") {{ {fields} }} }}', token)
        repo_data = data.get("repository") or {}
        for n in chunk:
            node = repo_data.get(f"p{n}")
            if node:
                opened[str(n)] = node["createdAt"]
        _write(pr_path, opened)

    edits_path = cache / "edits.json"
    edits = _read(edits_path) if edits_path.exists() else {}
    wanted = [r for r in rows if not r["is_bot"] and not r["in_reply_to_id"]
              and _seconds_between(r["created_at"], r["updated_at"]) > 60 and r["id"] not in edits]
    for i in range(0, len(wanted), 50):
        chunk = wanted[i:i + 50]
        ids = ", ".join(f'"{r["node_id"]}"' for r in chunk)
        query = ("{ nodes(ids: [%s]) { ... on PullRequestReviewComment { id "
                 "userContentEdits(first: 50) { nodes { editedAt diff } } } } }" % ids)
        try:
            nodes = _graphql(query, token).get("nodes") or []
        except RuntimeError:
            nodes = []
        by_node = {n["id"]: n for n in nodes if n}
        for r in chunk:
            node = by_node.get(r["node_id"])
            if node is None:
                edits[r["id"]] = {"status": "unavailable", "versions": []}
            else:
                versions = sorted((e for e in node["userContentEdits"]["nodes"] if e),
                                  key=lambda e: e["editedAt"])
                edits[r["id"]] = {"status": "ok", "versions": versions}
        _write(edits_path, edits)

    human_top = [r for r in rows if not r["is_bot"] and not r["in_reply_to_id"]]
    print(json.dumps({"comments": len(rows), "human_top_level": len(human_top), "prs": len({r["pr"] for r in rows}),
                      "pr_dates": len(opened), "edited_checked": len(edits),
                      "edit_history_unavailable": sum(v["status"] == "unavailable" for v in edits.values())}))


def _seconds_between(a: str, b: str) -> float:
    from datetime import datetime
    fmt = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))  # noqa: E731
    return (fmt(b) - fmt(a)).total_seconds()


def _lesson_rows(cache: Path) -> list[dict]:
    """Top-level human comments, the lesson and query pool."""
    edits = _read(cache / "edits.json") if (cache / "edits.json").exists() else {}
    out = []
    for r in _jsonl(cache / "comments.jsonl"):
        if r["is_bot"] or r["in_reply_to_id"] or not r["body"].strip():
            continue
        e = edits.get(r["id"])
        history = []
        if e and e["status"] == "unavailable":
            history = [{"edited_at": r["updated_at"], "previous_text": None}]
        elif e and len(e["versions"]) > 1:
            vs = e["versions"]
            history = [{"edited_at": vs[i]["editedAt"], "previous_text": vs[i - 1]["diff"]} for i in range(1, len(vs))]
        out.append({**r, "edits": history})
    return out


# ----- candidates ----------------------------------------------------------

def candidates(cache: Path) -> None:
    import math
    lessons = sorted(_lesson_rows(cache), key=lambda r: (r["created_at"], r["id"]))
    docs = [tokens(r["body"]) for r in lessons]
    df = defaultdict(int)
    for d in docs:
        for t in set(d):
            df[t] += 1
    n = len(docs)
    avg = sum(map(len, docs)) / max(n, 1)
    postings = defaultdict(list)
    for i, d in enumerate(docs):
        counts = defaultdict(int)
        for t in d:
            counts[t] += 1
        for t, tf in counts.items():
            postings[t].append((i, tf, len(d)))
    k1, b = 1.2, 0.75
    pairs = []
    for j, later in enumerate(lessons):
        scores = defaultdict(float)
        for t in set(docs[j]):
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            for i, tf, dl in postings[t]:
                if i >= j:
                    break
                if lessons[i]["pr"] == later["pr"]:
                    continue
                scores[i] += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avg))
        top = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:CANDIDATES_PER_COMMENT]
        for i, s in top:
            pairs.append({"id": f"{lessons[i]['id']}:{later['id']}", "earlier": lessons[i]["id"],
                          "later": later["id"], "bm25": round(s, 4)})
    _write_jsonl(cache / "pairs.jsonl", pairs)
    print(json.dumps({"lessons": n, "pairs": len(pairs)}))


# ----- model calls ---------------------------------------------------------

def _tf_call(cache: Path, model: str, prompt: str, stage: str) -> str:
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise RuntimeError("NEBIUS_API_KEY is not set")
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 16000, "temperature": 0, **TF_PARAMS}).encode()
    empties = 0
    for attempt in range(5):
        req = urllib.request.Request(TF_URL, data=body, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        start = time.time()
        try:
            with _tf_gate:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read())
            usage = data.get("usage") or {}
            content = (data["choices"][0]["message"].get("content") or "")
            _log_call(cache, {"stage": stage, "model": model, "params": TF_PARAMS, "seconds": round(time.time() - start, 2),
                              "prompt_tokens": usage.get("prompt_tokens"),
                              "completion_tokens": usage.get("completion_tokens"),
                              "status": "ok" if content.strip() else "empty"})
            if content.strip():
                return content
            empties += 1
            if empties >= 2:
                raise EmptyReply(f"{model}: reasoning used the whole budget twice")
        except urllib.error.HTTPError as err:
            _log_call(cache, {"stage": stage, "model": model, "params": TF_PARAMS, "seconds": round(time.time() - start, 2),
                              "status": f"http {err.code}"})
            if err.code not in (408, 429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError) as err:
            _log_call(cache, {"stage": stage, "model": model, "params": TF_PARAMS, "seconds": round(time.time() - start, 2),
                              "status": f"network {type(err).__name__}"})
        time.sleep(min(2 ** attempt * 3, 60))
    raise RuntimeError(f"{model}: no usable reply after retries")


def _grader_call(cache: Path, prompt: str, stage: str) -> str:
    cwd = cache / "grader-cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    start = time.time()
    proc = subprocess.run(["claude", "-p", "--model", "opus", "--tools", "", "--strict-mcp-config",
                           "--no-session-persistence", "--system-prompt", GRADER_SYSTEM, "--output-format", "json"],
                          input=prompt, capture_output=True, text=True, timeout=900, cwd=cwd)
    ok = proc.returncode == 0
    _log_call(cache, {"stage": stage, "model": "claude-opus (claude -p)", "seconds": round(time.time() - start, 2),
                      "status": "ok" if ok else f"exit {proc.returncode}"})
    if not ok:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip()[:200]}")
    return json.loads(proc.stdout).get("result", "")


def _codex_call(cache: Path, prompt: str, stage: str) -> str:
    import tempfile
    cwd = cache / "grader-cwd"
    cwd.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("r", suffix=".txt", dir=cwd, delete=False) as handle:
        last = Path(handle.name)
    start = time.time()
    try:
        proc = subprocess.run(["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only", "-C", str(cwd),
                               "-o", str(last), "-"], input=GRADER_SYSTEM + "\n\n" + prompt,
                              capture_output=True, text=True, timeout=900)
        ok = proc.returncode == 0
        _log_call(cache, {"stage": stage, "model": "gpt-6-astra (codex exec)", "seconds": round(time.time() - start, 2),
                          "status": "ok" if ok else f"exit {proc.returncode}"})
        if not ok:
            raise RuntimeError(f"codex exited {proc.returncode}: {proc.stderr.strip()[-200:]}")
        return last.read_text(encoding="utf-8")
    finally:
        last.unlink(missing_ok=True)


def _pair_items(batch: list[dict], by_id: dict) -> tuple[str, dict]:
    labels, parts = {}, []
    for k, pair in enumerate(batch, 1):
        pid = f"p{k}"
        labels[pid] = pair["id"]
        a, b = by_id[pair["earlier"]], by_id[pair["later"]]
        parts.append(f"### Pair {pid}\n"
                     f"Comment A (file {a['path']}):\n```diff\n{_hunk_tail(a['diff_hunk'])}\n```\n{_clip(a['body'], 1200)}\n\n"
                     f"Comment B (file {b['path']}):\n```diff\n{_hunk_tail(b['diff_hunk'])}\n```\n{_clip(b['body'], 1200)}")
    return "\n\n".join(parts), labels


def _decide(cache: Path, who: str, batch: list[dict], by_id: dict, stage: str) -> dict[str, bool]:
    """Decisions for one batch, cached; a malformed reply splits the batch in half."""
    items, labels = _pair_items(batch, by_id)
    version = PAIR_VERSION if who == "grader" else LABEL_VERSION
    prompt = (PAIR_PROMPT if who == "grader" else LABEL_PROMPT).format(items=items)
    params = "" if who in ("grader", CODEX) else json.dumps(TF_PARAMS, sort_keys=True)
    path = cache / "decisions" / f"{_sha(version, who, params, prompt)}.json"
    if path.exists():
        return _read(path)["decisions"]
    try:
        if who == "grader":
            reply = _grader_call(cache, prompt, stage)
        elif who == CODEX:
            reply = _codex_call(cache, prompt, stage)
        else:
            reply = _tf_call(cache, who, prompt, stage)
        parsed = {d["id"]: bool(d["same"]) for d in _extract_json(reply)["decisions"]}
        if set(parsed) != set(labels):
            raise ValueError("reply ids do not match")
    except RuntimeError as err:
        # A failed call (out of credits, auth, repeated HTTP errors) is not fixed by a smaller
        # batch; stop the run loudly. Only an empty reasoning-burn reply is worth splitting.
        if not isinstance(err, EmptyReply) or len(batch) == 1:
            raise
        half = len(batch) // 2
        return {**_decide(cache, who, batch[:half], by_id, stage), **_decide(cache, who, batch[half:], by_id, stage)}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        if len(batch) == 1:
            _log_call(cache, {"stage": stage, "model": who, "status": "unparseable single", "pair": batch[0]["id"]})
            return {}
        half = len(batch) // 2
        return {**_decide(cache, who, batch[:half], by_id, stage), **_decide(cache, who, batch[half:], by_id, stage)}
    result = {labels[k]: v for k, v in parsed.items()}
    _write(path, {"who": who, "version": version, "decisions": result})
    return result


def _decide_all(cache: Path, who: str, pairs: list[dict], by_id: dict, stage: str) -> dict[str, bool]:
    batches = [pairs[i:i + BATCH] for i in range(0, len(pairs), BATCH)]
    width = GRADER_WORKERS if who == "grader" else CODEX_WORKERS if who == CODEX else TF_WORKERS
    out: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=width) as pool:
        for result in pool.map(lambda b: _decide(cache, who, b, by_id, stage), batches):
            out.update(result)
    return out


def _agreement(labeler: dict, grader: dict) -> dict:
    common = [k for k in grader if k in labeler]
    tp = sum(labeler[k] and grader[k] for k in common)
    fp = sum(labeler[k] and not grader[k] for k in common)
    fn = sum(not labeler[k] and grader[k] for k in common)
    agree = sum(labeler[k] == grader[k] for k in common)
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
    return {"pairs": len(common), "accuracy": round(agree / len(common), 4) if common else None,
            "grader_same": sum(grader[k] for k in common), "labeler_same": sum(labeler[k] for k in common),
            "precision_same": round(prec, 4) if prec is not None else None,
            "recall_same": round(rec, 4) if rec is not None else None, "f1_same": round(f1, 4)}


# ----- bakeoff, label, check ----------------------------------------------

def bakeoff(cache: Path) -> None:
    pairs = _jsonl(cache / "pairs.jsonl")
    by_id = {r["id"]: r for r in _lesson_rows(cache)}
    sample = random.Random(SEED).sample(pairs, min(100, len(pairs)))
    grader = _decide_all(cache, "grader", sample, by_id, "bakeoff-grader")
    report = {"pairs": len(sample), "labelers": {}}
    for model in LABELERS:
        report["labelers"][model] = _agreement(_decide_all(cache, model, sample, by_id, f"bakeoff-{model}"), grader)
    f1 = {m: report["labelers"][m]["f1_same"] for m in LABELERS}
    acc = {m: report["labelers"][m]["accuracy"] or 0 for m in LABELERS}
    best = max(LABELERS, key=lambda m: (f1[m], acc[m]))
    if f1[LABELERS[0]] == f1[LABELERS[1]] and acc[LABELERS[0]] == acc[LABELERS[1]]:
        best = LABELERS[0]  # GLM-5.3-Flash on a tie
    report["chosen"] = best
    report["rule"] = "higher F1 on 'same' against the grader, then accuracy; GLM-5.3-Flash on a tie"
    report["labeler_params"] = TF_PARAMS
    report["seconds_per_call"] = _call_seconds(cache)
    _write(cache / "bakeoff.json", report)
    print(json.dumps(report, indent=1))


def _call_seconds(cache: Path) -> dict:
    rows = _jsonl(cache / "calls.jsonl") if (cache / "calls.jsonl").exists() else []
    out = {}
    for model in LABELERS:
        secs = sorted(r["seconds"] for r in rows if r.get("model") == model and r.get("status") == "ok"
                      and r.get("params") == TF_PARAMS and str(r.get("stage", "")).startswith("bakeoff"))
        out[model] = {"calls_ok": len(secs), "median": secs[len(secs) // 2] if secs else None}
    return out


# Confirms the first labeler's positives. DeepSeek-V4.1-Flash reached only 0.69 precision on
# fresh pairs (round 2). GPT-6 Astra passed (round 3, 0.91) but its Codex workspace ran out of
# credits; the larger GLM-5.3 on Token Factory was tried as a replacement and failed (round 4,
# 0.77), so Astra stays the confirmer and a repository waits until it can run.
CODEX = "gpt-6-astra"
CONFIRMER = CODEX
CODEX_WORKERS = 3


def label(cache: Path, labeler: str) -> None:
    """Two stages: the labeler decides every pair; a second family re-decides its positives.

    A pair is the same correction only when both say so. With one labeler, the
    pilot's first label check found 52% precision on "same"; the confirming
    stage raised it on the tuning pairs (see RESULTS.md, "Labels").
    """
    pairs = _jsonl(cache / "pairs.jsonl")
    by_id = {r["id"]: r for r in _lesson_rows(cache)}
    first = _decide_all(cache, labeler, pairs, by_id, "label")
    confirmer = CONFIRMER
    positives = [p for p in pairs if first.get(p["id"])]
    second = _decide_all(cache, confirmer, positives, by_id, "label-confirm")
    undecided = [p["id"] for p in pairs if p["id"] not in first] + [p["id"] for p in positives if p["id"] not in second]
    if undecided:
        # An undecided pair must not silently count as "different"; rerun (decisions are cached).
        raise SystemExit(f"label: {len(undecided)} pairs undecided (for example {undecided[0]}); no labels written")
    decisions = {k: bool(v and second.get(k)) for k, v in first.items()}
    _write(cache / "labels.json", {"labeler": labeler, "confirmer": confirmer, "version": LABEL_VERSION,
                                   "params": TF_PARAMS, "decisions": decisions,
                                   "first_stage_same": sum(first.values()), "confirm_undecided": len(positives) - len(second)})
    print(json.dumps({"pairs": len(pairs), "decided": len(first), "first_stage_same": sum(first.values()),
                      "confirmed_same": sum(decisions.values()), "undecided": len(pairs) - len(first),
                      "confirm_undecided": len(positives) - len(second)}))


def _used_pairs(cache: Path) -> set[str]:
    """Pairs already used by the bakeoff or an earlier check round (tuning), never rechecked."""
    used = {p["id"] for p in random.Random(SEED).sample(_jsonl(cache / "pairs.jsonl"), 100)}
    for f in sorted(cache.glob("label_check_round*.json")):
        used |= set(_read(f).get("pairs", []))
    return used


def check(cache: Path, round_: int) -> None:
    """Grader judges 100 'same' and 100 'different' decisions, blind to the label.

    Each round draws fresh pairs, excluding the bakeoff and earlier rounds, so a
    prompt tuned on one round is judged on pairs it was not tuned on.
    """
    labels = _read(cache / "labels.json")["decisions"]
    out = cache / f"label_check_round{round_}.json"
    used = _used_pairs(cache) - (set(_read(out).get("pairs", [])) if out.exists() else set())
    pairs = {p["id"]: p for p in _jsonl(cache / "pairs.jsonl") if p["id"] not in used}
    rng = random.Random(SEED + round_)
    same = sorted(k for k, v in labels.items() if v and k in pairs)
    diff = sorted(k for k, v in labels.items() if not v and k in pairs)
    pick = rng.sample(same, min(100, len(same))) + rng.sample(diff, min(100, len(diff)))
    rng.shuffle(pick)
    by_id = {r["id"]: r for r in _lesson_rows(cache)}
    grader = _decide_all(cache, "grader", [pairs[k] for k in pick], by_id, "check")
    s_ok = [labels[k] == grader[k] for k in pick if labels[k] and k in grader]
    d_ok = [labels[k] == grader[k] for k in pick if not labels[k] and k in grader]
    share_same = len(same) / max(len(same) + len(diff), 1)
    prec = sum(s_ok) / len(s_ok) if s_ok else None
    npv = sum(d_ok) / len(d_ok) if d_ok else None
    weighted = prec * share_same + npv * (1 - share_same) if prec is not None and npv is not None else None
    report = {"sampled_same": len(s_ok), "sampled_different": len(d_ok), "precision_same": prec,
              "agreement_different": npv, "population_share_same": round(share_same, 4),
              "population_weighted_accuracy": round(weighted, 4) if weighted is not None else None,
              "pass_mark": 0.85,
              "passes": bool(prec is not None and weighted is not None and prec >= 0.85 and weighted >= 0.85),
              "round": round_, "version": LABEL_VERSION, "pairs": pick}
    _write(out, report)
    print(json.dumps(report, indent=1))


# ----- situations and yield -----------------------------------------------

def situations(cache: Path, labeler: str) -> None:
    lessons = _lesson_rows(cache)
    batches = [lessons[i:i + BATCH] for i in range(0, len(lessons), BATCH)]

    def one(batch: list[dict]) -> dict[str, str]:
        items = "\n\n".join(f"### {r['id']} (file {r['path']})\n```diff\n{_hunk_tail(r['diff_hunk'])}\n```\n{_clip(r['body'], 1200)}"
                            for r in batch)
        prompt = SITUATION_PROMPT.format(items=items)
        path = cache / "situations" / f"{_sha(SITUATION_VERSION, labeler, json.dumps(TF_PARAMS, sort_keys=True), prompt)}.json"
        if path.exists():
            return _read(path)
        try:
            got = {s["id"]: s["situation"].strip() for s in _extract_json(_tf_call(cache, labeler, prompt, "situations"))["situations"]}
            got = {k: v for k, v in got.items() if k in {r["id"] for r in batch}}
        except EmptyReply:
            got = {}
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            got = {}
        if len(got) < len(batch) and len(batch) > 1:
            half = len(batch) // 2
            got = {**one(batch[:half]), **one(batch[half:]), **got}
        _write(path, got)
        return got

    out: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=TF_WORKERS) as pool:
        for got in pool.map(one, batches):
            out.update(got)
    missing = [r["id"] for r in lessons if r["id"] not in out]
    if missing:
        raise SystemExit(f"situations: {len(missing)} lessons without a situation line; rerun (batches are cached)")
    _write(cache / "situations.json", {"labeler": labeler, "version": SITUATION_VERSION, "situations": out})
    print(json.dumps({"lessons": len(lessons), "situations": len(out)}))


def build_yield(cache: Path) -> None:
    lessons = {r["id"]: r for r in _lesson_rows(cache)}
    opened = _read(cache / "pr_opened.json")
    labels = _read(cache / "labels.json")["decisions"]
    sits = _read(cache / "situations.json")["situations"] if (cache / "situations.json").exists() else {}
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    direct = defaultdict(set)
    for pid, same in labels.items():
        if same:
            a, b = pid.split(":")
            parent[find(a)] = find(b)
            direct[a].add(b)
            direct[b].add(a)
    groups = defaultdict(list)
    for x in list(parent):
        groups[find(x)].append(x)
    clusters = {f"c{i}": sorted(m) for i, m in enumerate(sorted(groups.values(), key=lambda m: sorted(m)))
                if len({lessons[c]["pr"] for c in m}) >= 2}
    member_of = {c: cid for cid, m in clusters.items() for c in m}

    queries = []
    for cid, members in clusters.items():
        for q in members:
            row = lessons[q]
            pr_open = opened.get(str(row["pr"]))
            if not pr_open:
                continue
            # Relevant lessons are the query's directly confirmed pairs, whose precision the label
            # check measures; cluster membership (used for recurrence counts) can chain across pairs.
            relevant = [c for c in direct.get(q, ()) if lessons[c]["pr"] != row["pr"] and lessons[c]["created_at"] < pr_open]
            if relevant:
                queries.append({"id": q, "pr": row["pr"], "pr_opened_at": pr_open, "path": row["path"],
                                "diff_hunk": row["diff_hunk"], "reference_text": row["body"],
                                "relevant": sorted(relevant), "post_cutoff": pr_open >= CUTOFF})
    _write_jsonl(cache / "lessons.jsonl", [
        {"id": r["id"], "pr": r["pr"], "created_at": r["created_at"], "path": r["path"],
         "paths_glob": (r["path"].rsplit("/", 1)[0] + "/**") if "/" in r["path"] else "**",
         "text": r["body"], "situation": sits.get(r["id"], ""), "edits": r["edits"]}
        for r in sorted(lessons.values(), key=lambda r: (r["created_at"], r["id"]))])
    _write_jsonl(cache / "queries.jsonl", sorted(queries, key=lambda q: (q["pr_opened_at"], q["id"])))
    _write(cache / "clusters.json", {"clusters": clusters,
                                     "member_pr": {c: lessons[c]["pr"] for c in member_of},
                                     "member_created": {c: lessons[c]["created_at"] for c in member_of}})
    sizes = sorted((len(m) for m in clusters.values()), reverse=True)
    report = {"lessons": len(lessons), "clusters": len(clusters), "largest_clusters": sizes[:5],
              "clustered_comments": len(member_of), "queries": len(queries),
              "queries_post_cutoff": sum(q["post_cutoff"] for q in queries), "target_per_repo": 42}
    _write(cache / "yield.json", report)
    print(json.dumps(report, indent=1))


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=["collect", "candidates", "bakeoff", "label", "check", "situations", "yield"])
    p.add_argument("--repo", required=True)
    p.add_argument("--cache", type=Path, required=True)
    p.add_argument("--labeler", choices=LABELERS)
    p.add_argument("--round", type=int, default=2, help="label check round; each round draws fresh pairs")
    args = p.parse_args(argv)
    cache = args.cache / args.repo.replace("/", "__")
    cache.mkdir(parents=True, exist_ok=True)
    if args.stage in ("label", "situations") and not args.labeler:
        chosen = (cache / "bakeoff.json")
        if not chosen.exists():
            p.error("--labeler is required until the bakeoff has run")
        args.labeler = _read(chosen)["chosen"]
    {"collect": lambda: collect(args.repo, cache), "candidates": lambda: candidates(cache),
     "bakeoff": lambda: bakeoff(cache), "label": lambda: label(cache, args.labeler), "check": lambda: check(cache, args.round),
     "situations": lambda: situations(cache, args.labeler), "yield": lambda: build_yield(cache)}[args.stage]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
