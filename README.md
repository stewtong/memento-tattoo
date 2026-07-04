# memento-tattoo

`memento-tattoo` is a correction-retention loop that helps coding agents stop repeating corrected mistakes across sessions.

If you want to understand or adapt the pattern, start with [IDEA.md](IDEA.md). If you want a working local CLI, install from source.

`memento-tattoo` is modeled after Christopher Nolan's *Memento*.

In the movie, Leonard cannot form new long-term memories, so everything important after his cutoff has to be externalized. LLMs face a similar operating problem: a correction from one session will not improve a later action unless it is preserved, located, and surfaced by an agent when relevant.

In *Memento*, Leonard uses a tiered memory system: notes for quick observations, Polaroids beside the people and places they explain, and tattoos for the few facts important enough to survive every reset.

`memento-tattoo` adapts that pattern for coding agents:

- notes are cheap lesson captures from corrections and reflections
- project `memory.md` files are the Polaroids beside the work
- tattoos are scarce promoted lessons that should be loaded before broad classes of action

Generic memory stores context. `memento-tattoo` stores corrections that should alter future behavior.

## What it solves

Most agent memory systems start by asking how much context can be recalled. `memento-tattoo` asks a narrower question: what correction would change the agent's next action?

That makes memory a lightweight continuous-learning loop. The model weights do not change; the working system does. Corrections become notes, repeated lessons can become tattoos, and a retention log checks whether the right lesson showed up when it mattered.

## What you get

- **Checked retrieval with a retention log.** Every recall records whether the right lesson surfaced when it mattered, so you get recall of lessons, not just recall of events. This loop is the core differentiator.
- **Situation-recognition recall.** Lessons are ranked for the current task, so a correction resurfaces the moment the situation has a name again.
- **Scarce promotion with a lifecycle.** Tattoos stay rare, and `tattoo-audit` flags promoted lessons due for a keep, demote, or cut review so the set does not grow without bound.
- **Plain-text memory you can inspect, repair, and delete.** Notes, project memory, and tattoos are Markdown files. No database, no service dependency.
- **Optional local coordination for parallel agents.** Advisory locks, reserved session IDs, and a queued registry drain for concurrent local sessions.

## Install from a checkout

Requires Python 3.11 or newer. Use the matching interpreter for your system:

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

# If the user approves the promoted rule:
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

A tattoo is not a good tip, a summary, or a project fact. It is a scarce operating lesson meant to be visible before broad classes of future action. Propose one only when, had it been loaded at the start of the session, it would have dramatically improved the course of action, and the lesson is durable across unrelated sessions, behavioral rather than informational, broader than the file that produced it, and short enough to load often. Promotion requires explicit user approval before running `tattoo-add`.

## How agents invoke the CLI

The CLI is usually not typed by hand during normal agent work. Map natural-language commands into `AGENTS.md`, `CLAUDE.md`, or your agent runner's instruction file.

Common mappings:

```text
"load memory"
  -> load tattoos at startup, then run `memento-tattoo --root <memento_root> load --project <project_dir> --query "<task situation>"`

"remember this"
  -> run `memento-tattoo --root <memento_root> note-add --sess <sess_id> --kind correction "<lesson>"`

"save work"
  -> scan the session, reserve a session id, then call `session-add`, `project-edit`, `note-add`, and optionally propose `tattoo-add`

"check memory"
  -> run `memento-tattoo --root <memento_root> doctor --project <project_dir>`
```

If your agent runner supports hooks, hooks can call the same CLI commands: session start (`load`), long-running checkpoints (`session-add` or `project-edit`), post-commit summaries (`project-edit`), session end (the save-work judgment pass), and periodic maintenance (`garden` and `doctor`). Hooks should not blindly promote tattoos; promotion still needs agent judgment and explicit user approval.

## Failure loop example

The basic example shows the loop this project is designed for:

1. An agent claims a code change is complete without running the proof command.
2. The user correction is captured as a note in [examples/basic/memento/notes.md](examples/basic/memento/notes.md).
3. The retention log records that an existing verification lesson was repaired in [examples/basic/memento/retention_log.jsonl](examples/basic/memento/retention_log.jsonl).
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
  registry.md
  sessions/
    sess_abcd.md
    index.md
    index-recent.md
    archive/
  _queue/
  .memento.lock
  .reserved_ids
```

- `project/memory.md`: adjacent project action journal: key decisions, state, and work performed.
- `memento/notes.md`: provisional lessons and corrections.
- `memento/notes_archive.md`: older note blocks rotated out of the hot file; still read during recall.
- `memento/tattoos.md`: promoted lessons that should be broadly reusable.
- `memento/retention_log.jsonl`: append-only record of checked retrieval decisions.
- `memento/registry.md`: optional compact index of project summaries.
- `memento/sessions/`: per-session save records and generated indexes; `archive/` holds rotated-out session files (still counted for ID-collision safety).
- `memento/_queue/`: durable registry deltas waiting for drain.
- `memento/.memento.lock`: advisory lock for short write operations.
- `memento/.reserved_ids`: short-lived session-ID reservations so parallel agents do not collide before a session file is written.

## Out of scope

This reference implementation does not include vector search, embeddings, a database, an MCP server, auto-capture hooks, hosted sync, transcript storage, a generic personal memory system, benchmark claims, or migration tooling from any private setup.

## Docs

- [Idea file](IDEA.md)
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
.venv/bin/python scripts/export_public.py .tmp/public-export
```

Publish from the exported tree.
