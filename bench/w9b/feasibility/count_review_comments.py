"""Count pull request review comments per repository for the benchmark feasibility check.

Reads the GitHub REST endpoint ``GET /repos/{owner}/{repo}/pulls/comments`` with
full pagination (no sampling) and keeps only aggregate counts. Comment text is
never stored or printed; nothing identifying an individual reviewer is written.

A comment is counted when its ``created_at`` falls inside the window. The API's
``since`` parameter filters on ``updated_at``, so every comment created inside
the window is returned; comments created earlier but edited later are dropped.

A comment is a bot comment when ``user.type`` is ``Bot`` or the login ends in
``[bot]``. A comment with no user (deleted account) counts as human with an
unknown author and is reported separately.

Usage: python count_review_comments.py [--out counts.json] [--workers 8]
Each repository's result is saved under counts.partial/ as it finishes, so a
rerun after a failure skips repositories already counted.
Requires the GitHub CLI to be logged in; its token is read through
``gh auth token`` and is never printed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPOS = [
    "django/django",
    "scikit-learn/scikit-learn",
    "microsoft/vscode",
    "kubernetes/kubernetes",
    "prometheus/prometheus",
    "rust-lang/rust",
    "astral-sh/ruff",
    "apache/kafka",
]
WINDOW_START = "2025-09-27T00:00:00Z"
WINDOW_END = "2026-09-27T00:00:00Z"
SPLIT = "2026-07-01T00:00:00Z"  # comments on or after this date are reported as "after June 2026"
API = "https://api.github.com"


def _token() -> str:
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def _get(url: str, token: str) -> tuple[list, str | None]:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                link = resp.headers.get("Link") or ""
                m = re.search(r'<([^>]+)>;\s*rel="next"', link)
                return json.loads(resp.read()), (m.group(1) if m else None)
        except urllib.error.HTTPError as err:
            if err.code in (403, 429, 500, 502, 503, 504):
                wait = int(err.headers.get("Retry-After") or 0) or 2 ** attempt * 5
                time.sleep(min(wait, 120))
                continue
            raise
        except urllib.error.URLError:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"giving up after retries: {url.split('?')[0]}")


def _is_bot(user: dict | None) -> bool:
    if not user:
        return False
    return user.get("type") == "Bot" or str(user.get("login", "")).endswith("[bot]")


def count_repo(repo: str, token: str) -> dict:
    url = f"{API}/repos/{repo}/pulls/comments?since={WINDOW_START}&sort=created&direction=asc&per_page=100"
    total = bot = human = unknown_author = human_top_level = after_split_human = 0
    prs_all: set[str] = set()
    prs_human: set[str] = set()
    reviewers: set[str] = set()
    per_pr_human: dict[str, int] = {}
    pages = 0
    while url:
        items, url = _get(url, token)
        pages += 1
        if pages % 50 == 0:
            print(f"{repo}: {pages} pages", flush=True)
        for c in items:
            created = c.get("created_at", "")
            if not (WINDOW_START <= created < WINDOW_END):
                continue
            total += 1
            pr = c.get("pull_request_url", "").rsplit("/", 1)[-1]
            prs_all.add(pr)
            user = c.get("user")
            if _is_bot(user):
                bot += 1
                continue
            human += 1
            prs_human.add(pr)
            per_pr_human[pr] = per_pr_human.get(pr, 0) + 1
            if user:
                reviewers.add(user.get("login", ""))
            else:
                unknown_author += 1
            if not c.get("in_reply_to_id"):
                human_top_level += 1
            if created >= SPLIT:
                after_split_human += 1
    print(f"{repo}: done, {pages} pages", flush=True)
    counts = sorted(per_pr_human.values())
    median = counts[len(counts) // 2] if counts else 0
    return {
        "repo": repo,
        "pages_read": pages,
        "review_comments": total,
        "bot_comments": bot,
        "human_comments": human,
        "human_comments_unknown_author": unknown_author,
        "human_top_level_comments": human_top_level,
        "prs_with_review_comments": len(prs_all),
        "prs_with_human_review_comments": len(prs_human),
        "median_human_comments_per_pr": median,
        "distinct_human_commenters": len(reviewers),
        "human_comments_after_june_2026": after_split_human,
        "share_human_after_june_2026": round(after_split_human / human, 4) if human else 0.0,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("counts.json"))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)
    token = _token()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    partial = args.out.with_suffix(".partial")
    partial.mkdir(exist_ok=True)

    def run(repo: str) -> dict:
        cached = partial / (repo.replace("/", "__") + ".json")
        if cached.exists():
            return json.loads(cached.read_text(encoding="utf-8"))
        result = count_repo(repo, token)
        cached.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return result

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run, REPOS))
    payload = {
        "collected_at": started,
        "window": {"start": WINDOW_START, "end": WINDOW_END, "field": "created_at"},
        "split_for_training_exposure": SPLIT,
        "endpoint": "GET /repos/{owner}/{repo}/pulls/comments (full pagination, since=window start)",
        "bot_rule": "user.type == 'Bot' or login ends with '[bot]'",
        "repos": results,
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    for r in results:
        print(f"{r['repo']:28} comments={r['review_comments']:6} human={r['human_comments']:6} "
              f"prs={r['prs_with_human_review_comments']:5} commenters={r['distinct_human_commenters']:5} "
              f"after_june={r['share_human_after_june_2026']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
