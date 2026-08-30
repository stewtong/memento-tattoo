<!-- register: public reference | reader: coding-agent users | consumed: copied as a standalone file -->

# Memento correction-retention pattern

This file is the canonical, implementation-neutral contract for giving coding agents a lightweight correction-retention system.

Paste it into your coding agent and ask it to adapt the pattern to your local repo, tools, and workflow. The point is not to prescribe one implementation. The point is to give the agent a small operating pattern for remembering lessons at the moment they should change behavior.

This document is inspired by the idea-file publication style of Andrej Karpathy's [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). It is not affiliated with, endorsed by, or an implementation of `llm-wiki`. It applies the single-file pattern to a different problem: helping coding agents retain corrected lessons.

For a working reference implementation of this correction-retention pattern, see the `memento-tattoo` repo.

## Adoption modes and contract boundary

Use either of these supported modes:

- Adapt this protocol with plain files and repo-local instructions.
- Install the reference CLI for deterministic writes and diagnostics.

Plain Markdown preserves the workflow and leaves coordination to the local adaptation. It does not by itself provide locking, collision-safe IDs, idempotent writes, atomic moves, complete-batch validation, or deterministic doctor checks. An adaptation must declare which optional surfaces it implements, including sessions, archives, and automated diagnostics. Omitted features must remain omitted in its instructions.

This file is the product contract. A disagreement with another product document is release-blocking drift. Historical plans and internal memory are evidence, not product authority.

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

## Agent judgment

The agent is the judge. The files and CLI do not decide what matters; they preserve what the agent decides after reviewing the work.

At the end of a session, the agent should scan what happened and decide:

- what project state changed enough to update `memory.md`
- whether a correction or reflection should become a note
- whether an existing note should be repaired instead of duplicated
- whether a lesson is strong enough to propose as a tattoo

Most sessions should not produce a tattoo. Many sessions should not produce a note. The healthy default is to write only the material that should change a future action.

At session end, surface the strongest tattoo candidate for immediate approval. Promote it only when the user explicitly approves the proposed wording. If the user rejects it, retain any useful lesson as an ordinary note. If the user takes no action, park the candidate in a durable non-tattoo surface for later review. Silence is never approval.

## Minimal local layout

Start with plain files:

```text
project/
  memory.md

memento/
  notes.md
  tattoos.md
  retention_log.jsonl
  notes_archive.md          # optional when notes rotate
  sessions/                 # optional session records
    archive/                # optional archived session records
```

Use `project/memory.md` for state tied to one repo or project.

Use `memento/notes.md` for provisional lessons. A note should include the situation, the lesson, and a few aliases that might help retrieval.

Use `memento/tattoos.md` for promoted lessons. A tattoo should be scarce, short enough to load often, and broad enough to apply across tasks.

Use `memento/retention_log.jsonl` as an append-only record of checked retrieval decisions.

Keep the four-file layout when it is enough. Add the archive and session surfaces only when the local workflow needs them.

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

When a new note relates to an existing note or tattoo, link to it by id instead of restating its lesson. Reference the prior note rather than duplicating it.

If a lesson recurs across different situations, propose promoting it to a tattoo.

Do not promote a tattoo without explicit user approval of its wording. If the user takes no action, park the candidate outside the tattoo set for later review.

At startup, load tattoos when they exist. Before starting a task with a recognizable situation name, search notes and project memory for that situation, then load only the matches that could change the next action.

Keep project memory beside the project. Put project-specific state close to the work it explains.

Treat retention logs as append-only.
```

## Promotion rules

Promote a note to a tattoo only when it passes a higher bar:

- It has recurred.
- It applies beyond one narrow file or one unusual moment.
- It would have changed future behavior if loaded earlier.
- It would have dramatically improved the course of action if loaded at the beginning of the session.
- It can be written as a declarative principle or compact rule.

Do not promote everything. Tattoos are valuable because the layer refuses to become a dump.

Use these as starting review recommendations, then adapt them to the workspace: review the tattoo set when it exceeds 25 tattoos, 7,168 bytes of tattoo text, or 300 characters for any one tattoo. Crossing a threshold starts a keep, demote, merge, or cut review. It never authorizes automatic removal.

Record the recommendation in use. Keep the count and byte measurements visible even when a local warning is disabled.

## Retrieval checks

When adding a correction or reflection, classify the retrieval result:

- `new`: no existing lesson covered the situation.
- `existing-missed`: a relevant lesson existed but did not prevent the mistake.

This makes repeated correction visible. A repeat miss is not just another note. It is evidence that the lesson trigger or loading rule needs repair.

Repairing an existing note is an action after classification, not another required retention outcome. A local implementation may record false-positive analysis as separate diagnostic metadata, but it should not mix that metadata into the two-outcome retention-health denominator.

The retention log measures write-time classification hygiene. It does not prove that an agent loaded, applied, or followed a lesson, or that the corrected behavior stopped recurring.

## Guardrails

- Keep tattoos scarce.
- Review tattoos periodically and demote or cut ones that no longer change behavior. Scarcity is maintained over time, not just at promotion.
- Keep project memory beside the project.
- Keep logs append-only.
- Prefer plain text that humans can inspect and repair.
- If archived notes are used, search hot and archived notes together. Report alias coverage separately for each store; 60 percent archived coverage is a starting review recommendation, not a universal requirement.
- Do not claim benchmark wins without benchmark evidence.
- Do not turn this into a transcript archive.
- Do not promote private, project-specific facts into global tattoos.

## Optional archive and session maintenance

When rotating notes, retrieval searches both `notes.md` and `notes_archive.md`. Maintenance reports alias coverage as `aliased/total` for the hot and archived stores separately. It may propose alias repairs and never invents or adds aliases automatically.

When retaining session records, keep stable IDs across `sessions/` and `sessions/archive/`. The operator chooses the age policy. Before a move, show the exact source and destination paths, check every destination and ID collision, then preserve the file content while moving it. Lookup and rebuild include both stores.

Plain-file adaptations should not archive sessions while another writer may be active unless they provide a lock or another method that serializes writes.

A parked tattoo candidate is retrievable evidence, not always-loaded instruction, and has no promotion status. An adaptation may park it in a session marker or tagged note until it defines a durable candidate store.

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
3. Promotion rules that propose the strongest candidate at session end, require explicit approval, and park the candidate outside the tattoo set when no action is taken.
4. Retrieval checks before writing correction or reflection notes.
5. Guardrails that keep project facts local and tattoos scarce, with locally adaptable review thresholds.
6. A report naming the automated guarantees, manual review steps, and omitted optional surfaces.

Verify the result through the interface the user will invoke, whether that is repo-local instructions, a script, or a CLI.

Do not build a database, vector search, hosted sync, or MCP server unless the current repo clearly needs it.
```
