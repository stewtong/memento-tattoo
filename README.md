# memento-tattoo

`memento-tattoo` is a correction-retention loop that helps coding agents stop repeating corrected mistakes across sessions.

If you want to understand or adapt the pattern, start with [IDEA.md](IDEA.md).
If you want a working local CLI, install from source.

`memento-tattoo` is modeled after Christopher Nolan's *Memento*.

In the movie, Leonard cannot form new long-term memories, so everything important after his cutoff has to be externalized. LLMs have a similar shape: their training data is fixed, and only the context loaded into the current session can affect the next action.

In *Memento*, Leonard uses a tiered memory system: notes for quick observations, Polaroids beside the people and places they explain, and tattoos for the few facts important enough to survive every reset.

`memento-tattoo` adapts that pattern for coding agents:

- notes are cheap lesson captures from corrections and reflections
- project `memory.md` files are the Polaroids beside the work
- tattoos are scarce promoted lessons that should be loaded before broad classes of action

The point is not to remember everything. The point is to preserve the lessons that should change the next action.

Generic memory stores context. `memento-tattoo` stores corrections that should alter future behavior.

This repo is a reference implementation. Install from source.

## What it solves

Most agent memory systems start by asking how much context can be recalled. `memento-tattoo` asks a narrower question: what correction would change the agent's next action?

That makes memory a lightweight continuous-learning loop. The model weights do not change; the working system does. Corrections become notes, repeated lessons can become tattoos, and the retention log checks whether the right lesson showed up when it mattered.

This reference implementation keeps the surface area narrow:

- plain Markdown files for notes, project memory, tattoos, and retention logs
- checked writes and ranked recall
- doctor checks and read-only gardening
- optional local coordination for parallel sessions
- local CLI, no service dependency

## Try the pattern without installing

You do not need the CLI to try the idea. Copy [templates/AGENTS.md](templates/AGENTS.md) into a repo, adapt the paths, and start with three plain files:

```text
project/
  memory.md

memento/
  notes.md
  tattoos.md
  retention_log.jsonl
```

That plain-Markdown version is enough for a single agent, a lightly coordinated team, or a repo-local convention. It does not provide real concurrent-write protection.

The practical layers look like this:

```text
AGENTS.md / CLAUDE.md  = how the agent should behave
project/memory.md     = what is going on here
memento/notes.md      = what the work taught us
memento/tattoos.md    = what must not be forgotten
retention_log.jsonl   = whether the lesson surfaced when it mattered
```

Modern coding agents already have memory surfaces: `AGENTS.md`, `CLAUDE.md`, rules files, auto-memory folders, hooks, and project docs. `memento-tattoo` is not trying to replace those. It gives them a correction-retention loop: capture the lesson, check whether it should already have fired, and keep the scarce operating principles visible before future action.

Tattoo lessons are intended to be loaded at startup. Project `memory.md` and `memento/notes.md` should be searched first, then loaded only when they match the current task.

Plain Markdown is enough to try the pattern. The CLI adds checked writes, ranked recall, doctor checks, gardening, and optional local coordination for parallel sessions.

## The agent is the judge

`memento-tattoo` does not decide what matters by itself. The CLI writes, checks, recalls, and coordinates files. The agent decides what deserves to be written.

At the end of a session, or when the user says something like "save work", the agent should scan the work just completed and decide:

- what belongs in the session record
- whether project state changed enough to update `memory.md`
- whether a correction or reflection should become a note
- whether an existing note should be repaired instead of duplicated
- whether there is a tattoo candidate worth proposing

This is a judgment pass, not a transcript dump. The useful question is:

```text
What from this session should change a future action?
```

Write to project `memory.md` when the project state changed: files changed, decisions were made, constraints were discovered, current status changed, or a future agent should not rediscover the same context. Project memory should summarize state beside the work it explains, not become a transcript log.

Project memory can be replaced for current state or appended for worklog-style sections; the CLI guards against silent overwrites.

Write to `notes.md` when the session produced a reusable lesson: a correction that could recur, a mistake pattern the agent noticed, an existing lesson that needs better aliases, or an operating lesson that would change behavior in a similar future situation.

A tattoo is not a good tip, a summary, or a project fact. It is a scarce operating lesson intended to be visible before broad classes of future action.

Before proposing one, ask:

```text
If this had been loaded at the beginning of the session, would it have dramatically improved the course of action?
```

Propose a tattoo only when the answer is yes and the lesson is durable across unrelated future sessions, behavioral rather than merely informational, broader than the project or file that produced it, short enough to load often, and written as a declarative principle or compact rule.

Tattoo promotion requires explicit user approval before running `tattoo-add`. Different agents may need different local wording for this bar; some over-promote broad rules, while others under-promote unless recurrence is obvious.

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

If your agent runner supports hooks, hooks can call the same CLI commands. Useful hook points include session start (`load`), long-running checkpoints (`session-add` or `project-edit`), post-commit project summaries (`project-edit`), session end (the save-work judgment pass), and periodic maintenance (`garden` and `doctor`).

Hooks can call the CLI, but hooks should not blindly promote tattoos. Promotion still needs agent judgment and explicit user approval.

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
- Promotion should be scarce. The tattoo layer is valuable because it refuses to be everything.

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
  tattoos.md
  retention_log.jsonl
  registry.md
  sessions/
    sess_abcd.md
    index.md
    index-recent.md
  _queue/
  .memento.lock
```

- `project/memory.md`: adjacent project action journal: key decisions, state, and work performed.
- `memento/notes.md`: provisional lessons and corrections.
- `memento/tattoos.md`: promoted lessons that should be broadly reusable.
- `memento/retention_log.jsonl`: append-only record of checked retrieval decisions.
- `memento/registry.md`: optional compact index of project summaries.
- `memento/sessions/`: per-session save records and generated indexes.
- `memento/_queue/`: durable registry deltas waiting for drain.
- `memento/.memento.lock`: advisory lock for short write operations.

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

This development checkout can contain local planning, research, and memory artifacts. To create the public GitHub surface, export a clean tree:

```bash
.venv/bin/python scripts/export_public.py .tmp/public-export
```

Use the exported tree for public GitHub pushes. Do not publish this development checkout directly.

This reference implementation is source-installable from GitHub.
