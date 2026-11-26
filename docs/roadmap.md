<!-- register: public roadmap | reader: coding-agent users, prospective contributors, maintainers of related tools | consumed: GitHub read, linked from the README -->

# Roadmap

`memento-tattoo` keeps an agent's corrections and project decisions in local Markdown, so the next session starts with them. This page covers what 0.5.0 contains, what the first benchmark found, and what waits until someone needs it.

## Constraints that do not change

- The CLI never calls a model. Relevance judgment stays with the agent reading the output.
- Markdown files are the source of truth. Anything generated can be deleted and rebuilt from them.
- No runtime dependencies, no vector database, no hosted service.
- The only required integration is a repo instruction file the harness already reads (`AGENTS.md`, `CLAUDE.md` or a rules file).
- Compatibility claims name the harness, model and version that were tested.

## 0.5.0, the first tagged release

- **Install in one command.** `uvx --from git+https://github.com/stewtong/memento-tattoo memento-tattoo init` creates the memory root and a project `memory.md`, copies the protocol, and prints the stub to paste. It never overwrites a file. Optional adapters write an [Agent Skills](https://agentskills.io/specification.md) `SKILL.md` or print the line that makes `CLAUDE.md` import `AGENTS.md`.
- **A small always-on footprint.** A 721-byte stub replaces the 11 KB instruction template of 0.3.1 in the always-loaded instruction file. The full procedure lives in `PROTOCOL.md`, which the agent reads only when the user corrects it, when it recognizes a past situation, when the user says "save work", or when the user asks it to bring in rules kept elsewhere.
- **Rules that carry their reasons.** Notes take an optional `Why:` field, approved rules have a documented shape (the action with its trigger, then the reason), and `doctor` reports how many records have one.
- **A better flagship example.** The example rule is now a fact a model cannot work out for itself: before changing a package's public API, search the other packages for callers, because CI runs only the changed package's tests.
- **Better search, still without embeddings.** Queries match whole words (so "art" no longer matches "start") with plural folding, and `load` ranks with field-weighted BM25, so a rare word counts for more than a common one.
- **A security policy** and private vulnerability reporting.

Each release is a tagged GitHub release with the built package attached and notes from the changelog. The package is installed from GitHub; it is not published to PyPI.

## A small public benchmark for repeated corrections

We found no public benchmark that tests whether a memory system surfaces a past correction before the same mistake happens again, so we built a small one from public code review. When a reviewer makes the same correction on several pull requests, each later instance is a query and the earlier comments are the lessons that should have been available. The [specification](../bench/w9b/README.md) was fixed before any result was scored, and narrowed from eight repositories to one before scoring. The specification and its changelog were kept in a private working copy until the 0.5.0 release, so the freeze and change dates are the author's record, not public commits.

The [first results](../bench/w9b/RESULTS.md) cover one repository, prometheus/prometheus, with 50 queries across six ways of choosing the lessons an agent sees: `memento-tattoo`, plain BM25, local embeddings, a short curated file, a long uncurated file, and no memory. `memento-tattoo` showed no advantage over any of the other five; all six raised the reviewer's point on 25 to 27 of the 50 queries. The relevant earlier lesson reached the agent in 7 of 50 queries with `memento-tattoo` and 12 of 50 with the long file. The benchmark searches with the raw diff; a query written by the agent was not tested. The sample detects only differences of about 18 percentage points or more at 80% power; a smaller real difference would usually read as no advantage, so this result does not show that the arms are equivalent. Against no memory the difference was +4 points, with a 95% interval of 0 to +10: `memento-tattoo` raised the point on 2 queries that no memory missed and missed none that no memory raised. The benchmark counts an advantage only when the interval excludes zero, so by its rule this is no advantage. No person checked any label or grade. GLM-5.3-Flash made the labels and GPT-6 Astra confirmed them; the only check of their accuracy, on samples of 200 pairs, was made by Claude Opus 5.5, which is also the agent and the grader. The scored repository is also the pilot repository: its pairs were used to tune the labeling, so the label checks measure agreement with the grader the labeling was tuned toward.

## Later, if people need it

These are designed but not scheduled. Open a discussion if one would help you.

- Path-scoped rules and `load --path`, which walks `memory.md` files from a file up to the repo root.
- Exporting rules into Claude Code, Cursor, OpenCode and Kilo Code rule files.
- Merge-safe storage for teams, reference and secrets checks in `doctor`, and a GitHub Action.
- Several phrasings per query, and a candidate list built for the agent's judgment.
- Reviewing rules when a new model starts reading them.
- The benchmark with a query written by the agent instead of the raw diff, and on more repositories.
- Windows support, through an `msvcrt` lock beside the current POSIX `fcntl` lock, once the lock tests pass on a Windows runner.

## Related projects

- [okf-agent-memory](https://github.com/okf-memory/okf-agent-memory): git-native agent memory with BM25 search and path lookup, built on Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).
- [claude-reflect](https://github.com/BayramAnnakov/claude-reflect): captures corrections into a review queue before syncing approved ones into instruction files.
- [rulesync](https://github.com/dyoshikawa/rulesync) and [ruler](https://github.com/intellectronica/ruler): generate each harness's rule files from one source.
- [Agent Skills](https://agentskills.io/): the open skill format the optional adapter targets.

## How to help

- Design questions and proposals are welcome in GitHub Discussions.
- Report security problems privately, as described in `SECURITY.md`.
- Bug reports with a small synthetic reproduction are the most useful contribution.
