<!-- register: public project README | reader: coding-agent users and contributors | consumed: GitHub skim -->

# memento-tattoo

**Persistent memory for coding agents, inspired by Christopher Nolan's *Memento*.**

Keep corrections and project decisions available across sessions. `memento-tattoo` stores them in local Markdown files and ranks the stored lessons against the next task. It is designed to be harness- and model-agnostic: the one required integration is an instruction file the agent already reads, such as `AGENTS.md`, `CLAUDE.md`, or a rules file. Tested harness and model combinations will be listed here once the cross-harness smoke test has run.

In *Memento*, Leonard relies on notes, Polaroids, and tattoos because he cannot form new long-term memories. Coding agents also need records to carry corrections across sessions. Those records can be wrong, stale, or taken out of context. You and your agent preserve reasons and evidence, record revisions, and mark superseded advice. You approve the few rules loaded every session. The CLI never verifies a lesson's truth by itself; that judgment stays with you and your agent.

`memento-tattoo` adapts the film's tiered system:

- **Notes** (`notes.md`) capture lessons from corrections and experience.
- **Polaroids** (project `memory.md` files) keep decisions and current state beside the work.
- **Tattoos** (`tattoos.md`) are the few rules you explicitly approve for loading at the start of each session.

![Evidence board in the style of Memento: pinned Polaroids of project state, handwritten notes, and red string converging on a small forearm tattoo, the notes, memory, and tattoo layers of memento-tattoo](docs/memento-memory-hero-v2.png)

The same pattern works for research, writing, and other knowledge work, anywhere a correction or decision should outlive the session that produced it. Coding agents are the primary audience and the first example. Everything is plain Markdown you can inspect, repair, and delete: no database, no hosted service, and no model dependency in the CLI.

## The loop in one example

1. In a monorepo, an agent renames a public function in the billing package. The billing tests pass and CI is green, because CI runs only the changed package's tests. After merge, the checkout package, which still calls the old name, breaks.
2. The user's correction is captured as a note with the situation it applies to, the lesson, and a `Why:` line naming the cause the agent could not see, in [examples/basic/memento/notes.md](examples/basic/memento/notes.md).
3. When a later API change repeats the mistake, the retention log records that the existing lesson was missed, in [examples/basic/memento/retention_log.jsonl](examples/basic/memento/retention_log.jsonl).
4. If you approve the wording, the lesson is promoted to [examples/basic/memento/tattoos.md](examples/basic/memento/tattoos.md): "Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests."
5. The next session loads that tattoo at start, so the agent searches for callers before CI can give a false green.

See [examples/basic/README.md](examples/basic/README.md) for the concrete walkthrough. The loop is deliberately small: **capture** what from the session should change a future action, **persist** it to plain Markdown, and **retrieve** only the lessons relevant to the next task.

## Adoption

The agent reads memento's instructions in two layers:

- A short stub, [templates/memento-stub.md](templates/memento-stub.md), goes in the instruction file your agent loads every session. It loads tattoos at start, points at the nearest project `## Current state`, and says when to open the protocol.
- [templates/PROTOCOL.md](templates/PROTOCOL.md), copied to `memento/PROTOCOL.md`, holds the procedure: handling a correction, retrieving lessons, the save judgment pass, bringing in existing rules, the note and tattoo formats, and the promotion gates. The agent reads it only when the user corrects it, when it recognizes a past lesson's situation, when the user says "save work", or when the user asks it to bring in existing rules, so it costs nothing in other sessions.

With the CLI installed, `memento-tattoo init` creates the memory root and project `memory.md`, copies `PROTOCOL.md`, and prints the stub to paste. It never overwrites an existing file. `init --adapter skill` also writes an Agent Skills `SKILL.md` that points to the protocol, and `init --adapter claude-md-import` prints the line that makes `CLAUDE.md` import `AGENTS.md` (with `--write`, it creates `CLAUDE.md` when absent). See [Concepts](docs/concepts.md#instruction-surface-and-init) for the options.

### Use the plain Markdown pattern

You do not need the CLI to try the idea. Copy `templates/PROTOCOL.md` to `memento/PROTOCOL.md`, paste the stub into your instruction file, and create the files shown in [File layout](#file-layout): a project `memory.md` beside the work, plus `notes.md`, `tattoos.md`, and a retention log under `memento/`. [templates/AGENTS.md](templates/AGENTS.md) shows the stub beside a sample repo's own rules. That is enough for a single agent or a repo-local convention; it does not provide concurrent-write protection.

Modern coding agents already have memory surfaces (`AGENTS.md`, `CLAUDE.md`, rules files, auto-memory folders, hooks). `memento-tattoo` does not replace them; it gives them a correction-retention loop. To bring rules you already keep into memento, ask your agent to follow "When the user asks you to bring in existing rules" in `memento/PROTOCOL.md`. It proposes candidate notes for your approval and leaves the original file unchanged.

## Install from GitHub

Requires Python 3.11 or newer on macOS or Linux; the locking implementation uses POSIX `fcntl`, so Windows is not currently supported. The package is distributed from this repository, not PyPI. To set up a repository without installing anything permanently, run this from its root:

```bash
uvx --from git+https://github.com/stewtong/memento-tattoo memento-tattoo init
```

To keep the command installed, use `pipx install git+https://github.com/stewtong/memento-tattoo`. Add a release tag to pin a version, for example `git+https://github.com/stewtong/memento-tattoo@v0.5.1`. `init` prints a short stub; paste it into the instruction file your agent reads every session (see [Adoption](#adoption)).

## Install from a checkout

For development or to run the bundled examples:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
```

If your system provides Python 3.11 instead, use `python3.11 -m venv .venv`.

The CLI adds checked writes, ranked recall, `doctor` checks, gardening, and optional local coordination for parallel agents.

## Quickstart

Verify the install against the bundled example:

```bash
.venv/bin/memento-tattoo --root examples/basic/memento doctor
.venv/bin/memento-tattoo --root examples/basic/memento load --project examples/basic/project --query "changing a package public API callers"
```

Create a new root and run the loop once:

```bash
.venv/bin/memento-tattoo init --root .tmp/demo/memento --project .tmp/demo

.venv/bin/memento-tattoo --root .tmp/demo/memento project-edit \
  --project .tmp/demo \
  --sess sess_demo \
  --section "## Current state" \
  --replace \
  "- Situation: billing package API rename
- Note: format_amount is now format_money; the checkout caller was updated in the same change."

note_text=$(cat <<'EOF'
Situation: changing a function signature or name in a shared package's public API
Note: search every other package for callers before changing a package's public API.
Why: CI runs only the changed package's tests, so a broken caller in another package stays green until it ships.
aliases: monorepo, breaking change, rename, callers, ci
EOF
)

.venv/bin/memento-tattoo --root .tmp/demo/memento note-add --sess sess_demo --kind correction "$note_text"

# Only after observed recurrence, all promotion gates,
# and explicit user approval of this wording:
.venv/bin/memento-tattoo --root .tmp/demo/memento tattoo-add --sess sess_demo "Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests."
.venv/bin/memento-tattoo --root .tmp/demo/memento doctor --project .tmp/demo
.venv/bin/memento-tattoo --root .tmp/demo/memento load --project .tmp/demo --query "changing a package public API callers"
```

`init` lists each file it created under `.tmp/demo/` and prints the stub. `doctor` also prints a few WARN lines for things a fresh root does not have yet, such as a `project.md`. Among its checks:

```text
PASS  why-coverage: hot 1/1 with Why; archive 0/0 with Why
PASS  project-memory: memory.md present for demo
PASS  tattoo-reasons: 1/1 with a reason clause
```

`load` prints the current state from `.tmp/demo/memory.md`, then ranks the note first and the tattoo second:

```text
  situation: changing a function signature or name in a shared package's public API
  note: search every other package for callers before changing a package's public API.
```

## Everyday use

### The agent is the judge

`memento-tattoo` does not decide what matters by itself. The CLI writes, checks, recalls, and coordinates files; the agent decides what deserves to be written.

At the end of a session, or when the user says something like "save work", the agent scans the work just completed and decides what belongs in the session record, whether project `memory.md` should change, whether a correction should become a note or repair an existing one, and whether any lesson is a tattoo candidate. This is a judgment pass, not a transcript dump. The useful question is:

```text
What from this session should change a future action?
```

The strongest material is what the current repository or sources cannot cheaply reconstruct: why an option was rejected, the basis of a decision, a verified technique, and the conditions and exceptions attached to a correction.

### Tattoos are scarce

A tattoo is not a good tip, a summary, or a project fact. It is a scarce operating lesson meant to be visible before broad classes of future action. Propose one only when, had it been loaded at the start of the session, it would have dramatically improved the course of action, and the lesson has recurred, is durable across unrelated sessions, changes future behavior, reaches beyond the file that produced it, and fits a declarative principle or compact rule.

At session end, the agent manually proposes the strongest candidate and its reason for clearing the bar. The CLI neither proposes nor parks candidates. Explicit approval promotes the proposed wording; rejection leaves any useful lesson as an ordinary note. If the user takes no action, park the candidate in a durable non-tattoo surface, such as a session marker or tagged note, for later review. Silence is never approval.

### Read the full record before revising it

Recall previews identify their source, indicate clipping and provide a full-read command. `entry-read` returns complete content and a digest; `--format markdown` shows active and prior versions as readable sections. `note-amend` uses that digest to reject stale edits, preserves the creation ID and records the previous active body with its reason and evidence. It edits ordinary notes without creating application counts or promoting rules. See [complete reads and amendments](docs/concepts.md#read-complete-evidence-and-revise-ordinary-notes) for the CLI contract.

### Mapping agent commands

The CLI is usually not typed by hand during normal agent work. Map natural-language commands into `AGENTS.md`, `CLAUDE.md`, or your agent runner's instruction file:

```text
"load memory"
  -> load tattoos at startup, then run `memento-tattoo --root <memento_root> load --project <project_dir> --query "<task situation>"`

"remember this"
  -> run `memento-tattoo --root <memento_root> note-add --sess <sess_id> --kind correction "<lesson>"`

"save work"
  -> scan the session, reserve a session id, draft one `save-commit` spec, and run `save-commit`; surface any tattoo candidate separately and run `tattoo-add` only after explicit approval

"check memory"
  -> run `memento-tattoo --root <memento_root> doctor --project <project_dir>`
```

If your agent runner supports hooks, hooks can call the same CLI commands: session start (`load`), long-running checkpoints (`session-add` or `project-edit`), post-commit summaries (`project-edit`), session end (the save-work judgment pass), and periodic maintenance (`garden` and `doctor`). Hooks should not blindly promote tattoos; promotion still needs agent judgment and explicit user approval.

### Saving a full session

For a runnable JSON spec that saves a session, project state, and registry entry, follow [Save work with the CLI](docs/save-work.md). It includes read-back and replay commands, and the [registry format](docs/concepts.md#registry-queue) shows the complete file and its entry metadata.

Use `memento-tattoo load --query "<situation and action>" --project <directory>` to combine a project's explicit current-state section with relevant lessons. Historical notes remain searchable and superseded entries remain labelled. For a registry edit, copy the inspected line into `registry_delta.expected_line` in the save JSON. The driver rejects a stale draft before writing the session; drain rechecks for intervening changes. An empty expected line means the entry must be absent. See [the pattern contract](MEMENTO-PATTERN.md#retrieve-for-the-action-and-save-the-actual-changes) for scope and compatibility.

## Retrieval, retention, and what the numbers prove

`load` ranks lessons against the situation named in the query, across hot and archived notes, and includes the project's explicit current-state section. When a correction or reflection is written, the system records whether a covering lesson was detected at that write-time checkpoint; authors can separately record whether a lesson was missed, applied, or overapplied.

You can re-run the deterministic baseline with `.venv/bin/python scripts/retention_eval.py`, which checks the classifier's cover detection against a small bundled set of cases. It prints 3/3 true covers flagged (1.00 coverage) and 0/3 negative queries flagged (0.00 false-positive rate); three cases each cannot show more than that the classifier works on them.

Those figures measure note-write classification hygiene and cover detection. They do not measure behavioral repeat reduction, retrieval exposure, whether an agent applied a lesson, or recurrence against opportunities; optional author observations do not supply comprehensive exposure or opportunity denominators. A promotion gate with a review lifecycle sits on top: corrections become rules, rules can become scarce tattoos, and `tattoo-audit` flags promoted lessons for keep, demote, or cut review.

Whether retrieval helps an agent avoid a repeated mistake is measured separately, by a benchmark built from public code review: when a reviewer makes the same correction on several pull requests, does the earlier comment reach an agent reviewing the later one, and does the agent raise the point? The [first results](bench/w9b/RESULTS.md), on one repository (prometheus/prometheus) with 50 queries, found no advantage for `memento-tattoo` over a short curated file, a long uncurated file, plain BM25, local embeddings, or no memory. All six raised the reviewer's point on 25 to 27 of the 50 queries. Against no memory the difference was +4 points, with a 95% interval of 0 to +10: `memento-tattoo` raised the point on 2 queries that no memory missed and missed none that no memory raised. The benchmark counts an advantage only when the interval excludes zero, so by its rule this is no advantage. The sample detects only differences of about 18 percentage points or more at 80% power; a smaller real difference would usually read as no advantage, so this result does not show that the arms are equivalent. The relevant earlier lesson reached the agent in 7 of 50 queries with `memento-tattoo` and 12 of 50 with the long file. The benchmark searches with the raw diff; a query written by the agent, as in normal use, was not tested. No person checked any label or grade. GLM-5.3-Flash made the labels and GPT-6 Astra confirmed them; the only check of their accuracy, on samples of 200 pairs, was made by Claude Opus 5.5, which is also the agent and the grader. The scored repository is also the pilot repository: its pairs were used to tune the labeling, so the label checks measure agreement with the grader the labeling was tuned toward. The method is in the [specification](bench/w9b/README.md).

## Advanced: local coordination

If you run parallel local agents, the CLI has coordination guardrails: advisory locks for short writes, reserved session IDs, idempotent markers, and a queued registry drain path. Interrupted project writes are recovered from recorded content hashes, and a completed save cannot be replayed to restore superseded state. All writers of the same project must use the same memory root, and replay checks depend on keeping the `_project_receipts/` directory (see [File layout](#file-layout)).

This is designed for a local filesystem. Network filesystems and sync folders may not preserve lock semantics. See [Concepts](docs/concepts.md) for the mechanics.

## Design bets

- Memory should be plain text you can inspect, repair, and delete.
- Project memory belongs next to the project, close to the work it explains.
- Corrections matter more than transcripts.
- Promotion should be scarce. The tattoo layer is valuable because it refuses to be everything. `tattoo-audit` flags promoted lessons that are due for a keep, demote, or cut review so the tattoo set does not grow without bound.
- `note-add` keeps the hot `notes.md` bounded by rotating older blocks out to `notes_archive.md`; recall reads both files, so rotation stays non-lossy.
- `doctor` reports alias coverage and tattoo-budget pressure as review signals. It does not repair aliases, demote tattoos, or remove lessons.

## CLI at a glance

Examples include the shared `--root <path>` flag; add `--agent <agent_id>` when you want provenance for parallel sessions. These are abbreviated command shapes; see [Concepts](docs/concepts.md) for full options.

Setup:

```text
memento-tattoo init [--root <path>]        # create the root, copy PROTOCOL.md, print the stub
```

Core loop:

```text
memento-tattoo --root <path> note-add      # capture a correction/reflection lesson
memento-tattoo --root <path> tattoo-add    # write an approved promoted lesson
memento-tattoo --root <path> project-edit  # update adjacent project memory.md
memento-tattoo --root <path> load          # rank relevant lessons for a task
memento-tattoo --root <path> entry-read    # read complete content, digest and history
memento-tattoo --root <path> note-amend    # revise an ordinary note with a digest guard
```

Maintenance:

```text
memento-tattoo --root <path> doctor
memento-tattoo --root <path> garden
memento-tattoo --root <path> rebuild --check
memento-tattoo --root <path> tattoo-audit  # flags promoted lessons due for keep/demote/cut review
memento-tattoo --root <path> session-list --limit 50
memento-tattoo --root <path> session-archive --days 30 --limit 100  # dry run
memento-tattoo --root <path> session-archive --days 30 --limit 100 --apply
```

Advanced local coordination:

```text
memento-tattoo --root <path> new-id
memento-tattoo --root <path> session-add ...
memento-tattoo --root <path> registry-queue ...
memento-tattoo --root <path> drain
memento-tattoo --root <path> save-commit --spec <json>
```

## File layout

A project and memento root use adjacent files:

```text
project/
  memory.md

memento/
  PROTOCOL.md
  notes.md
  notes_archive.md
  tattoos.md
  retention_log.jsonl
  retention_log_archive.jsonl
  tattoo_firing.json
  registry.md
  sessions/
    sess_abcd.md
    index.md
    index-recent.md
    archive/
  _project_receipts/
  _queue/
    applied/
      archive/
    conflicts/
      archive/
  .memento.lock
  .reserved_ids
```

`init` creates `project/memory.md`, `memento/PROTOCOL.md`, `notes.md`, `tattoos.md`, and `retention_log.jsonl`. The CLI adds the other files when the features that use them run.

- `project/memory.md`: adjacent project action journal: key decisions, current state, and work performed.
- `memento/PROTOCOL.md`: the agent procedure, read when a correction, a recognized situation, or "save work" calls for it.
- `memento/notes.md`: provisional lessons and corrections.
- `memento/notes_archive.md`: older note blocks rotated out of the hot file; still read during recall.
- `memento/tattoos.md`: promoted lessons that should be broadly reusable.
- `memento/retention_log.jsonl`: hot portion of the checked-retrieval history; older complete events rotate out by byte target.
- `memento/retention_log_archive.jsonl`: append-only archive of rotated retention events. Readers combine it with the hot log, so the logical history remains complete.
- `memento/tattoo_firing.json`: supplemental local citation counter used by tattoo review. Durable note and session citations remain authoritative when this cache is stale or missing.
- `memento/registry.md`: optional compact index of project summaries.
- `memento/_project_receipts/`: JSON receipts for `project-edit` and `save-commit` operations, keyed by project path and delta ID, including standalone project edits that carry no registry delta. Keep these receipts with the memory root; replay checks and standalone-edit replay protection depend on them, and there is no automatic pruning.
- `memento/sessions/`: per-session save records and generated indexes; `archive/` holds rotated-out session files (still counted for ID-collision safety).
- `memento/_queue/`: durable registry deltas waiting for drain, applied-delta receipts, and conflict artifacts. Older receipts move to `applied/archive/` for replay checks. Old or excess conflicts move to `conflicts/archive/` without deletion.
- `memento/.memento.lock`: advisory lock for short write operations.
- `memento/.reserved_ids`: short-lived session-ID reservations so parallel agents do not collide before a session file is written.

`session-list` includes hot and archived records by default. `session-archive` moves only records older than the caller-selected `--days` cutoff, previews exact paths by default, and moves files only with `--apply`. Archived sessions remain readable to lookup, rebuild, and collision checks.

`doctor` reports note alias coverage as `aliased/total` for hot and archived note stores separately, and `Why:` coverage the same way. Its archived-store recommendation starts at 60 percent coverage. It also reports tattoo count, total UTF-8 bytes, and over-length tattoos. The starting review recommendations are 25 tattoos, 7,168 bytes, and 300 characters per tattoo. It also counts tattoos written with a reason clause. `Why:` and reason-clause coverage are report-only unless you set `--why-coverage-warn` or `--tattoo-reason-warn`. Each warning can be changed or disabled without hiding its measurement. Warnings start a keep, demote, merge, or cut review and never remove a lesson automatically.

## Out of scope

This reference implementation does not include vector search, embeddings, a database, an MCP server, auto-capture hooks, hosted sync, transcript storage, a generic personal memory system, or migration tooling from any private setup.

## Docs

- [Canonical Memento pattern](MEMENTO-PATTERN.md)
- [Agent protocol](templates/PROTOCOL.md) and [instruction stub](templates/memento-stub.md)
- [Example AGENTS.md](templates/AGENTS.md)
- [Save work with the CLI](docs/save-work.md)
- [Basic failure-loop example](examples/basic/README.md)
- [Concepts](docs/concepts.md)
- [Design essay](docs/essay.md)
- [Security policy](SECURITY.md)
- [Roadmap](docs/roadmap.md)
- [Repeated-correction benchmark results](bench/w9b/RESULTS.md) and [evaluation code](bench/README.md)
- For the seven-slide explanation, clone or download the repository, then open [the HTML demo](docs/memento-tattoo-demo.html) in a browser. Keep its Memento-inspired visual asset in the same folder.

## License

Apache-2.0.

## Development

```bash
.venv/bin/python -m pip install build
.venv/bin/python -m pytest -q
.venv/bin/python -m build
```

The repo ships to GitHub through an export script that produces a clean public tree:

```bash
.venv/bin/python scripts/export_public.py ../memento-public-export
```

Choose a new destination outside the source tree. The exporter rejects existing destinations and source symlinks. Verify the export and built package in an isolated environment before publishing. Releases are tagged on GitHub; pushing a `v*` tag that matches the package version runs `.github/workflows/release.yml`, which tests, builds, and publishes the GitHub release with the changelog entry as its notes.

The evaluation code in `bench/` is not part of the package. Its tests run with `.venv/bin/python -m pytest bench/tests bench/w9b/tests`.
