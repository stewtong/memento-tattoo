<!-- register: operator guide | reader: memory users and agent authors | consumed: task reference -->

# Agent memory instructions

Use this template to add a lightweight correction-retention loop to a repo. Adjust paths to match the local project.

Choose plain-file mode or CLI mode. In plain-file mode, search and edit the adopted files directly, coordinate one writer at a time, and read back each change. In CLI mode, install `memento-tattoo` and use its commands with the configured memory root. Sessions, generated indexes, registry queues, and automation are optional; leave omitted surfaces out of the local instructions.

## Memory surfaces

- `memory.md`: project-local state, decisions, and work history that should survive across sessions.
- `memento/notes.md`: provisional lessons, usually from corrections or reflections.
- `memento/tattoos.md`: scarce promoted lessons that should change behavior across broad task classes.
- `memento/retention_log.jsonl`: checked-retrieval history with separately attributed author observations.
- `memento/sessions/`: optional per-session save records and, with the CLI, generated indexes.
- `memento/sessions/archive/`: optional archived session records that remain readable.
- `memento/registry.md`: optional compact project registry updated through `memento/_queue/`.

## Startup loading

1. Read this instruction file.
2. Load `memento/tattoos.md` at startup when it exists.
3. Read `memory.md` when the task is about this project.
4. Search for relevant lessons before loading notes. In plain-file mode, search both `memento/notes.md` and `memento/notes_archive.md` when present, using situation, lesson, and alias terms. In CLI mode, use `memento-tattoo load`, which ranks matches from both stores.
5. Load only the matching lessons that could change the next action.

## Correction handling

When the user corrects the agent:

1. Identify the situation.
2. Search existing notes and tattoos for a lesson that should have applied.
3. Repair an existing covering note or add a note containing:
   - `Situation:`
   - `Note:`
   - `aliases:`
   - optional `review_after:`
4. In plain-file mode, save the note directly and append one JSON object to the adopted retention log for the judgment. Include timestamp, session or source reference, note ID, decision, and `decision_source: "author"`; name a covering note when applicable. Read back both artifacts. For a new note in CLI mode, use `memento-tattoo note-add` for a correction or reflection and let it append the event. Do not append a second event by hand.

Use these retention decisions:

- `new`: no existing lesson covered the situation.
- `related`: automatic retrieval found a possible covering lesson.
- `existing-missed`: the author recorded a missed lesson.
- `applied`: the author recorded useful application.
- `overapplied`: the author recorded harmful or unnecessary application.

For an existing note, the CLI has no in-place editor or standalone observation command. Coordinate a pause in other writers, edit the block in whichever note store holds it, preserve its original ID, and add the amendment date and session reference. Append one author observation to the hot retention log with a unique `event_id`, timestamp, amendment session, existing `note_id`, `cover_note_id`, decision, and `decision_source: "author"`. Read back both changes and retrieve the amended note to check its trigger. Do not use `note-add` to create a duplicate for this repair.

## Session-end judgment

When the user says "save work", "save memory", "remember this session", or a similar local command, do a judgment pass before writing anything.

Scan the session and decide:

- what belongs in the session record
- whether project state changed enough to update `memory.md`
- whether a correction or reflection should become a note
- whether an existing note should be strengthened instead of duplicated
- whether there is a tattoo candidate worth proposing

Use this test:

```text
What from this session should change a future action?
```

Do not dump the transcript. Most sessions should update changed project memory and, if adopted, a session record, but produce no new note.

## Multi-agent writes

Plain Markdown works best for one agent at a time, or for teams that already coordinate writes.

If using the `memento-tattoo` CLI or a compatible implementation:

Set an agent identity before writing:

```bash
export MEMENTO_AGENT=codex
```

Use `new-id` for every save session. Do not invent session IDs by hand.

Use `save-commit` when writing several memory surfaces from one session. It writes through the same locked commands and verifies by artifact.

For correction or reflection notes, pass retention judgment fields to `note-add` or `save-commit` when the agent has better context than the retrieval classifier. Seed and pattern notes do not log retention events and reject explicit retention judgments:

- `decision`: `new`, `related`, `existing-missed`, `applied`, or `overapplied`
- `covered_note_id`: existing note id that should have applied

Use `registry-queue` for shared project summary updates, then run `drain`. If a drain cannot acquire the local lock, leave the queued delta in place for a later drain.

Copy the exact inspected registry entry into `registry_delta.expected_line` in a save spec, or pass `registry-queue --expected-line`. An empty string means the entry was absent. A stale draft fails and requires rereading and reconciliation. Older callers that omit this field remain unguarded. Preserve applied receipts, including their archive, for retries.

Use `project-edit --append` for accumulating project memory sections such as worklogs. Use `project-edit --replace` when intentionally rewriting a current-state snapshot such as `## State`. Plain `project-edit` runs in guarded auto mode and should fail rather than silently drop existing delta markers.

## When to write notes

Write a note when:

- the user corrects behavior that could recur
- a task reveals a reusable operating lesson
- an existing lesson needs clearer aliases or a sharper trigger

Do not write notes for:

- raw transcript dumps
- one-off facts that belong in `memory.md`
- private project facts that would be unsafe as global lessons
- vague preferences that do not change a future action

## When to promote tattoos

A tattoo is not a good tip, a summary, or a project fact. It is a scarce operating lesson intended to be visible before broad classes of future action.

Before proposing one, ask:

```text
If this had been loaded at the beginning of the session, would it have dramatically improved the course of action?
```

Propose a tattoo only when the answer is yes and the lesson is:

- supported by observed recurrence
- durable across unrelated future sessions
- behavioral, not merely informational
- broader than the project or file that produced it
- short enough to load often
- written as a declarative principle or compact rule

Keep tattoos scarce. If everything is promoted, nothing is visible.

Do not write a tattoo until the user explicitly approves the proposed wording. First surface the candidate and the reason it passes the bar.

If the user rejects the candidate, retain any useful lesson as an ordinary note and do not keep it in the pending candidate cohort. If the user takes no action, park the candidate in a durable non-tattoo surface for later review. Silence is never approval. A parked candidate is retrievable evidence, not always-loaded instruction, and has no promotion status.

These promotion requirements apply in both adoption modes. The package's authoring standards also cover merge review, note checks, and provenance.

## When to update project memory

Update `memory.md` when the project state changes:

- durable decisions
- current status
- work performed
- constraints a future agent should not rediscover

Keep project facts in project memory. Do not promote them into tattoos unless they become a general operating lesson.

Keep a short `## Current state` section beside project history. In plain-file mode, read that section and search the adopted note stores for lessons matching the action. In CLI mode, run `memento-tattoo load --query "<situation and action>" --project <directory>`. Routine saves update changed state; CLI saves invoke the driver once. Broader maintenance follows the local cadence.

## Minimal file formats

Use this note shape:

```markdown
<!-- delta:sess_example.note.shortid agent=codex ts=2026-06-17T18:24:58Z -->
Situation: publishing a public repo
Note: scan examples for private names, secret values, and local paths before publishing.
aliases: oss, public, sanitize, release
review_after: 2026-12-31
```

Use this tattoo shape:

```markdown
<!-- delta:sess_example.tattoo.shortid agent=codex ts=2026-06-17T18:24:58Z -->
- Before sharing a package, prove it works from the built artifact in a clean workspace.
```

Use one JSON object per line in `retention_log.jsonl`.

## Archive and maintenance controls

When notes rotate, search `notes.md` and `notes_archive.md` together. Keep alias coverage visible as `aliased/total` for hot and archived stores separately. Review low coverage and repair aliases deliberately; never invent aliases automatically.

Treat 25 tattoos, 7,168 bytes of tattoo text, 300 characters per tattoo, and 60 percent archived-note alias coverage as starting recommendations. Adapt or disable a warning for the local context while retaining the measurement. Tattoo thresholds trigger keep, demote, merge, or cut review and never authorize automatic removal.

If sessions are retained, keep IDs stable in hot and archived stores. Before archiving, choose the age policy, preview exact source and destination paths, check collisions, preserve content, and keep archived sessions in lookup and rebuild. Do not archive concurrently with another writer unless the implementation serializes writes with a lock or equivalent coordination.

## Interpret evidence within its scope

Automatic classification records `new` or `related`. Author judgments record their source separately. Historical events without that provenance remain unverified classifications; gardening retains their count but excludes them from observed-miss promotion counts. Citation counts establish mentions. Behavioral effectiveness requires evidence from the task. Sparse citations alone do not justify removing a rare, consequential safeguard.

Use the named project's current state together with transferable lessons matching the action. Expand the search when evidence conflicts, a needed source is absent, or a consequential decision needs more support. A bounded result cannot establish absence. A newer summary does not supersede an authoritative decision merely by being newer. Preserve useful successful approaches as well as corrections.

A tattoo states when its action helps and preserves necessary exceptions. Its wording must not turn a local correction into a universal restriction. Review scope, overlap, and the cost of unnecessary application before proposing it. Existing approval and candidate-parking rules still apply.
