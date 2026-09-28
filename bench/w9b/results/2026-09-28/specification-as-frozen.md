<!-- register: public benchmark specification | reader: agent-tooling developers and reviewers checking the method | consumed: read in full before trusting a result -->

# Repeated-correction benchmark

**Status: frozen on September 27, 2026, before any arm was scored.** Any later change is listed in the changelog at the end, with its date and reason.

## What it measures

When a reviewer makes the same correction on several pull requests in one repository, the earlier comment is a lesson that should have been available the second time. This benchmark asks whether a memory system puts that earlier lesson in front of an agent before the same mistake recurs, and whether the agent then acts on it.

Existing memory benchmarks (LongMemEval, LoCoMo, MemoryAgentBench, ContextBench) test recall of past conversation events, and code-review benchmarks (CR-Bench, SeRe) test review quality without a memory of earlier corrections. A search on September 26, 2026 of those benchmarks found no public benchmark for this question.

## Corpus

| Language | Repository | License |
|---|---|---|
| Python | django/django | BSD-3-Clause |
| Python | scikit-learn/scikit-learn | BSD-3-Clause |
| TypeScript | microsoft/vscode | MIT |
| Go | kubernetes/kubernetes | Apache-2.0 |
| Go | prometheus/prometheus | Apache-2.0 |
| Rust | rust-lang/rust | MIT or Apache-2.0 |
| Rust | astral-sh/ruff | MIT |
| Java | apache/kafka | Apache-2.0 |

- **Selection rules.** An MIT, Apache or BSD license; code review on GitHub pull requests; review mostly by people. The list was chosen from these rules before any result was seen. The only check made before freezing it is a count of review comments per repository, to confirm each has enough material ([feasibility counts](feasibility/)). A repository may be replaced under the same rules until the first arm runs, and the replacement is recorded.
- **Window.** Pull request review comments created from September 27, 2025 to September 27, 2026. Collected on September 27 and 28, 2026; each repository's collection time is recorded with the dataset.
- **Bot filter.** A comment is excluded when its author's account type is `Bot` or the login ends in `[bot]`.
- **Unit.** Top-level human review comments (not replies within a thread) are the candidate lessons and queries. Replies are kept only as context for deciding whether a comment was a correction.
- **Collection.** Through the GitHub REST and GraphQL APIs, within their rate limits.

## Labels

A model clusters comments within one repository that make the same correction. Within a cluster, each later comment is a query, and every earlier comment in the cluster is a relevant lesson for it. Clustering runs once, when the dataset is built, with a versioned prompt and cached outputs. The package under test makes no model call.

1. **Candidate pairs.** For each top-level comment, a BM25 search over the repository's earlier top-level comments from other pull requests proposes the 5 most similar. No model is involved in this step.
2. **Pair decisions, in two stages.** A fast first-pass labeler reads each candidate pair, with each comment's file path and diff hunk, and decides whether both comments make the same correction. A second labeler from another model family re-decides only the pairs the first called the same. A pair is the same correction only when both agree. Pairs are sent in batches of 20.
3. **One definition.** Both labelers and the grader answer the identical question: two comments make the same correction when one reusable instruction covers both, at the level of a single line in the project's contributing guide (for example "make repeated test cases table-driven"). The prompt text is published with the scripts.
4. **Relevant lessons and clusters.** A query's relevant lessons are the earlier comments directly confirmed as the same correction. Confirmed pairs are also joined into clusters, used only to count how often a correction recurred; a cluster counts only when its comments span at least two pull requests.
5. **Label check.** Before the run, the grader judges a fresh sample of 100 pairs the labelers called the same and 100 they called different, blind to the label. The labels are used only if at least 85% of the "same" decisions are correct and the accuracy weighted by each group's share of all pairs is at least 85%. A sample drawn uniformly would be dominated by easy "different" pairs and hide a weak "same" decision. When a check fails and the labeling is changed, the next check draws new pairs. The checking model only measures accuracy and never changes a label. Every check round, including failed ones, is reported with the results.

## Model roles

| Role | Model | Rule |
|---|---|---|
| First-pass labeler: decides every candidate pair and writes each lesson's situation line | GLM-5.3-Flash, at low reasoning effort | A different model family from the agent and the grader. |
| Confirming labeler: re-decides the first pass's "same" pairs | GPT-6 Astra | A different model family from the first pass, the agent and the grader. |
| Agent: writes the review at the agent level | Claude Opus 5.5 | Documented training cutoff of June 2026. |
| Grader: judges whether the review raised the reviewer's point | Claude Opus 5.5 | Sees the reference comment and the review, never the arm that produced it. |

Keeping the labelers' families apart from the agent and grader keeps the benchmark from rewarding agreement with its own labels. The agent and the grader share a model family; grading is blind to the arm, and a regrade of about 100 queries by a second family is reported when available. The exact model identifiers and inference provider are recorded with the results. Every prompt is versioned and every model output is cached, so a rerun with unchanged inputs makes no new model call.

## Queries

The query is the later pull request's situation: its changed paths and the diff hunk the reviewer commented on. The review comment itself is never part of the query, because it contains the answer.

## Point in time

Each query sees only lessons created before its pull request was opened. A lesson comment edited after that time is used with its earlier text when the GraphQL edit history provides it. When the history does not, the lesson is excluded from that query, and the exclusions are counted and reported.

## Lesson records

Each earlier comment becomes a lesson record: the comment text as the note, the commented file's directory as its `paths:` glob, and a one-line situation written by the labeler. The raw comment is kept beside the record, so any arm can also be run without the model-written situation.

## Pilot

One repository is run first to check collection, labeling accuracy, the labeler comparison and each arm's plumbing. No arm is scored in the pilot, and the pilot's outputs are not inspected for arm results. The specification is frozen after the pilot and before the first scored run.

## Two levels

- **Retrieval level, every query.** Does the arm rank a relevant lesson in its top 5? Reported as recall@5, hit@5 and mean reciprocal rank, with 95% bootstrap intervals.
- **Agent level, a fixed sample.** Given the later pull request's diff and the lessons an arm supplies, does the agent's review raise the same point the human reviewer raised? Where the human comment gives a reason, does the review give a compatible one? The reason score is reported only on queries whose reference comment states a reason, with that count.

The agent level costs model calls, so it runs on a fixed sample drawn once, with a fixed seed, before any arm runs:

- **Only recent pull requests.** Every sampled query comes from a pull request opened on or after July 1, 2026, after the agent model's documented training cutoff, so the agent cannot have seen the reviewer's comment during training. Its lessons may come from anywhere earlier in the window.
- **Equal share per repository.** 42 queries from each repository, 336 in total, drawn at random from that repository's eligible queries (at least one relevant earlier lesson). If a repository has fewer than 42, all of them are used and the shortfall is redrawn evenly from the other repositories; any shortfall is reported.
- **Size.** From [power.py](power.py): 330 paired queries give 80% power to detect a 10-point difference between two arms at a two-sided 5% level, for discordance rates up to 40%, checked by simulation under the bootstrap decision rule below. 336 meets that.

Bootstrap intervals resample queries within each repository.

## Arms

| Arm | Retrieval level | Agent level |
|---|:--:|:--:|
| memento lexical recall | yes | yes |
| memento lexical recall with `paths:` scoping (runs when path scoping ships; added as a dated changelog entry) | yes | yes |
| Plain BM25 over the lesson records | yes | yes |
| Local embedding search | yes | yes |
| A short curated file | | yes |
| A long file: the newest lessons, uncurated, up to 32 KiB (the default size cap on `AGENTS.md` content in Codex) | | yes |
| No memory | | yes |

Other tools join where they expose a retrieval interface the benchmark can call. Where a tool does not, the report says so instead of approximating it. The memento version and configuration used for each arm are recorded with the results.

## The curated-file arm

This arm stands in for a maintainer who keeps the most repeated corrections in a short instruction file, with no person choosing. For each query:

1. Take the lessons created before its pull request.
2. Rank them by how many earlier pull requests their correction had already recurred on. Ties go to the most recent lesson.
3. Keep the top lessons that fit in 2,000 tokens.

The long-file arm is a second baseline, because it shows what not curating costs at the largest size a common agent harness loads by default. A file holding every lesson does not fit a context window for most queries (55,000 to 161,000 tokens per query in the smallest repository), so it is not an arm.

## What counts as an advantage

memento has an advantage over a baseline when its agent-level rate of raising the reviewer's point is higher and the paired bootstrap 95% interval of the difference excludes zero. Anything else is reported as no advantage. Tokens loaded per query are reported beside every arm's result.

Results are reported for each repository and pooled. The pooled result decides whether there is an advantage; per-repository results are descriptive.

If memento shows no advantage over the curated-file arm, the report says so in its first paragraph. A result against the long-file arm is reported but carries less weight, because that file is a noisier baseline. Results are published for every arm whether or not memento leads.

## Publishing

- The scripts that rebuild the dataset are published. The comment text is not, so reuse stays within GitHub's terms and each author's content stays where they posted it.
- Each comment's ID and a SHA-256 hash of its text are published, so a rebuild reports which comments were edited or deleted since collection. Results are expected to reproduce within 3 percentage points of the published values when fewer than 5% of the comments have been changed or deleted.
- Labels are published as pairs of comment IDs. Cached model outputs that quote comment text are not published.

## Threats to validity

- **Review comments are a proxy.** A reviewer's repeated correction stands in for a correction given to an agent. The two can differ in wording, frequency and what counts as a mistake.
- **Retrieval is not behavior.** A lesson ranked in the top 5 does not show that an agent changed what it did. The agent level measures that, on a sample.
- **Label noise.** Model clustering can merge distinct corrections or split one correction. The label check above measures the error rate on a random sample, and the rate is reported. Candidate pairs come from lexical search, so two comments that make the same correction in unrelated words may never be compared, which undercounts clusters.
- **Repository selection.** Eight large, active projects with strong review cultures. Results may not hold for small teams or repositories with little review.
- **Sample composition.** Each repository contributes the same number of agent-level queries, so the pooled result is an average across repositories, not across comments. The busiest repositories carry more queries at the retrieval level, where per-repository results are also reported.
- **Training-data exposure.** Public review comments may appear in a model's training data, which would let an agent raise a point from memory instead of from the supplied lessons, flattering every arm including no memory. The agent level uses only pull requests opened on or after July 1, 2026, after the agent model's documented cutoff. The retrieval level uses the whole window and reports results before and after July 1, 2026 separately.
- **Drift.** Comments edited or deleted after collection change a rebuilt dataset. The published hashes make the drift measurable.

## Changelog

- **September 27, 2026, freeze.** A pilot on prometheus/prometheus checked collection, labeling and each arm's plumbing without scoring any arm, and changed the design before freezing: the labeler became two-stage (GLM-5.3-Flash, then GPT-6 Astra confirming its "same" decisions) after single-labeler and DeepSeek-V4.1-Flash-confirmed designs failed the label check on fresh pairs (precision on "same" 0.52 and 0.69); the labelers and the grader share one written definition of "same correction"; the label check is stratified and each round draws fresh pairs; relevant lessons are directly confirmed pairs, not whole clusters; the every-lesson file was replaced by the 32 KiB long file. The pilot's labels passed on fresh pairs with precision 0.91.
