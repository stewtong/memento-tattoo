"""Metrics for ranked arms and for chosen-set arms (plan section 5.1).

``relevant`` is the set of note IDs judged *would have prevented* for a query.
Queries with an empty ``relevant`` set have no correct answer in the pool;
callers leave them out of every metric here and report their count.
"""
from __future__ import annotations

import random
from statistics import mean


def recall_at(ranked: list[str], relevant: set[str], k: int) -> float:
    """Share of the query's relevant notes found in the top k."""
    return len(set(ranked[:k]) & relevant) / len(relevant)


def hit_at(ranked: list[str], relevant: set[str], k: int) -> float:
    """1.0 when at least one relevant note is in the top k."""
    return 1.0 if set(ranked[:k]) & relevant else 0.0


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for rank, nid in enumerate(ranked, 1):
        if nid in relevant:
            return 1.0 / rank
    return 0.0


def precision_at(ranked: list[str], acceptable: set[str], k: int) -> float:
    """Share of the top k judged acceptable (*would have prevented* or *related*)."""
    top = ranked[:k]
    return len(set(top) & acceptable) / len(top) if top else 0.0


def set_hit(chosen: set[str], relevant: set[str]) -> float:
    return 1.0 if chosen & relevant else 0.0


def set_recall(chosen: set[str], relevant: set[str]) -> float:
    return len(chosen & relevant) / len(relevant)


def set_precision(chosen: set[str], acceptable: set[str]) -> float | None:
    """None when nothing was chosen; callers report that count separately."""
    return len(chosen & acceptable) / len(chosen) if chosen else None


def bootstrap_ci(values: list[float], *, seed: int = 20260927, rounds: int = 2000,
                 alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap interval of the mean."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(mean(rng.choices(values, k=n)) for _ in range(rounds))
    lo = means[int(rounds * alpha / 2)]
    hi = means[min(rounds - 1, int(rounds * (1 - alpha / 2)))]
    return (lo, hi)


def paired_bootstrap_diff(a: list[float], b: list[float], *, seed: int = 20260927,
                          rounds: int = 2000, alpha: float = 0.05) -> tuple[float, float, float]:
    """Mean of a - b over paired queries, with a percentile bootstrap interval."""
    if len(a) != len(b):
        raise ValueError("paired samples must have equal length")
    diffs = [x - y for x, y in zip(a, b)]
    lo, hi = bootstrap_ci(diffs, seed=seed, rounds=rounds, alpha=alpha)
    return (mean(diffs) if diffs else float("nan"), lo, hi)
