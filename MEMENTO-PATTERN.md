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
  PROTOCOL.md
  notes.md
  tattoos.md
  retention_log.jsonl
  notes_archive.md          # optional when notes rotate
  sessions/                 # optional session records
    archive/                # optional archived session records
```

Use `project/memory.md` for state tied to one repo or project.

Use `memento/PROTOCOL.md` for the agent procedure: correction handling, retrieval, the save judgment pass, record formats and promotion gates. Agents read it when a trigger fires, not every session.

Use `memento/notes.md` for provisional lessons. A note should include the situation, the lesson, and a few aliases that might help retrieval. It may add a `Why:` field of one or two sentences naming the cost or mechanism behind the lesson. `Why:` is recommended, never required: a reason lets a later reader decide whether a new case is covered, and a required field would invite filler.

Use `memento/tattoos.md` for promoted lessons. A tattoo should be scarce, short enough to load often, and broad enough to apply across tasks. Write it as `<action with its trigger>; <reason clause>.` The trigger says when the rule applies; the reason says why, so a reviewer can later ask whether the reason still holds.

Use `memento/retention_log.jsonl` as an append-only record of checked retrieval decisions.

Keep the core layout when it is enough. Add the archive and session surfaces only when the local workflow needs them.

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

Split the instructions in two, because always-loaded text is paid for on every request.

1. A short stub goes in the always-on instruction file, for example `AGENTS.md`, `CLAUDE.md`, or another repo-local rules file. It loads tattoos, points at current project state, and says when to open the protocol:

```text
## Memory (memento)
- At session start, read memento/tattoos.md down to its "## Scoped" heading, or to the end if it has none. Each tattoo is an approved rule that states when it applies and why.
- When working under a directory, read the "## Current state" (or "## State") section of the nearest memory.md, walking up to the repo root.
- Before editing a file, also read the entries under "## Scoped" in memento/tattoos.md whose paths: glob matches it.
- When the user corrects you, when you recognize the situation of a past lesson, or when the user says "save work", read memento/PROTOCOL.md and follow the matching section.
- Add or change a line in memento/tattoos.md only after the user approves its exact wording.
```

The two scoped lines take effect only when `tattoos.md` has a `## Scoped` heading whose entries carry a `paths:` glob. Without that heading, the agent reads the whole file at start, so the stub works unchanged in a repo that never scopes a rule. The reference CLI does not yet parse `paths:`; an agent following the stub matches globs by reading.

2. `memento/PROTOCOL.md` holds the procedure, read on demand. It states each rule as behavior with its reason and covers plain-file mode and CLI mode. It must include:

- When the user corrects the agent, search existing notes and tattoos for a matching lesson before writing, then repair the covering note or write a new one with the situation, the lesson, an optional `Why:`, and aliases.
- If the session shows that a matching lesson existed but was missed, record `existing-missed` explicitly. Automatic similarity alone records `related`.
- When a new note relates to an existing note or tattoo, link to it by id instead of restating its lesson.
- Before a task with a recognizable situation, search notes and project memory for that situation, then load only the matches that could change the next action.
- At "save work", run the judgment pass described under [Agent judgment](#agent-judgment).
- If a lesson recurs across different situations, propose promoting it to a tattoo. Do not promote without explicit user approval of its wording. If the user takes no action, park the candidate outside the tattoo set for later review.
- Keep project memory beside the project, and treat retention logs as append-only.

Adapters for particular harnesses, such as an Agent Skills `SKILL.md`, point to `memento/PROTOCOL.md` and carry no copy of it, so the procedure has one source. The reference CLI's `init` command creates the root files, copies the protocol and prints the stub.

The protocol names tool commands without restating their internals; counting rules, digests and replay receipts belong to the implementation's reference documentation.

## Complete evidence and editorial revisions

Keep a path from a short retrieval result to its complete source, including necessary exceptions and prior revisions. Mark clipped previews. A content-snapshot reference may identify an unmarked legacy record, but must not be described as a durable logical identity. Preserve ordinary notes' original identities when editing them.

Agents may capture working notes and make evidence-backed revisions under the adopted policy, preserving the source, reason and visible prior active content. Revisions must not silently replace an owner decision or turn repeated agent proposals into approved rules. Durable rules and changes to their meaning or scope require explicit owner approval. An editorial change is not evidence that a lesson was applied or missed.

The reference CLI provides `entry-read` for complete source-scoped reads and `note-amend` for guarded ordinary-note revisions. The amendment compares the full current block digest, retains its creation marker and stores prior active content plus provenance in the same atomically replaced Markdown file. History stays out of active recall. An identical immediate retry preserves bytes; stale edits and obsolete retries fail. Plain-file adaptations must supply their own coordination and revision discipline. This contract does not require a database or model-specific memory store.

## Promotion rules

Promote a note to a tattoo only when it passes a higher bar:

- It has recurred.
- It applies beyond one narrow file or one unusual moment.
- It would have changed future behavior if loaded earlier.
- It would have dramatically improved the course of action if loaded at the beginning of the session.
- It can be written as a declarative principle or compact rule, in the shape `<action with its trigger>; <reason clause>.`

A tattoo states when its action helps and preserves necessary exceptions. Its wording must not turn a local correction into a universal restriction. Review scope, overlap, and the cost of unnecessary application before proposing it.

Do not promote everything. Tattoos are valuable because the layer refuses to become a dump.

Use these as starting review recommendations, then adapt them to the workspace: review the tattoo set when it exceeds 25 tattoos, 7,168 bytes of tattoo text, or 300 characters for any one tattoo. Crossing a threshold starts a keep, demote, merge, or cut review. It never authorizes automatic removal.

Record the recommendation in use. Keep the count and byte measurements visible even when a local warning is disabled.

## Retrieval checks

When adding a correction or reflection, classify the retrieval result:

- `new`: no existing lesson covered the situation.
- `related`: automatic retrieval found a possible covering lesson.
- `existing-missed`: the author recorded that a relevant lesson existed but did not prevent the mistake.
- `applied`: the author recorded useful application of a lesson.
- `overapplied`: the author recorded harmful or unnecessary application.

An author-recorded miss warrants review of its cause. Similarity alone does not establish a retrieval failure.

Repairing an existing note is an action after classification, not another required retention outcome. A local implementation may record false-positive analysis as separate diagnostic metadata, but it should not mix that metadata into the two-outcome retention-health denominator.

The retention log measures write-time classification hygiene. It does not prove that an agent loaded, applied, or followed a lesson, or that the corrected behavior stopped recurring.

## Guardrails

- Keep tattoos scarce.
- Review tattoos periodically and demote or cut ones that no longer change behavior. Scarcity is maintained over time, not just at promotion.
- Keep project memory beside the project.
- Keep logs append-only.
- Prefer plain text that humans can inspect and repair.
- Report how many notes carry `Why:` and how many tattoos carry a reason clause, as review signals. A missing reason is never an error, and a coverage warning stays off unless the adaptation turns it on.
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
- A retention log records write-time retrieval classifications and separately attributed author observations of missed, useful, or unnecessary lesson application.

Adapt the pattern to this repo with the smallest useful implementation.

Create or propose:
1. A local file layout for notes, project memory, tattoos, and a retention log.
2. A short always-on instruction block, plus an on-demand protocol file for writing notes, saving work and proposing tattoos.
3. Promotion rules that propose the strongest candidate at session end, require explicit approval, and park the candidate outside the tattoo set when no action is taken.
4. Retrieval checks before writing correction or reflection notes.
5. Guardrails that keep project facts local and tattoos scarce, with locally adaptable review thresholds.
6. A report naming the automated guarantees, manual review steps, and omitted optional surfaces.

Verify the result through the interface the user will invoke, whether that is repo-local instructions, a script, or a CLI.

Do not build a database, vector search, hosted sync, or MCP server unless the current repo clearly needs it.
```

## Evidence scope

Retention counts, citation counts and bounded search results each prove less than they appear to. Automatic classification is not an author judgment, a mention is not an application, and a search that finds nothing does not establish absence. The reference implementation defines these limits in [Concepts: interpret evidence within its scope](docs/concepts.md#interpret-evidence-within-its-scope); an adaptation keeps equivalent limits in its own reporting.

## Retrieve for the action and save the actual changes

Keep a short `## Current state` beside preserved project history. Retrieve that state and lessons about the intended action when they could change the decision. The reference CLI accepts `load --query "<situation and action>" --project <directory>` and includes an explicit current-state excerpt alongside ranked lessons. Scope, source and supersession remain visible. Matching suggests relevance; current user instructions and source evidence determine what applies. Widen a search when missing or conflicting evidence matters, without making retrieval a ritual on every turn.

Routine saves reuse unchanged protocol context, refresh relevant shared state, and call the mechanical driver once. Broader tattoo review and historical housekeeping follow the adaptation's declared maintenance cadence. Deferred maintenance remains visible and must not be reported as completed persistence.

For registry updates in the reference CLI, supply `registry_delta.expected_line` in the save JSON, or `registry-queue --expected-line`, with the exact entry read before drafting; an empty string means the entry was absent. Preflight, queue and drain check the source fingerprint, so a stale draft fails instead of overwriting another writer. Older callers remain compatible but lack this guard. A retry reuses its original receipt. Required session and registry writes still receive artifact checks; optional enrichment never substitutes for them.
