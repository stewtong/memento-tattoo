<!-- register: public benchmark report | reader: agent-tooling developers and skeptical reviewers checking the method | consumed: GitHub read, linked from the README -->

# Repeated-correction benchmark: first results

**September 28, 2026. One repository (prometheus/prometheus), 50 agent-level queries from 32 pull requests.**

memento-tattoo showed **no advantage** over the short curated file. An agent given memento's lessons raised the human reviewer's point on 27 of 50 queries (54%), against 26 of 50 (52%) with the curated file. The difference is +2 percentage points, with a 95% interval of -12 to +14. At this size, the comparison detects a difference of about 18 points or more with 80% power; a smaller real difference would usually read as no advantage, so this result does not show that the arms are equivalent.

memento also showed no advantage over any of the other four baselines, including no memory. All six arms raised the point on 25 to 27 of the 50 queries. The query was the raw diff hunk, which is not how an agent searches when it uses the package; that query form was not tested. The method is in the [frozen specification](README.md), and the changes made to it before scoring are listed under "Changes from the specification" below.

## Terms

- **Query:** a later review comment's situation, given as the commented file's path and the diff hunk the reviewer commented on. The comment itself is the reference answer and is never shown to the agent.
- **Lesson:** an earlier top-level review comment from the same repository.
- **Relevant lesson:** an earlier comment labeled as making the same correction as the query's comment.
- **Arm:** one way of choosing which lessons the agent sees.
- **Points:** percentage points.

## Agent level

For each sampled query, an agent reviewed the diff hunk with the lessons one arm supplied. A grader, blind to the arm, judged whether the review raised the human reviewer's point. Both were Claude Opus 5.5 (see "How this run was made").

| Arm | Raised the reviewer's point | 95% interval | Relevant lesson in context | Context tokens (median) |
|---|---:|---|---:|---:|
| memento-tattoo (`load` ranking) | 27 of 50 (54%) | 40% to 68% | 7 of 50 | 768 |
| Plain BM25 | 26 of 50 (52%) | 38% to 66% | 5 of 50 | 773 |
| Local embeddings | 27 of 50 (54%) | 40% to 68% | 3 of 50 | 518 |
| Curated file (2,000 tokens) | 26 of 50 (52%) | 38% to 66% | 7 of 50 | 1,967 |
| Long file (32 KiB, newest first) | 27 of 50 (54%) | 40% to 68% | 12 of 50 | 8,144 |
| No memory | 25 of 50 (50%) | 36% to 64% | 0 of 50 | 0 |

- **memento-tattoo** ranks the lessons with the package's `load` ranking function (field-weighted BM25 over whole words) and supplies the top 5.
- **Plain BM25** is the same ranking with every field weighted equally and no penalty for superseded notes.
- **Curated file** stands in for a maintainer's short rules file, with no person choosing: lessons are ordered by how many earlier pull requests their correction had already recurred on, and kept while they fit in 2,000 tokens ([specification](README.md#the-curated-file-arm)). The recurrence counts come from the benchmark's own labels, so this baseline knows which corrections recur, which makes it an optimistic stand-in for a real file. Clusters are joined through all labeled pairs, so a link between two earlier lessons can pass through a comment made after the query; only lessons created before the query are counted.
- **Long file** holds the newest lessons created before the query, uncurated, up to 32 KiB, the default size cap on `AGENTS.md` content in Codex.
- **Relevant lesson in context** counts the queries where at least one relevant lesson was among the lessons the agent saw.
- **Context tokens** are estimated as one token per four characters of the lessons the agent saw. The reviews themselves had similar lengths across arms (median 232 to 271 words).

| memento-tattoo minus | Difference | 95% interval | Queries only memento got | Queries only the other arm got |
|---|---:|---|---:|---:|
| Curated file | +2 points | -12 to +14 | 6 | 5 |
| Long file | 0 | -12 to +10 | 4 | 4 |
| No memory | +4 points | 0 to +10 | 2 | 0 |
| Plain BM25 | +2 points | -4 to +8 | 2 | 1 |
| Local embeddings | 0 | -6 to +6 | 1 | 1 |

The difference intervals come from a paired bootstrap over queries (10,000 resamples, seed 20260927); the per-arm intervals in the first table use 2,000 resamples. Queries are resampled as independent, although several come from the same pull request, which can make the intervals too narrow. The specification counts an advantage only when the interval excludes zero. Against no memory, the lower bound is exactly zero: memento raised the point on 2 queries that no memory missed, and missed none that no memory raised. By the rule, that is no advantage. The 18-point detectable difference comes from Connor's formula for McNemar's test at the observed rate of disagreeing pairs (22%); at assumed rates of 20% to 40% it is 17 to 24 points.

**Exposure did not explain the gains either.** When the relevant lesson was in memento's context (7 queries), the review raised the point on 4, and so did the no-memory review on those same 4. memento's 2 wins over no memory both came on queries where its context held no relevant lesson. The curated file raised the point on 4 of its 7 exposed queries, where no memory raised 1; the long file raised it on 7 of its 12, where no memory raised 5. These counts are too small to compare arms. The diff alone carried most of the signal: all six arms raised the point on 17 queries, and at least one arm raised it on 35.

A review scores on reason only when it raised the point and the grader judged its reason compatible with the reviewer's. This applies to the 40 queries where most of the six grades said the reviewer's comment stated a reason. On those 40, the review gave a compatible reason on 21 (memento), 19 (BM25), 22 (embeddings), 22 (curated file), 21 (long file) and 19 (no memory).

## Retrieval level

Every query with at least one relevant earlier lesson (279), ranking only the lessons created before its pull request opened.

| Arm | recall@5 | hit@5 | MRR |
|---|---:|---:|---:|
| memento-tattoo (`load` ranking) | 0.155 | 0.168 | 0.110 |
| Plain BM25 | 0.151 | 0.165 | 0.116 |
| Local embeddings | 0.051 | 0.057 | 0.047 |

recall@5 is the share of a query's relevant lessons ranked in the top 5, averaged over queries. hit@5 is the share of queries with at least one relevant lesson in the top 5. MRR is the mean of 1 divided by the rank of the first relevant lesson. On the 52 queries from pull requests opened on or after July 1, 2026, recall@5 was 0.127 (memento), 0.089 (BM25) and 0.058 (embeddings). Intervals per slice are in `results.json`; no paired interval was computed for memento against BM25 at this level.

The candidate pairs that define relevance were proposed by BM25 over the comment text (see "Labels"), so a relevant lesson is always a lexical neighbor of the query's comment. That favors the lexical arms over embeddings here.

## Dataset

| | prometheus/prometheus |
|---|---:|
| Review comments collected (September 27, 2025 to September 27, 2026) | 4,993 |
| Top-level human comments (the lessons and queries) | 2,932 |
| Candidate pairs (up to 5 earlier BM25 neighbors per comment) | 14,558 |
| Pairs labeled the same correction | 599 |
| Queries with a relevant earlier lesson | 279 |
| Of those, from pull requests opened on or after July 1, 2026 | 52 |
| Agent-level sample (the per-repository target, drawn at random from the 52) | 50 |

Only pull requests opened on or after July 1, 2026, after the agent model's documented training cutoff, are sampled at the agent level. No lesson was excluded for an unavailable edit history.

## Labels

GLM-5.3-Flash (low reasoning effort) decided every candidate pair, and GPT-6 Astra re-decided the pairs GLM called the same. A pair is labeled the same correction only when both agree. Before each check, Claude Opus 5.5 judged 100 "same" and 100 "different" pairs it had not judged before, without seeing the labels. Weighted accuracy combines the accuracy on both groups, weighted by each group's share of the pairs eligible for that round.

| Round | Labeling | Precision on "same" | Weighted accuracy | Result |
|---|---|---:|---:|---|
| 1 | GLM-5.3-Flash alone, first prompt | 0.52 | 0.971 | Failed |
| 2 | GLM-5.3-Flash, confirmed by DeepSeek-V4.1-Flash | 0.69 | 0.975 | Failed |
| 3 | GLM-5.3-Flash, confirmed by GPT-6 Astra | 0.91 | 0.997 | Passed; these labels are used |
| 4 | GLM-5.3-Flash, confirmed by GLM-5.3 | 0.77 | 0.972 | Failed; not used |

- **The pass mark is 0.85 on both measures.** Round 3's 91 of 100 has a 95% interval of about 0.84 to 0.95, which reaches below the mark, and it passed on the third labeling design tried. About 1 in 11 "same" labels is wrong in the grader's judgment, which adds noise to relevance at both levels.
- **Round 1 was a tuning set.** Its 200 pairs were used to revise the labeling prompt, and rounds 2 to 4 each drew pairs not used before. Because the revisions were judged against Claude Opus 5.5 on those pairs, the later checks measure agreement with the same grader the prompt was tuned toward.
- **No person checked any label or grade.** The labels are checked only by Claude Opus 5.5, which is also the agent and the grader.
- **Round 4** tested a replacement confirming model, for a second repository, after GPT-6 Astra stopped being available to us. It failed, so no label from it is used.

## Changes from the specification

The specification was frozen on September 27, 2026 for eight repositories and 336 agent-level queries; that text is published as [specification-as-frozen.md](results/2026-09-28/specification-as-frozen.md), unchanged except for two relative link paths corrected in 0.5.1. The specification and its changelog were kept in a private working copy until this release, so the freeze and change dates are the author's record, not public commits. prometheus/prometheus, the scored repository, is also the pilot repository whose pairs were used to tune the labeling. Each reduction below made a no-advantage result more likely.

Made before any arm was scored, and dated in the specification's changelog:

- **One repository instead of eight.** The first cut went to two repositories, prometheus/prometheus and django/django. django was collected and passed the first labeling stage, but its confirming stage could not run: GPT-6 Astra became unavailable to us, and the replacement failed round 4 above. Confirming django with a different model than prometheus would make the two repositories' labels incomparable, so django is left out.
- **50 agent-level queries** instead of 42 per repository across eight.

Found or decided after scoring:

- **The query uses the commented file's path**, not every path the pull request changed, as the specification says. The code has done this since the pilot; the difference was found when checking these results.
- **The paths-scoped memento arm did not run**, because path scoping is not built.
- **The second-family regrade**, grading about 100 queries again with a model from another family, was not run; the specification reports it only when available.

## How this run was made

- **memento-tattoo:** the 0.5.0 source, before the version number was raised from 0.4.0, so `results.json` records 0.4.0. The ranking code is unchanged between the run and the 0.5.0 release; later changes to the package before release affect only error handling and which current-state section `load` prints.
- **Agent and grader:** `claude -p --model opus` with tools disabled and a fixed system prompt, prompt versions r1 (review) and gr1 (grade). The model was recorded as the alias `opus`, and outputs were cached under the alias. It resolved to `claude-opus-5-5` when checked on the same machine on September 28. Claude Code also added its user-level instruction file to every call: a short note about a web-search tool, unrelated to code review, identical for every arm and for the grader.
- **Labelers:** GLM-5.3-Flash through Nebius Token Factory (us-north1) and GPT-6 Astra through the Codex CLI, both with prompt version pair-v3. GLM-5.3-Flash also wrote each lesson's one-line situation (prompt version situation-v1), which the lexical arms index with the comment.
- **Caching:** every model output is cached by a hash of its prompt version, model and prompt. The reviews and grades for 4 of the 300 query-arm pairs (query 3909406466 under memento, embeddings, the curated file and no memory) were first produced with identical inputs by a pre-freeze check that only confirmed outputs parsed. All six arms raised the point on that query, so reusing them cannot move any paired difference. Two sampled queries are separate reviewer comments on the same diff hunk, so each arm gave both one review, graded against each comment. One review is shared by memento and plain BM25, which supplied the same lessons in the same order for that query.
- **Embeddings:** `BAAI/bge-base-en-v1.5` through fastembed, run locally.

## Limits

- **Small sample.** 50 queries detect only differences of about 18 points or more at 80% power.
- **One repository, one language.** prometheus is a large Go project with an active review culture. Results may not hold for other projects or smaller teams.
- **The query is a raw diff.** The retrieval level mostly measures how well each arm matches a diff hunk to an earlier comment. The query an agent writes in normal use was not tested.
- **Review comments stand in for corrections.** A reviewer's repeated comment is a proxy for a correction given to an agent.
- **One model family judges everything.** The agent, the grader and the label check are all Claude Opus 5.5. Grading is blind to the arm, but no second-family regrade or human audit was run.
- **Label noise.** Precision on "same" is 0.91. Candidate pairs come from lexical search, so the same correction written in different words is missing from the labels.
- **Scoring rule.** "Raised the point" does not penalize a review for raising many other points.

## Files

[results/2026-09-28/](results/2026-09-28/) holds everything published from this run. Comment text, diff hunks and model outputs are not published.

- `results.md` and `results.json`: the scorer's output, with every interval and the power calculation.
- `sample.json`: the 50 sampled query ids and the draw time.
- `agent_results.jsonl`: one row per query and arm, with the lesson ids the agent saw, context tokens and the grade.
- `specification-as-frozen.md`: the specification as frozen, before its changelog entries.
- `prometheus__prometheus/comments.csv`: every collected comment's id, pull request, creation time, and the SHA-256 of its body at collection. A rebuild can compare hashes to find edited or deleted comments.
- `prometheus__prometheus/pairs.csv`: every candidate pair, with the first-stage decision and the final label.
- `prometheus__prometheus/queries.csv`: every query and its relevant lesson ids.
- `prometheus__prometheus/retrieval_runs.json`: each retrieval arm's ranked lesson ids per query.
- `prometheus__prometheus/label_checks/`: all four label check rounds.

**Rebuilding.** The scripts are `build.py` (collect, candidates, label, situations, check, yield), `sample.py`, `agent.py run`, `score.py retrieve` and `score.py score`; `publish.py` writes this directory from the private cache. Collection needs a GitHub token and reads the live API, so a rebuild sees comments as they are on that day. The labeling cannot be rerun as published while GPT-6 Astra is unavailable. `pairs.csv` holds the final labels, and the retrieval level can be recounted from `queries.csv` and `retrieval_runs.json` without any model. The agent level calls a sampled model, so a rerun will differ by more than rounding; the specification's expectation of results within 3 points was not tested.
