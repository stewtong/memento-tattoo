"""Score the repeated-correction benchmark (spec: README.md in this directory).

Two steps:

  retrieve  rank every query's visible lessons with each retrieval arm and cache
            the rankings per repository (retrieval_runs.json). The lexical arms
            run in worker processes; the embedding arm needs fastembed and saves
            its vector cache once per repository.
  score     read the rankings, agent_results.jsonl and sample.json and write
            results.json and results.md at the cache root.

Retrieval level: every query of every included repository, recall@5, hit@5
and MRR with 95% bootstrap intervals, per repository and pooled, split before
and after July 1, 2026. Agent level: the sample, the rate of raising the
reviewer's point per arm, the reason-compatible rate on queries whose reference
states a reason, tokens per arm, and paired bootstrap differences of memento
minus each baseline, resampling queries within each repository.

Usage:
  python score.py retrieve --cache CACHE_ROOT [--workers 6]
  python score.py score --cache CACHE_ROOT
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import arms  # noqa: E402
import power  # noqa: E402
import sample as sampling  # noqa: E402
from memento_bench import metrics as m  # noqa: E402

SEED = 20260927
ROUNDS = 10_000
CI_ROUNDS = 2_000
K = 5
RANK_LIMIT = 50
LEXICAL_ARMS = ("memento_lexical", "bm25")
RETRIEVAL_ARMS = ("memento_lexical", "bm25", "embeddings")
AGENT_ARMS = ("memento_lexical", "bm25", "embeddings", "curated_file", "long_file", "no_memory")
PRIMARY = "memento_lexical"
BASELINES = ("curated_file", "long_file", "no_memory", "bm25", "embeddings")
NOT_RUN = {"memento_paths": "paths scoping not built yet; runs when it ships (spec changelog)"}


# ----- retrieval runs -------------------------------------------------------

def _fingerprint(repo_dir: Path) -> str:
    h = hashlib.sha256()
    for name in ("lessons.jsonl", "queries.jsonl"):
        h.update((repo_dir / name).read_bytes())
    return h.hexdigest()


_W: dict = {}


def _worker_init(repo_dir: str) -> None:
    lessons, queries, _ = arms.load_dataset(Path(repo_dir))
    _W["lessons"] = lessons
    _W["queries"] = {q["id"]: q for q in queries}


def _rank_lexical(qid: str) -> tuple[str, dict, int]:
    q = _W["queries"][qid]
    visible, unknown = arms.visible_lessons_counted(q, _W["lessons"])
    return qid, {arm: arms.RETRIEVAL_ARMS[arm](q, visible, limit=RANK_LIMIT) for arm in LEXICAL_ARMS}, unknown


def retrieve_repo(repo_dir: Path, workers: int = 6, arm_names=RETRIEVAL_ARMS) -> dict:
    out_path = repo_dir / "retrieval_runs.json"
    fp = _fingerprint(repo_dir)
    existing = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else None
    if existing and existing.get("fingerprint") != fp:
        existing = None  # the dataset changed; rank again
    runs = existing["runs"] if existing else {}
    unknown = existing.get("excluded_unknown_text", {}) if existing else {}
    lessons, queries, _ = arms.load_dataset(repo_dir)
    qids = [q["id"] for q in queries]

    todo = [qid for qid in qids if any(qid not in runs.get(a, {}) for a in arm_names if a in LEXICAL_ARMS)]
    if todo and any(a in LEXICAL_ARMS for a in arm_names):
        with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init, initargs=(str(repo_dir),)) as pool:
            for qid, ranked, n_unknown in pool.map(_rank_lexical, todo, chunksize=4):
                for arm, ids in ranked.items():
                    runs.setdefault(arm, {})[qid] = ids
                unknown[qid] = n_unknown

    if "embeddings" in arm_names:
        todo = [q for q in queries if q["id"] not in runs.get("embeddings", {})]
        if todo:
            try:
                from memento_bench.embed import EmbeddingArm
            except ImportError as exc:
                raise SystemExit(f"the embeddings arm needs fastembed in this interpreter ({exc})")
            embed = EmbeddingArm(repo_dir / "embed-cache")
            for q in todo:
                visible, n_unknown = arms.visible_lessons_counted(q, lessons)
                ranked = embed.rank(arms.query_text(q), arms._as_notes(visible), limit=RANK_LIMIT) if visible else []
                runs.setdefault("embeddings", {})[q["id"]] = ranked
                unknown[q["id"]] = n_unknown
            embed.save()

    result = {"fingerprint": fp, "rank_limit": RANK_LIMIT, "runs": runs, "excluded_unknown_text": unknown,
              "ranked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    out_path.write_text(json.dumps(result), encoding="utf-8")
    return {"repo": sampling.repo_name(repo_dir), "queries": len(qids),
            "ranked": {a: len(runs.get(a, {})) for a in arm_names}}


# ----- statistics -----------------------------------------------------------

def stratified_bootstrap_diff(pairs_by_repo: dict[str, list[tuple[float, float]]], *, rounds: int = ROUNDS,
                              seed: int = SEED, alpha: float = 0.05) -> tuple[float, float, float, int]:
    """Mean of a - b over all paired queries, with a percentile interval that resamples within each repository."""
    diffs_by_repo = {r: [a - b for a, b in p] for r, p in pairs_by_repo.items() if p}
    all_diffs = [d for ds in diffs_by_repo.values() for d in ds]
    if not all_diffs:
        return float("nan"), float("nan"), float("nan"), 0
    rng = random.Random(seed)
    n = len(all_diffs)
    means = []
    for _ in range(rounds):
        total = 0.0
        for ds in diffs_by_repo.values():
            total += sum(rng.choices(ds, k=len(ds)))
        means.append(total / n)
    means.sort()
    lo = means[int(rounds * alpha / 2)]
    hi = means[min(rounds - 1, int(rounds * (1 - alpha / 2)))]
    return statistics.fmean(all_diffs), lo, hi, n


def stratified_bootstrap_mean(values_by_repo: dict[str, list[float]], *, rounds: int = CI_ROUNDS,
                              seed: int = SEED) -> tuple[float, float]:
    zeros = {r: [(v, 0.0) for v in vs] for r, vs in values_by_repo.items()}
    _, lo, hi, _ = stratified_bootstrap_diff(zeros, rounds=rounds, seed=seed)
    return lo, hi


def minimum_detectable_difference(n: int, pd: float) -> float | None:
    """Smallest difference detectable with 80% power at two-sided alpha 0.05, for n paired queries.

    Inverts Connor's formula for McNemar's test (power.py): the smallest d in
    (0, pd) whose required sample is at most n, found by bisection. Returns
    None when no difference within (0, pd) is detectable at this n.
    """
    if n <= 0 or not 0 < pd <= 1:
        return None

    def needed(d: float) -> float:
        return (power.Z_ALPHA * pd ** 0.5 + power.Z_BETA * max(pd - d * d, 0.0) ** 0.5) ** 2 / (d * d)

    hi = pd * (1 - 1e-9)
    if needed(hi) > n:
        return None
    lo = 1e-6
    for _ in range(100):
        mid = (lo + hi) / 2
        if needed(mid) > n:
            lo = mid
        else:
            hi = mid
    return hi


def power_statement(pairs_by_repo: dict[str, list[tuple[float, float]]]) -> dict:
    """The sample size actually scored and the difference it can detect (80% power, alpha 0.05)."""
    all_pairs = [p for ps in pairs_by_repo.values() for p in ps]
    n = len(all_pairs)
    observed_pd = sum(1 for a, b in all_pairs if a != b) / n if n else None
    assumed = {f"{pd:.2f}": _r(minimum_detectable_difference(n, pd)) for pd in power.DISCORDANT}
    return {"paired_queries": n, "per_repo": {r: len(ps) for r, ps in sorted(pairs_by_repo.items())},
            "power": 0.80, "alpha_two_sided": 0.05, "method": "Connor (1987) McNemar sample size, inverted (power.py)",
            "mdd_at_assumed_discordance": assumed,
            "observed_discordance": _r(observed_pd),
            "mdd_at_observed_discordance": _r(minimum_detectable_difference(n, observed_pd)) if observed_pd else None}


def decide(diff: float, lo: float, hi: float) -> str:
    """The frozen rule: an advantage needs a higher rate and a 95% interval that excludes zero."""
    if diff > 0 and lo > 0:
        return "advantage"
    if diff < 0 and hi < 0:
        return "no advantage (baseline higher; interval excludes zero)"
    return "no advantage"


def _r(x, nd=4):
    return None if x is None or x != x else round(x, nd)


# ----- scoring --------------------------------------------------------------

def _label_rounds(repo_dir: Path) -> list[dict]:
    rounds = []
    for f in sorted(repo_dir.glob("label_check_round*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        rounds.append({k: d.get(k) for k in ("round", "version", "precision_same", "agreement_different",
                                               "population_weighted_accuracy", "passes", "note")})
    return sorted(rounds, key=lambda r: r["round"] or 0)


def _provenance(repo_dirs: dict[str, Path]) -> dict:
    prov = {"agent_and_grader": {"cli": "claude -p", "model_alias": None, "review_version": None, "grade_version": None},
            "labelers": {}, "memento_tattoo_version": None}
    try:
        import agent
        prov["agent_and_grader"].update(model_alias=agent.MODEL, review_version=agent.REVIEW_VERSION,
                                        grade_version=agent.GRADE_VERSION)
    except ImportError:
        pass
    try:
        import memento_tattoo
        prov["memento_tattoo_version"] = memento_tattoo.__version__
    except ImportError:
        pass
    try:
        import build
        prov["inference_provider_labelers"] = build.TF_URL.split("/v1")[0]
        prov["prompt_versions"] = {"pair": build.PAIR_VERSION, "label": build.LABEL_VERSION,
                                   "situation": build.SITUATION_VERSION}
    except Exception:  # build.py needs its own imports; provenance is best effort beyond the labels files
        pass
    for repo, d in repo_dirs.items():
        entry = {}
        if (d / "labels.json").exists():
            lab = json.loads((d / "labels.json").read_text(encoding="utf-8"))
            entry.update({k: lab.get(k) for k in ("labeler", "confirmer", "version", "params")})
        if (d / "situations.json").exists():
            sit = json.loads((d / "situations.json").read_text(encoding="utf-8"))
            entry["situations"] = {k: sit.get(k) for k in ("labeler", "version")}
        prov["labelers"][repo] = entry
    return prov


def _retrieval_level(repo_dirs: dict[str, Path]) -> dict:
    per = {}  # arm -> slice -> repo -> metric -> values
    counts = {}
    for repo, d in repo_dirs.items():
        runs_path = d / "retrieval_runs.json"
        if not runs_path.exists():
            raise SystemExit(f"{repo}: no retrieval_runs.json; run `score.py retrieve` first")
        runs = json.loads(runs_path.read_text(encoding="utf-8"))
        if runs["fingerprint"] != _fingerprint(d):
            raise SystemExit(f"{repo}: retrieval_runs.json is stale; run `score.py retrieve` again")
        lessons, queries, _ = arms.load_dataset(d)
        skipped = 0
        for q in queries:
            visible_ids = {l["id"] for l in arms.visible_lessons(q, lessons)}
            rel = set(q["relevant"]) & visible_ids
            if not rel:
                skipped += 1
                continue
            for arm in RETRIEVAL_ARMS:
                ranked = runs["runs"].get(arm, {}).get(q["id"])
                if ranked is None:
                    raise SystemExit(f"{repo}: {arm} has no ranking for query {q['id']}")
                vals = {"recall@5": m.recall_at(ranked, rel, K), "hit@5": m.hit_at(ranked, rel, K),
                        "mrr": m.reciprocal_rank(ranked, rel)}
                for sl in ("all", "after_2026-07-01" if q["post_cutoff"] else "before_2026-07-01"):
                    for metric, v in vals.items():
                        per.setdefault(arm, {}).setdefault(sl, {}).setdefault(repo, {}).setdefault(metric, []).append(v)
        counts[repo] = {"queries": len(queries), "skipped_no_visible_relevant": skipped}

    out = {"queries": counts, "arms": {}}
    for arm, slices in per.items():
        out["arms"][arm] = {}
        for sl, repos in slices.items():
            block = {"per_repo": {}, "pooled": {}}
            for repo, mets in repos.items():
                block["per_repo"][repo] = {"n": len(mets["recall@5"])}
                for metric, vs in mets.items():
                    lo, hi = m.bootstrap_ci(vs, seed=SEED, rounds=CI_ROUNDS)
                    block["per_repo"][repo][metric] = {"mean": _r(statistics.fmean(vs)), "ci95": [_r(lo), _r(hi)]}
            for metric in ("recall@5", "hit@5", "mrr"):
                by_repo = {repo: mets[metric] for repo, mets in repos.items()}
                allv = [v for vs in by_repo.values() for v in vs]
                lo, hi = stratified_bootstrap_mean(by_repo)
                block["pooled"][metric] = {"mean": _r(statistics.fmean(allv)), "ci95": [_r(lo), _r(hi)]}
            block["pooled"]["n"] = sum(len(mets["recall@5"]) for mets in repos.values())
            out["arms"][arm][sl] = block
    return out


def _agent_level(cache_root: Path, sample: dict) -> dict:
    rows = [json.loads(line) for line in (cache_root / "agent_results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    sampled = {(e["repo"], e["query_id"]) for e in sample["sample"]}
    res: dict[tuple[str, str], dict[str, dict]] = {}
    for r in rows:
        key = (r["repo"], r["query_id"])
        if key in sampled:
            res.setdefault(key, {})[r["arm"]] = r  # a rerun of the same job keeps its last line
    missing = {arm: sum(1 for k in sampled if arm not in res.get(k, {})) for arm in AGENT_ARMS}

    # A query states a reason when most of its grades say so; ties count as no reason.
    states_reason = {}
    for key, by_arm in res.items():
        votes = [g["grade"]["reference_states_reason"] for g in by_arm.values()]
        states_reason[key] = sum(votes) * 2 > len(votes)

    out = {"sampled_queries": len(sampled), "missing_results": missing, "arms": {}, "comparisons": {}}
    for arm in AGENT_ARMS:
        raised, reason, tokens = {}, {}, []
        for (repo, qid), by_arm in res.items():
            row = by_arm.get(arm)
            if row is None:
                continue
            raised.setdefault(repo, []).append(1.0 if row["grade"]["raised_point"] else 0.0)
            tokens.append(row["context_tokens"])
            if states_reason[(repo, qid)]:
                reason.setdefault(repo, []).append(1.0 if row["grade"].get("reason_compatible") is True else 0.0)
        allr = [v for vs in raised.values() for v in vs]
        allz = [v for vs in reason.values() for v in vs]
        lo, hi = stratified_bootstrap_mean(raised) if allr else (float("nan"), float("nan"))
        out["arms"][arm] = {
            "n": len(allr), "raised_point_rate": _r(statistics.fmean(allr)) if allr else None, "ci95": [_r(lo), _r(hi)],
            "reason_queries": len(allz), "reason_compatible_rate": _r(statistics.fmean(allz)) if allz else None,
            "tokens_mean": _r(statistics.fmean(tokens), 1) if tokens else None,
            "tokens_median": statistics.median(tokens) if tokens else None,
            "per_repo": {repo: {"n": len(vs), "raised_point_rate": _r(statistics.fmean(vs))} for repo, vs in sorted(raised.items())},
        }
    for base in BASELINES:
        pairs = {}
        for (repo, qid), by_arm in res.items():
            if PRIMARY in by_arm and base in by_arm:
                pairs.setdefault(repo, []).append((1.0 if by_arm[PRIMARY]["grade"]["raised_point"] else 0.0,
                                                   1.0 if by_arm[base]["grade"]["raised_point"] else 0.0))
        diff, lo, hi, n = stratified_bootstrap_diff(pairs)
        per_repo = {repo: _r(statistics.fmean(a - b for a, b in p)) for repo, p in sorted(pairs.items())}
        out["comparisons"][base] = {"paired_queries": n, "difference": _r(diff), "ci95": [_r(lo), _r(hi)],
                                    "decision": decide(diff, lo, hi) if n else "not run", "per_repo_difference": per_repo}
        if base == "curated_file":
            out["power"] = power_statement(pairs)
    return out


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def render_markdown(results: dict) -> str:
    ag = results["agent_level"]
    c = ag["comparisons"]["curated_file"]
    mem, cur = ag["arms"][PRIMARY], ag["arms"]["curated_file"]
    pts = lambda x: "n/a" if x is None else f"{100 * x:+.1f}"  # noqa: E731
    lo, hi = c["ci95"]
    first = (f"memento against the short curated file: **{c['decision']}**. memento's reviews raised the reviewer's point "
             f"on {_pct(mem['raised_point_rate'])} of {mem['n']} sampled queries against {_pct(cur['raised_point_rate'])} "
             f"for the curated file, a difference of {pts(c['difference'])} points (95% interval {pts(lo)} to {pts(hi)}, "
             f"resampling queries within each repository).")
    pw = ag.get("power") or {}
    sizes = ", ".join(f"{r} {k}" for r, k in pw.get("per_repo", {}).items())
    assumed = pw.get("mdd_at_assumed_discordance", {})
    span = [v for v in assumed.values() if v is not None]
    mdd_text = (f"{100 * min(span):.0f} to {100 * max(span):.0f} points for discordance rates of "
                f"{', '.join(f'{100 * float(k):.0f}%' for k in assumed)}" if span else "not computable")
    obs = pw.get("mdd_at_observed_discordance")
    obs_text = (f"; at the observed discordance of {_pct(pw.get('observed_discordance'))} it is {100 * obs:.0f} points"
                if obs is not None else "")
    sample_line = (f"Sample: {pw.get('paired_queries', 0)} paired queries ({sizes}). At this size, the smallest difference "
                   f"between memento and the curated file that the comparison detects with 80% power (two-sided 5% level) "
                   f"is {mdd_text}{obs_text}. A smaller true difference would usually be reported as no advantage.")
    lines = [first, "", sample_line, "", "## Agent level", "",
             "| Arm | Raised the point | 95% interval | Reason compatible | Tokens (median) |", "|---|---:|---|---:|---:|"]
    for arm in AGENT_ARMS:
        a = ag["arms"][arm]
        lines.append(f"| {arm} | {_pct(a['raised_point_rate'])} | {_pct(a['ci95'][0])} to {_pct(a['ci95'][1])} | "
                     f"{_pct(a['reason_compatible_rate'])} (of {a['reason_queries']}) | {a['tokens_median']} |")
    lines += ["", "| memento minus | Difference (points) | 95% interval | Decision |", "|---|---:|---|---|"]
    for base, cmp_ in ag["comparisons"].items():
        lines.append(f"| {base} | {pts(cmp_['difference'])} | {pts(cmp_['ci95'][0])} to {pts(cmp_['ci95'][1])} | {cmp_['decision']} |")
    rl = results["retrieval_level"]
    lines += ["", "## Retrieval level (pooled)", "", "| Arm | Slice | n | recall@5 | hit@5 | MRR |", "|---|---|---:|---:|---:|---:|"]
    for arm, slices in rl["arms"].items():
        for sl in ("all", "before_2026-07-01", "after_2026-07-01"):
            if sl in slices:
                p = slices[sl]["pooled"]
                lines.append(f"| {arm} | {sl} | {p['n']} | {p['recall@5']['mean']} | {p['hit@5']['mean']} | {p['mrr']['mean']} |")
    lines += ["", "## Label checks", ""]
    for repo, rounds in results["label_checks"].items():
        desc = "; ".join(f"round {r['round']}: precision {r['precision_same']}, {'pass' if r['passes'] else 'fail'}" for r in rounds)
        lines.append(f"- {repo}: {desc}")
    if results["not_run"]:
        lines += ["", "Not run: " + "; ".join(f"{k} ({v})" for k, v in results["not_run"].items()) + "."]
    return "\n".join(lines) + "\n"


def score(cache_root: Path) -> dict:
    sample = json.loads((cache_root / "sample.json").read_text(encoding="utf-8"))
    included, excluded = sampling.included_repos(cache_root)
    results = {
        "spec": "bench/w9b/README.md (frozen 2026-09-27)",
        "scored_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample": {k: sample.get(k) for k in ("sha256", "counts", "eligible", "shortfalls", "unfilled", "excluded")},
        "repositories": sorted(included), "excluded_repositories": excluded,
        "label_checks": {repo: _label_rounds(d) for repo, d in sorted(included.items())},
        "provenance": _provenance(included),
        "retrieval_level": _retrieval_level(included),
        "agent_level": _agent_level(cache_root, sample),
        "bootstrap": {"rounds": ROUNDS, "seed": SEED, "stratified_by": "repository"},
        "not_run": NOT_RUN,
    }
    (cache_root / "results.json").write_text(json.dumps(results, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (cache_root / "results.md").write_text(render_markdown(results), encoding="utf-8")
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("retrieve")
    r.add_argument("--cache", type=Path, required=True)
    r.add_argument("--workers", type=int, default=6)
    s = sub.add_parser("score")
    s.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "retrieve":
        included, excluded = sampling.included_repos(args.cache)
        for repo, d in sorted(included.items()):
            print(json.dumps(retrieve_repo(d, args.workers)), flush=True)
        if excluded:
            print(json.dumps({"excluded": excluded}))
        return 0
    score(args.cache)
    print(f"wrote {args.cache / 'results.json'} and {args.cache / 'results.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
