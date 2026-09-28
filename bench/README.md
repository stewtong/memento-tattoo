<!-- register: public directory readme | reader: contributors and reviewers checking the evaluation code | consumed: GitHub read -->

# Evaluation code

Code used to evaluate `memento-tattoo` retrieval. It lives outside the package, so the CLI stays dependency-free and never calls a model.

- [w9b/](w9b/): the repeated-correction benchmark built from public code review. [Specification](w9b/README.md) and [first results](w9b/RESULTS.md).
- [memento_bench/](memento_bench/): shared rankers (including a frozen copy of the 0.4.0 ranker), metrics and an optional local embedding baseline.
- [fixtures/](fixtures/): a synthetic 200-note ranking fixture and the script that generates it.
- [latency.py](latency.py): end-to-end `load` time on synthetic stores.
- [compat/](compat/): a round-trip check between CLI versions.

Tests: `python -m pytest bench/tests bench/w9b/tests` from the repository root, with the package installed. The embedding tests need `fastembed` and are skipped without it.
