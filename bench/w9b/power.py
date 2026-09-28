"""Sample size for the agent-level paired comparison.

Each sampled query yields one binary outcome per arm: did the agent's review
raise the reviewer's point? Two arms on the same queries form a paired design.
Only discordant queries (one arm succeeds, the other fails) carry information
about the difference, so the required sample depends on how often the arms
disagree, which is unknown before the run.

Analytic sample size uses Connor's (1987) formula for McNemar's test:

    n = (z_a * sqrt(pd) + z_b * sqrt(pd - d**2))**2 / d**2

where d = p10 - p01 is the difference to detect (0.10) and pd = p10 + p01 is
the discordant proportion. The decision rule actually used is a paired
bootstrap 95% interval that excludes zero, so ``--simulate`` checks the
analytic size by Monte Carlo under that rule (requires numpy).

Usage: python power.py [--simulate] [--sims 2000] [--boot 2000]
"""
from __future__ import annotations

import argparse
import math

Z_ALPHA = 1.959964  # two-sided alpha 0.05
Z_BETA = 0.841621   # power 0.80
D = 0.10
DISCORDANT = (0.20, 0.30, 0.40)


def connor_n(d: float, pd: float) -> int:
    return math.ceil((Z_ALPHA * math.sqrt(pd) + Z_BETA * math.sqrt(pd - d * d)) ** 2 / (d * d))


def simulate_power(n: int, d: float, pd: float, sims: int, boot: int, seed: int = 20260927) -> float:
    import numpy as np

    rng = np.random.default_rng(seed)
    p10, p01 = (pd + d) / 2, (pd - d) / 2
    probs = [p10, p01, 1 - pd]  # per-query difference +1, -1, 0
    hits = 0
    for _ in range(sims):
        n10, n01, n00 = rng.multinomial(n, probs)
        # Resampling n queries with replacement from the observed ones is a multinomial draw
        # over the three difference values with the observed proportions.
        draws = rng.multinomial(n, [n10 / n, n01 / n, n00 / n], size=boot)
        diffs = (draws[:, 0] - draws[:, 1]) / n
        lo = np.quantile(diffs, 0.025)
        hits += lo > 0
    return hits / sims


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--sims", type=int, default=2000)
    parser.add_argument("--boot", type=int, default=2000)
    args = parser.parse_args(argv)
    print(f"difference to detect: {D:.2f}; alpha 0.05 two-sided; power 0.80")
    for pd in DISCORDANT:
        n = connor_n(D, pd)
        line = f"discordant {pd:.2f} (p10 {(pd + D) / 2:.2f}, p01 {(pd - D) / 2:.2f}): n = {n}"
        if args.simulate:
            line += f"; simulated bootstrap power at n = {simulate_power(n, D, pd, args.sims, args.boot):.3f}"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
