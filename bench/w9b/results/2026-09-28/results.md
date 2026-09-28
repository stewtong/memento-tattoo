memento against the short curated file: **no advantage**. memento's reviews raised the reviewer's point on 54.0% of 50 sampled queries against 52.0% for the curated file, a difference of +2.0 points (95% interval -12.0 to +14.0, resampling queries within each repository).

Sample: 50 paired queries (prometheus/prometheus 50). At this size, the smallest difference between memento and the curated file that the comparison detects with 80% power (two-sided 5% level) is 17 to 24 points for discordance rates of 20%, 30%, 40%; at the observed discordance of 22.0% it is 18 points. A smaller true difference would usually be reported as no advantage.

## Agent level

| Arm | Raised the point | 95% interval | Reason compatible | Tokens (median) |
|---|---:|---|---:|---:|
| memento_lexical | 54.0% | 40.0% to 68.0% | 52.5% (of 40) | 767.5 |
| bm25 | 52.0% | 38.0% to 66.0% | 47.5% (of 40) | 773.0 |
| embeddings | 54.0% | 40.0% to 68.0% | 55.0% (of 40) | 518.0 |
| curated_file | 52.0% | 38.0% to 66.0% | 55.0% (of 40) | 1967.0 |
| long_file | 54.0% | 40.0% to 68.0% | 52.5% (of 40) | 8143.5 |
| no_memory | 50.0% | 36.0% to 64.0% | 47.5% (of 40) | 0.0 |

| memento minus | Difference (points) | 95% interval | Decision |
|---|---:|---|---|
| curated_file | +2.0 | -12.0 to +14.0 | no advantage |
| long_file | +0.0 | -12.0 to +10.0 | no advantage |
| no_memory | +4.0 | +0.0 to +10.0 | no advantage |
| bm25 | +2.0 | -4.0 to +8.0 | no advantage |
| embeddings | +0.0 | -6.0 to +6.0 | no advantage |

## Retrieval level (pooled)

| Arm | Slice | n | recall@5 | hit@5 | MRR |
|---|---|---:|---:|---:|---:|
| memento_lexical | all | 279 | 0.1548 | 0.1685 | 0.1103 |
| memento_lexical | before_2026-07-01 | 227 | 0.1612 | 0.1762 | 0.1184 |
| memento_lexical | after_2026-07-01 | 52 | 0.1269 | 0.1346 | 0.0747 |
| bm25 | all | 279 | 0.1507 | 0.1649 | 0.1155 |
| bm25 | before_2026-07-01 | 227 | 0.1649 | 0.1806 | 0.1209 |
| bm25 | after_2026-07-01 | 52 | 0.0885 | 0.0962 | 0.092 |
| embeddings | all | 279 | 0.0514 | 0.0573 | 0.0474 |
| embeddings | before_2026-07-01 | 227 | 0.0499 | 0.0573 | 0.0465 |
| embeddings | after_2026-07-01 | 52 | 0.0577 | 0.0577 | 0.0517 |

## Label checks

- prometheus/prometheus: round 1: precision 0.52, fail; round 2: precision 0.69, fail; round 3: precision 0.91, pass

Not run: memento_paths (paths scoping not built yet; runs when it ships (spec changelog)).
