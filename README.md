<!-- register: public project README | reader: coding-agent users and contributors | consumed: GitHub skim -->

# memento-tattoo

`memento-tattoo` stores corrected lessons and current project state in plain files for coding agents to retrieve across sessions. The user controls what becomes an always-loaded rule.

The loop is deliberately small:

1. **Capture:** the agent decides what from the session should change a future action.
2. **Persist:** project state, provisional lessons, and scarce operating rules are written to plain Markdown files.
3. **Retrieve:** the next session loads the rules and recalls only the lessons relevant to the current situation.

Chat, email, Slack, and documents can remain source systems. `memento-tattoo` provides the durable layer where decisions, corrections, lessons, and current state survive the session that produced them.

If you want to understand or adapt the canonical pattern, start with [MEMENTO-PATTERN.md](MEMENTO-PATTERN.md). If you want a working local CLI, install from source.

For the seven-slide explanation, clone or download the repository, then open [the HTML demo](docs/memento-tattoo-demo.html) in a browser. Keep its Memento-inspired visual asset in the same folder.

`memento-tattoo` is modeled after Christopher Nolan's *Memento*.

In the movie, Leonard cannot form new long-term memories, so everything important after his cutoff has to be externalized. LLMs face a similar operating problem: a correction from one session will not improve a later action unless it is preserved, located, and surfaced by an agent when relevant.

In *Memento*, Leonard uses a tiered memory system: notes for quick observations, Polaroids beside the people and places they explain, and tattoos for the few facts important enough to survive every reset.

`memento-tattoo` adapts that pattern for coding agents:

- notes are cheap lesson captures from corrections and reflections
- project `memory.md` files are the Polaroids beside the work
- tattoos are scarce promoted lessons that should be loaded before broad classes of action

## What it solves

`memento-tattoo` helps an agent preserve a correction, retrieve it for a later task, and decide whether it should change the next action.

That makes memory a lightweight learning loop. The model weights do not change; the working system does. Corrections become notes, repeated lessons can become tattoos, and a retention log checks whether a covering lesson was detected at the write-time checkpoint.

## What you get

- **A promotion gate with a lifecycle.** Corrections become rules, rules can become scarce tattoos, and `tattoo-audit` flags promoted lessons for keep, demote, or cut review.
- **Situation-recognition recall.** The `load` command ranks lessons against the situation named in a query, across hot and archived notes.
- **Checked retrieval with a retention log.** When a correction or reflection is written, the system records whether a covering lesson was detected at that write-time checkpoint. Authors can separately record whether a lesson was missed or applied.
- **Plain-text memory you can inspect, repair, and delete.** Notes, project memory, and tattoos are Markdown files. No database, no service dependency.
- **Optional local coordination for parallel agents.** Advisory locks, reserved session IDs, and a queued registry drain for concurrent local sessions.

## What the retention signal proves

The historical retention-health signal compares the recorded `existing-missed` and `new` classifications. Automatic retrieval now records `related` for a possible covering lesson; authors can explicitly record `existing-missed`, `applied`, or `overapplied`. Re-run the deterministic baseline with `.venv/bin/python scripts/retention_eval.py`:

```text
existing-missed / (new + existing-missed)
```

It measures note-write classification hygiene. It does not measure behavioral repeat reduction, retrieval exposure, whether an agent applied a lesson, or recurrence against opportunities; optional author observations do not supply comprehensive exposure or opportunity denominators. The deterministic cover-detection evaluation reports a baseline of 3/3 true covers flagged (1.00 coverage) and 0/3 negative queries flagged (0.00 false-positive rate). Those figures measure cover detection, not behavioral repeat reduction.

## Install from a checkout

Requires Python 3.11 or newer on macOS or Linux. The locking implementation uses POSIX `fcntl`, so Windows is not currently supported. Use the matching interpreter for your system:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
```

If your system provides Python 3.11 instead, use `python3.11 -m venv .venv`.

Then run:

```bash
.venv/bin/memento-tattoo --root examples/basic/memento doctor
```

## Quickstart

Inspect the example root:

```bash
.venv/bin/memento-tattoo --root examples/basic/memento load --project examples/basic/project --query "claiming complete verification"
.venv/bin/memento-tattoo --root examples/basic/memento garden
```

Create a new root:

```bash
mkdir -p .tmp/demo-project .tmp/demo-memento

project_state=$(cat <<'EOF'
- Situation: claiming a code change is complete
- Note: run the relevant test or smoke command before saying the change is complete.
EOF
)

.venv/bin/memento-tattoo --root .tmp/demo-memento project-edit \
  --project .tmp/demo-project \
  --sess sess_demo \
  --section "## State" \
  "$project_state"

note_text=$(cat <<'EOF'
Situation: claiming a code change is complete
Note: run the relevant test or smoke command before saying the change is complete.
aliases: tests, verification, done, complete
EOF
)

.venv/bin/memento-tattoo --root .tmp/demo-memento note-add --sess sess_demo --kind seed "$note_text"

# Only after observed recurrence, all promotion gates,
# and explicit user approval of this wording:
.venv/bin/memento-tattoo --root .tmp/demo-memento tattoo-add --sess sess_demo "Before claiming work is complete, run the command that proves it and read the output."
.venv/bin/memento-tattoo --root .tmp/demo-memento doctor --project .tmp/demo-project
.venv/bin/memento-tattoo --root .tmp/demo-memento load --project .tmp/demo-project --query "claiming complete verification"
```

## Try the pattern without installing

You do not need the CLI to try the idea. Copy [templates/AGENTS.md](templates/AGENTS.md) into a repo, adapt the paths, and create the plain Markdown files shown in [File layout](#file-layout): a project `memory.md` beside the work, plus `notes.md`, `tattoos.md`, and a retention log under a `memento/` root.

That plain-Markdown version is enough for a single agent or a repo-local convention. It does not provide real concurrent-write protection. Modern coding agents already have memory surfaces (`AGENTS.md`, `CLAUDE.md`, rules files, auto-memory folders, hooks); `memento-tattoo` does not replace them, it gives them a correction-retention loop. The CLI adds checked writes, ranked recall, doctor checks, gardening, and optional local coordination.

## The agent is the judge

`memento-tattoo` does not decide what matters by itself. The CLI writes, checks, recalls, and coordinates files. The agent decides what deserves to be written.

At the end of a session, or when the user says something like "save work", the agent scans the work just completed and decides what belongs in the session record, whether project `memory.md` should change, whether a correction should become a note or repair an existing one, and whether any lesson is a tattoo candidate. This is a judgment pass, not a transcript dump. The useful question is:

```text
What from this session should change a future action?
```

A tattoo is not a good tip, a summary, or a project fact. It is a scarce operating lesson meant to be visible before broad classes of future action. Propose one only when, had it been loaded at the start of the session, it would have dramatically improved the course of action, and the lesson has recurred, is durable across unrelated sessions, changes future behavior, reaches beyond the file that produced it, and fits a declarative principle or compact rule. Promotion requires explicit user approval before running `tattoo-add`.

At session end, the agent manually proposes the strongest candidate and its reason for clearing the bar. The CLI neither proposes nor parks candidates. Explicit approval promotes the proposed wording. Rejection leaves any useful lesson as an ordinary note. No action parks the candidate in a durable non-tattoo surface, such as a session marker or tagged note, for later review. Silence is never approval.

## How agents invoke the CLI

The CLI is usually not typed by hand during normal agent work. Map natural-language commands into `AGENTS.md`, `CLAUDE.md`, or your agent runner's instruction file.

Common mappings:

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

### Current project context and guarded updates

Use `memento-tattoo load --query "<situation and action>" --project <directory>` to combine a project's explicit current-state section with relevant lessons. Historical notes remain searchable and superseded entries remain labelled. For a registry edit, copy the inspected line into `registry_delta.expected_line` in the save JSON. The driver rejects a stale draft before writing the session; drain rechecks for intervening changes. An empty expected line means the entry must be absent. See [the pattern contract](MEMENTO-PATTERN.md#retrieve-for-the-action-and-save-the-actual-changes) for scope and compatibility.

## Failure loop example

The basic example shows the loop this project is designed for:

1. An agent claims a code change is complete without running the proof command.
2. The user correction is captured as a note in [examples/basic/memento/notes.md](examples/basic/memento/notes.md).
3. The retention log records that an existing verification lesson was missed in [examples/basic/memento/retention_log.jsonl](examples/basic/memento/retention_log.jsonl).
4. If the user approves the broader completion rule, it is promoted to [examples/basic/memento/tattoos.md](examples/basic/memento/tattoos.md).
5. A later task can load the tattoo before claiming completion.

See [examples/basic/README.md](examples/basic/README.md) for the concrete walkthrough.

## Advanced: local coordination

If you run parallel local agents, the CLI has coordination guardrails: advisory locks for short writes, reserved session IDs, idempotent markers, and a queued registry drain path.

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

Core loop:

```text
memento-tattoo --root <path> note-add      # capture a correction/reflection lesson
memento-tattoo --root <path> tattoo-add    # write an approved promoted lesson
memento-tattoo --root <path> project-edit  # update adjacent project memory.md
memento-tattoo --root <path> load          # rank relevant lessons for a task
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
  _queue/
    applied/
      archive/
    conflicts/
      archive/
  .memento.lock
  .reserved_ids
```

- `project/memory.md`: adjacent project action journal: key decisions, state, and work performed.
- `memento/notes.md`: provisional lessons and corrections.
- `memento/notes_archive.md`: older note blocks rotated out of the hot file; still read during recall.
- `memento/tattoos.md`: promoted lessons that should be broadly reusable.
- `memento/retention_log.jsonl`: hot portion of the checked-retrieval history; older complete events rotate out by byte target.
- `memento/retention_log_archive.jsonl`: append-only archive of rotated retention events. Readers combine it with the hot log, so the logical history remains complete.
- `memento/tattoo_firing.json`: supplemental local citation counter used by tattoo review. Durable note and session citations remain authoritative when this cache is stale or missing.
- `memento/registry.md`: optional compact index of project summaries.
- `memento/sessions/`: per-session save records and generated indexes; `archive/` holds rotated-out session files (still counted for ID-collision safety).
- `memento/_queue/`: durable registry deltas waiting for drain, applied-delta receipts, and conflict artifacts. Older receipts move to `applied/archive/` for replay checks. Old or excess conflicts move to `conflicts/archive/` without deletion.
- `memento/.memento.lock`: advisory lock for short write operations.
- `memento/.reserved_ids`: short-lived session-ID reservations so parallel agents do not collide before a session file is written.

`session-list` includes hot and archived records by default. `session-archive` moves only records older than the caller-selected `--days` cutoff, previews exact paths by default, and moves files only with `--apply`. Archived sessions remain readable to lookup, rebuild, and collision checks.

`doctor` reports note alias coverage as `aliased/total` for hot and archived note stores separately. Its archived-store recommendation starts at 60 percent coverage. It also reports tattoo count, total UTF-8 bytes, and over-length tattoos. The starting review recommendations are 25 tattoos, 7,168 bytes, and 300 characters per tattoo. Each warning can be changed or disabled without hiding its measurement. Warnings start a keep, demote, merge, or cut review and never remove a lesson automatically.

## Out of scope

This reference implementation does not include vector search, embeddings, a database, an MCP server, auto-capture hooks, hosted sync, transcript storage, a generic personal memory system, benchmark claims, or migration tooling from any private setup.

## Docs

- [Canonical Memento pattern](MEMENTO-PATTERN.md)
- [Agent instruction template](templates/AGENTS.md)
- [Basic failure-loop example](examples/basic/README.md)
- [Concepts](docs/concepts.md)
- [Design essay](docs/essay.md)

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

Choose a new destination outside the source tree. The exporter rejects existing destinations and source symlinks. Verify the export and built package in an isolated environment before publishing. The package version remains 0.3.1; the Unreleased changelog records changes since the August 30 source update.
