"""Draw the agent-level sample once, before any arm runs (spec: README.md, "Two levels").

Eligible queries come from pull requests opened on or after July 1, 2026 and
have at least one relevant earlier lesson. Each included repository gives
--per-repo queries (default 50), drawn with a fixed seed. A repository with fewer gives all of them, and the
shortfall is redrawn evenly from the other repositories' remaining eligible
queries (round-robin for any remainder). Shortfalls are recorded.

A repository is included only when it has yield output (queries.jsonl) and its
latest label check round passed. Excluded repositories are listed.

Usage: python sample.py --cache CACHE_ROOT [--per-repo 50] [--force]
Writes CACHE_ROOT/sample.json and refuses to overwrite it without --force.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SEED = 20260927
PER_REPO = 50


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_label_check(repo_dir: Path) -> dict | None:
    rounds = []
    for f in repo_dir.glob("label_check_round*.json"):
        m = re.fullmatch(r"label_check_round(\d+)\.json", f.name)
        if m:
            rounds.append((int(m.group(1)), f))
    if not rounds:
        return None
    return json.loads(max(rounds)[1].read_text(encoding="utf-8"))


def repo_dirs(cache_root: Path) -> list[Path]:
    return sorted(p for p in cache_root.iterdir() if p.is_dir() and "__" in p.name)


def repo_name(repo_dir: Path) -> str:
    return repo_dir.name.replace("__", "/", 1)


def included_repos(cache_root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    included, excluded = {}, {}
    for d in repo_dirs(cache_root):
        name = repo_name(d)
        if not (d / "queries.jsonl").exists():
            excluded[name] = "no yield output (queries.jsonl)"
            continue
        check = latest_label_check(d)
        if check is None:
            excluded[name] = "no label check round"
        elif not check.get("passes"):
            excluded[name] = f"latest label check round {check.get('round')} failed"
        else:
            included[name] = d
    return included, excluded


def eligible(queries: list[dict]) -> list[dict]:
    return sorted((q for q in queries if q.get("post_cutoff") and q.get("relevant")), key=lambda q: q["id"])


def draw(pools: dict[str, list[str]], per_repo: int = PER_REPO, seed: int = SEED) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Per-repository draw with shortfall redistribution. ``pools`` maps repo to eligible query ids."""
    chosen, remaining, shortfall = {}, {}, {}
    for repo in sorted(pools):
        rng = random.Random(f"{seed}:{repo}")
        ids = sorted(pools[repo])
        take = min(per_repo, len(ids))
        picked = rng.sample(ids, take)
        rest = [i for i in ids if i not in set(picked)]
        rng.shuffle(rest)
        chosen[repo], remaining[repo] = picked, rest
        if take < per_repo:
            shortfall[repo] = per_repo - take
    missing = sum(shortfall.values())
    while missing > 0:
        donors = [r for r in sorted(remaining) if remaining[r]]
        if not donors:
            break
        share = missing // len(donors)
        if share:
            for r in donors:
                extra = remaining[r][:share]
                remaining[r] = remaining[r][share:]
                chosen[r].extend(extra)
                missing -= len(extra)
        else:
            for r in donors:
                if missing == 0:
                    break
                chosen[r].append(remaining[r].pop(0))
                missing -= 1
    return chosen, shortfall


def build_sample(cache_root: Path, per_repo: int = PER_REPO, seed: int = SEED) -> dict:
    included, excluded = included_repos(cache_root)
    pools = {name: [q["id"] for q in eligible(_jsonl(d / "queries.jsonl"))] for name, d in included.items()}
    chosen, shortfall = draw(pools, per_repo, seed)
    sample = sorted(({"repo": r, "query_id": q} for r, ids in chosen.items() for q in ids),
                    key=lambda e: (e["repo"], e["query_id"]))
    digest = hashlib.sha256(json.dumps(sample, sort_keys=True).encode("utf-8")).hexdigest()
    return {"seed": seed, "per_repo_target": per_repo, "target_total": per_repo * len(included),
            "sample": sample, "sha256": digest,
            "counts": {r: len(ids) for r, ids in sorted(chosen.items())},
            "eligible": {r: len(p) for r, p in sorted(pools.items())},
            "shortfalls": shortfall, "unfilled": per_repo * len(included) - len(sample),
            "excluded": excluded, "drawn_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, required=True, help="cache root with one subdirectory per repository")
    parser.add_argument("--per-repo", type=int, default=PER_REPO, help="queries per repository (default %(default)s)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing sample.json")
    args = parser.parse_args(argv)
    out = args.cache / "sample.json"
    if out.exists() and not args.force:
        print(f"refusing to overwrite {out}; the sample is drawn once (use --force to redraw)", file=sys.stderr)
        return 2
    if args.per_repo < 1:
        parser.error("--per-repo must be at least 1")
    result = build_sample(args.cache, per_repo=args.per_repo)
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("per_repo_target", "counts", "eligible", "shortfalls", "unfilled", "excluded", "sha256")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
