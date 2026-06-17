# memento-tattoo

`memento-tattoo` is a file-based memory framework for LLM agents.

This memory system is modeled after Christopher Nolan's *Memento*: Leonard Shelby has memory up to a fixed point in time, then relies on external systems for everything after it. Notes, Polaroids, and tattoos become his post-cutoff memory.

LLMs have a similar shape: training data gives them a cutoff, and the rest has to arrive through external memory loaded into context. Notes capture details, but only help when he can find the right one. Polaroids preserve compact context, but captions can be incomplete. Tattoos get privileged surface area because they are the reminders he cannot afford to miss.

`memento-tattoo` applies that model to LLM agents. Project `memory.md` files are the Polaroids: context attached to the thing being worked on. Notes are searchable lessons from prior sessions. Tattoos are the scarce rules that deserve repeated attention in a limited context window.

Early reference implementation. Install from source; not published to PyPI yet.

## What it solves

Most agent memory systems start by asking how much context can be recalled. `memento-tattoo` asks a narrower question: what correction would change the agent's next action?

The mapping is deliberate:

- Notes are cheap to write, but fail silently when the right one does not surface.
- Project memory is attached to the thing being worked on, like a labeled snapshot.
- Tattoos have limited surface area, like an agent's limited context window.
- The retention loop checks whether the right lesson appeared when it was needed.

The first release is intentionally small:

- plain Markdown files for notes, project context, and promoted lessons
- adjacent project `memory.md` action journals
- append-only JSONL retention log
- checked retrieval before adding correction/reflection notes
- read-only gardening digest
- simple doctor checks
- local CLI, no service dependency

## Design bets

- Memory should be plain text you can inspect, repair, and delete.
- Project memory belongs next to the project, not hidden inside an agent database.
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
.venv/bin/memento-tattoo --root examples/basic/memento load --project examples/basic/project --query "sanitize public release"
.venv/bin/memento-tattoo --root examples/basic/memento garden
```

Create a new root:

```bash
mkdir -p .tmp/demo-project .tmp/demo-memento

project_state=$(cat <<'EOF'
- Situation: publishing docs
- Note: verify the local package from the built artifact before sharing it.
EOF
)

.venv/bin/memento-tattoo --root .tmp/demo-memento project-edit \
  --project .tmp/demo-project \
  --sess sess_demo \
  --section "## State" \
  "$project_state"

note_text=$(cat <<'EOF'
Situation: publishing docs
Note: scan examples for private names, secret values, and local paths before publishing.
aliases: public, sanitize, release
EOF
)

.venv/bin/memento-tattoo --root .tmp/demo-memento note-add --sess sess_demo --kind seed "$note_text"

.venv/bin/memento-tattoo --root .tmp/demo-memento tattoo-add --sess sess_demo "Before sharing a package, prove it works from the built artifact in a clean workspace."
.venv/bin/memento-tattoo --root .tmp/demo-memento doctor --project .tmp/demo-project
.venv/bin/memento-tattoo --root .tmp/demo-memento load --project .tmp/demo-project --query "sanitize release"
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

This first release does not include vector search, embeddings, a database, an MCP server, auto-capture hooks, hosted sync, benchmark claims, or migration tooling from any private setup.

## Docs

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

The package is structured for PyPI publication, but this first release is source-installable from GitHub only.
