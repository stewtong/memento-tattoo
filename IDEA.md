# Memento-tattoo idea file

This is an idea file for giving coding agents a lightweight correction-retention system.

Paste it into your coding agent and ask it to adapt the pattern to your local repo, tools, and workflow. The point is not to prescribe one implementation. The point is to give the agent a small operating pattern for remembering lessons at the moment they should change behavior.

This document is inspired by the idea-file publication style of Andrej Karpathy's [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). It is not affiliated with, endorsed by, or an implementation of `llm-wiki`. It applies the idea-file format to a different problem: helping coding agents retain corrected lessons.

For a working reference implementation of this correction-retention pattern, see the `memento-tattoo` repo.

## Core metaphor

The metaphor comes from Christopher Nolan's *Memento*.

An agent has a cutoff: what the model already knows, plus whatever is loaded into context right now. Everything after that has to be externalized.

Use three memory surfaces:

- Notes: cheap lesson captures, usually from corrections or reflections.
- Polaroids: project-local memory that lives beside the thing being worked on.
- Tattoos: scarce, promoted lessons that should be visible before broad classes of action.

The useful constraint is scarcity. Not every note deserves to become a tattoo. If everything is promoted, nothing is visible.

## Problem

Agents often repeat corrected mistakes.

Transcript memory is not enough. A chat log can contain the correction and still fail to surface the lesson when the agent is about to repeat the behavior. The failure is not only storage. It is retrieval at action time.

The question this pattern asks is narrow:

```text
What correction would have changed the agent's next action?
```

## Design bet

Correction memory matters more than transcript memory.

The agent does not need a perfect archive of every event. It needs a small, inspectable loop:

1. Capture the lesson when a correction happens.
2. Check whether an existing lesson should already have fired.
3. Log the result.
4. Promote only the lessons that prove durable and broad.

The model weights do not change. The working system does.

## Minimal local layout

Start with plain files:

```text
project/
  memory.md

memento/
  notes.md
  tattoos.md
  retention_log.jsonl
```

Use `project/memory.md` for state tied to one repo or project.

Use `memento/notes.md` for provisional lessons. A note should include the situation, the lesson, and a few aliases that might help retrieval.

Use `memento/tattoos.md` for promoted lessons. A tattoo should be short enough to load often and broad enough to apply across tasks.

Use `memento/retention_log.jsonl` as an append-only record of checked retrieval decisions.

## Concurrency note

The plain-Markdown pattern is intentionally easy to copy, but it is not a complete multi-agent coordination system by itself. It works best for one agent at a time, or for teams that are already coordinating writes.

If you expect agent swarms, parallel coding sessions, or several tools writing to the same memory root concurrently, add real coordination:

- a lock around short writes
- collision-safe session IDs
- idempotent markers
- append-only or queued writes for shared summaries
- a drain/rebuild step that verifies artifacts on disk

Those coordination pieces are what the `memento-tattoo` CLI implements as the reference version of the pattern.

## Agent instructions

Add instructions like these to your agent config, for example `AGENTS.md`, `CLAUDE.md`, or another repo-local instruction file:

```text
When the user corrects you, write a note that captures:
- the situation
- what went wrong
- the rule going forward
- aliases that would help retrieve the lesson later

Before writing a correction or reflection note, search existing notes for a matching lesson.

If a matching lesson already existed but did not affect your action, log that as an existing-missed retrieval.

If a lesson recurs across different situations, propose promoting it to a tattoo.

Before starting a task with a recognizable situation name, search notes and tattoos for that situation.

Keep project memory beside the project. Put project-specific state close to the work it explains.

Treat retention logs as append-only.
```

## Promotion rules

Promote a note to a tattoo only when it passes a higher bar:

- It has recurred.
- It applies beyond one narrow file or one unusual moment.
- It would have changed future behavior if loaded earlier.
- It can be written as a short imperative.

Do not promote everything. Tattoos are valuable because the layer refuses to become a dump.

## Retrieval checks

When adding a correction or reflection, classify the retrieval result:

- `new`: no existing lesson covered the situation.
- `existing-missed`: a relevant lesson existed but did not prevent the mistake.
- `existing-repaired`: a relevant lesson existed and was improved.
- `false-positive`: retrieval suggested a lesson that should not count.

This makes repeated correction visible. A repeat miss is not just another note. It is evidence that the lesson trigger or loading rule needs repair.

## Guardrails

- Keep tattoos scarce.
- Keep project memory beside the project.
- Keep logs append-only.
- Prefer plain text that humans can inspect and repair.
- Do not claim benchmark wins without benchmark evidence.
- Do not turn this into a transcript archive.
- Do not promote private, project-specific facts into global tattoos.

## Alternate implementation paths

The pattern does not require a specific tool.

You can implement it as:

- pure Markdown plus repo-local agent instructions
- a small local CLI
- an MCP server
- an Obsidian vault
- a repo-local `AGENTS.md` or `CLAUDE.md` convention
- a hosted memory service, if your constraints justify it

`memento-tattoo` is one reference implementation of the pattern as a local CLI.

## Paste this into your agent

```text
I want to add a lightweight correction-retention system to this repo.

Use this pattern:
- Notes are cheap lesson captures.
- Project memory lives beside the project as a local file.
- Tattoos are scarce promoted lessons that should be loaded before broad classes of action.
- A retention log records whether the right lesson showed up when it mattered.

Adapt the pattern to this repo with the smallest useful implementation.

Create or propose:
1. A local file layout for notes, project memory, tattoos, and a retention log.
2. Agent instructions for when to write notes.
3. Promotion rules for tattoos.
4. Retrieval checks before writing correction or reflection notes.
5. Guardrails that keep project facts local and tattoos scarce.

Do not build a database, vector search, hosted sync, or MCP server unless the current repo clearly needs it.
```
