# memento-tattoo

`memento-tattoo` is a correction-retention loop that helps coding agents stop repeating corrected mistakes across sessions.

If you want to understand or adapt the pattern, start with [IDEA.md](IDEA.md).
If you want a working local CLI, install this repo.

`memento-tattoo` is modeled after Christopher Nolan's *Memento*.

In the movie, Leonard cannot form new long-term memories, so everything important after his cutoff has to be externalized. LLMs have a similar shape: their training data is fixed, and only the context loaded into the current session can affect the next action.

In *Memento*, Leonard uses a tiered memory system: notes for quick observations, Polaroids beside the people and places they explain, and tattoos for the few facts important enough to survive every reset.

`memento-tattoo` adapts that pattern for coding agents:

- notes are cheap lesson captures from corrections and reflections
- project `memory.md` files are the Polaroids beside the work
- tattoos are scarce promoted lessons that should be loaded before broad classes of action

The point is not to remember everything. The point is to preserve the lessons that should change the next action.

This repo is an early reference implementation. Install from source.

## What it solves

Most agent memory systems start by asking how much context can be recalled. `memento-tattoo` asks a narrower question: what correction would change the agent's next action?

That makes memory a lightweight continuous-learning loop. The model weights do not change; the working system does. Corrections become notes, repeated lessons can become tattoos, and the retention log checks whether the right lesson showed up when it mattered.

The first release keeps the surface area narrow:

- plain Markdown files for notes, project context, and promoted lessons
- adjacent project `memory.md` action journals
- append-only JSONL retention log
- checked retrieval before adding correction/reflection notes
- read-only gardening digest
- simple doctor checks
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

The CLI in this repo is the reference implementation of that pattern. It is useful when you want checked writes, ranked recall, doctor checks, and a read-only gardening digest.

## Failure loop example

The basic example shows the loop this project is designed for:

1. An agent claims a code change is complete without running the proof command.
2. The user correction is captured as a note in [examples/basic/memento/notes.md](examples/basic/memento/notes.md).
3. The retention log records that an existing verification lesson was repaired in [examples/basic/memento/retention_log.jsonl](examples/basic/memento/retention_log.jsonl).
4. A broader completion rule is promoted to [examples/basic/memento/tattoos.md](examples/basic/memento/tattoos.md).
5. A later task can load the tattoo before claiming completion.

See [examples/basic/README.md](examples/basic/README.md) for the concrete walkthrough.

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

.venv/bin/memento-tattoo --root .tmp/demo-memento tattoo-add --sess sess_demo "Before claiming work is complete, run the command that proves it and read the output."
.venv/bin/memento-tattoo --root .tmp/demo-memento doctor --project .tmp/demo-project
.venv/bin/memento-tattoo --root .tmp/demo-memento load --project .tmp/demo-project --query "claiming complete verification"
```

## CLI

```text
memento-tattoo --root <path> note-add --sess <sess_id> [--kind correction|reflection|seed] <text>
memento-tattoo --root <path> tattoo-add --sess <sess_id> <text>
memento-tattoo --root <path> project-edit --project <project_dir> --sess <sess_id> [--section "## State"] [--flow-start ISO] <text>
memento-tattoo --root <path> load [--project <project_dir>]... --query <query> [--limit N]
memento-tattoo --root <path> garden [--today YYYY-MM-DD] [--promote-threshold N]
memento-tattoo --root <path> doctor [--project <project_dir>]...
```

`seed` notes are imported without retention logging. `correction` and `reflection` notes run checked retrieval first and append one retention event only when the note write is new.

## File layout

A project and memento root use adjacent files:

```text
project/
  memory.md

memento/
  notes.md
  tattoos.md
  retention_log.jsonl
  .memento.lock
```

- `project/memory.md`: adjacent project action journal: key decisions, state, and work performed.
- `memento/notes.md`: provisional lessons and corrections.
- `memento/tattoos.md`: promoted lessons that should be broadly reusable.
- `memento/retention_log.jsonl`: append-only record of checked retrieval decisions.
- `memento/.memento.lock`: advisory lock for short write operations.

## Out of scope

This first release does not include vector search, embeddings, a database, an MCP server, auto-capture hooks, hosted sync, transcript storage, a generic personal memory system, benchmark claims, or migration tooling from any private setup.

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

This first release is source-installable from GitHub.
