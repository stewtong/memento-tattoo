"""End-to-end `load` latency on synthetic stores.

Measures, at each store size, the wall time of a fresh process including
interpreter start:

- ``cli``: the shipped CLI, ``python -m memento_tattoo --root R load --query Q``.
- ``bm25f``: a fresh process that parses the same store with the package's
  parser and ranks it with the A1 prototype, to size Phase 3's cost.

Usage: python bench/latency.py [--sizes 1000 5000 20000] [--runs 5] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "src"

QUERIES = (
    "changing a shared package interface before release",
    "deploy fails after a config migration on the staging cluster",
    "reviewing a pull request that touches generated files",
)


def _vocabulary(rng: random.Random, size: int = 3000) -> list[str]:
    syllables = ["ka", "lo", "mi", "ter", "ban", "dex", "ro", "sil", "ven", "tor", "pla", "qui", "nor", "zen", "fa"]
    words = set()
    while len(words) < size:
        words.add("".join(rng.choice(syllables) for _ in range(rng.randint(2, 4))))
    common = ["agent", "file", "run", "test", "deploy", "config", "package", "review", "build", "cluster",
              "migration", "interface", "release", "generated", "staging", "shared", "change", "before", "after"]
    return common + sorted(words)


def _sentence(rng: random.Random, vocab: list[str], n: int) -> str:
    # Zipf-like draw so a few words dominate, as in real notes.
    weights = [1 / (i + 1) for i in range(len(vocab))]
    return " ".join(rng.choices(vocab, weights=weights, k=n))


def build_store(root: Path, count: int, seed: int = 7) -> None:
    rng = random.Random(seed)
    vocab = _vocabulary(rng)
    hot, archive = [], []
    for i in range(count):
        block = "\n".join([
            f"<!-- delta:synth.note.{i:08x} -->",
            f"Situation: {_sentence(rng, vocab, rng.randint(10, 25))}",
            f"Note: {_sentence(rng, vocab, rng.randint(20, 60))}",
            f"aliases: {', '.join(rng.sample(vocab[:400], 4))}",
            "",
        ])
        (hot if i < 20 else archive).append(block)
    root.mkdir(parents=True, exist_ok=True)
    (root / "notes.md").write_text("\n".join(hot), encoding="utf-8")
    (root / "notes_archive.md").write_text("\n".join(archive), encoding="utf-8")
    (root / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")


BM25_SNIPPET = """
import sys
sys.path[:0] = [{src!r}, {bench!r}]
from pathlib import Path
from memento_tattoo.recall import load_memento_notes
from memento_bench.rankers import BM25FIndex, BM25FConfig
notes = load_memento_notes(Path({root!r}))
corpus = [dict(note_id=n.note_id, situation=n.situation, note=n.note, why=getattr(n, "why", ""),
               aliases=list(n.aliases), tags=list(n.tags or []), superseded_by=n.superseded_by) for n in notes]
index = BM25FIndex(corpus)
for q in {queries!r}:
    index.rank(q, BM25FConfig())
"""


def _time(cmd: list[str]) -> float:
    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.perf_counter() - start
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[:4]} failed: {proc.stderr[-300:]}")
    return elapsed


def measure(sizes: list[int], runs: int) -> dict:
    results = {"python": sys.version.split()[0], "machine": platform.machine(), "platform": platform.platform(),
               "processor": platform.processor(), "runs_per_cell": runs, "cells": []}
    with tempfile.TemporaryDirectory(prefix="memento-latency-") as tmp:
        for size in sizes:
            root = Path(tmp) / f"store-{size}"
            build_store(root, size)
            cli = [sys.executable, "-m", "memento_tattoo", "--root", str(root), "load", "--query", QUERIES[0]]
            bm = [sys.executable, "-c", BM25_SNIPPET.format(src=str(SRC), bench=str(HERE), root=str(root),
                                                              queries=QUERIES)]
            for name, cmd in (("cli", cli), ("bm25f_three_queries", bm)):
                _time(cmd)  # warm the file cache and bytecode once, unmeasured
                times = [_time(cmd) for _ in range(runs)]
                results["cells"].append({"notes": size, "arm": name, "median_s": round(statistics.median(times), 4),
                                         "min_s": round(min(times), 4), "max_s": round(max(times), 4)})
    startup = [_time([sys.executable, "-c", "pass"]) for _ in range(runs)]
    results["interpreter_start_median_s"] = round(statistics.median(startup), 4)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 5000, 20000])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    report = measure(args.sizes, args.runs)
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
