# Agent memory instructions

Use this template to add a lightweight correction-retention loop to a repo. Adjust paths to match the local project.

## Memory surfaces

- `memory.md`: project-local state, decisions, and work history that should survive across sessions.
- `memento/notes.md`: provisional lessons, usually from corrections or reflections.
- `memento/tattoos.md`: scarce promoted lessons that should change behavior across broad task classes.
- `memento/retention_log.jsonl`: append-only record of checked retrieval decisions.
- `memento/sessions/`: per-session save records and generated indexes.
- `memento/registry.md`: optional compact project registry updated through `memento/_queue/`.

## Startup loading

1. Read this instruction file.
2. Load `memento/tattoos.md` at startup when it exists.
3. Read `memory.md` when the task is about this project.
4. Do not automatically load all of `memento/notes.md`; search it first with `memento-tattoo load`, grep, or another local retrieval step.
5. Load only the matching lessons that could change the next action.

## Correction handling

When the user corrects the agent:

1. Identify the situation.
2. Search existing notes and tattoos for a lesson that should have applied.
3. Write a note to `memento/notes.md` with:
   - `Situation:`
   - `Note:`
   - `aliases:`
   - optional `review_after:`
4. Append one retention event to `memento/retention_log.jsonl`.

Use these retention decisions:

- `new`: no existing lesson covered the situation.
- `existing-missed`: a relevant lesson existed but did not affect the action.
- `existing-repaired`: a relevant lesson existed and was improved.
- `false-positive`: retrieval suggested a lesson that should not count.

## Session-end judgment

When the user says "save work", "save memory", "remember this session", or a similar local command, do a judgment pass before writing anything.

Scan the session and decide:

- what belongs in the session record
- whether project state changed enough to update `memory.md`
- whether a correction or reflection should become a note
- whether an existing note should be repaired instead of duplicated
- whether there is a tattoo candidate worth proposing

Use this test:

```text
What from this session should change a future action?
```

Do not dump the transcript. Most sessions should produce project memory and a session record, but no new note.

## Multi-agent writes

Plain Markdown works best for one agent at a time, or for teams that already coordinate writes.

If using the `memento-tattoo` CLI or a compatible implementation:

Set an agent identity before writing:

```bash
export MEMENTO_AGENT=codex
```

Use `new-id` for every save session. Do not invent session IDs by hand.

Use `save-commit` when writing several memory surfaces from one session. It writes through the same locked commands and verifies by artifact.

When the agent has better context than the retrieval classifier, pass retention judgment fields to `note-add` or `save-commit`:

- `decision`: `new`, `existing-missed`, `existing-repaired`, or `false-positive`
- `repair`: short explanation of what was repaired or why the judgment changed
- `covered_note_id`: existing note id that should have applied or was repaired

Use `registry-queue` for shared project summary updates, then run `drain`. If a drain cannot acquire the local lock, leave the queued delta in place for a later drain.

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

- durable across unrelated future sessions
- behavioral, not merely informational
- broader than the project or file that produced it
- short enough to load often
- written as a declarative principle or compact rule

Keep tattoos scarce. If everything is promoted, nothing is visible.

Do not write a tattoo until the user explicitly approves the proposed wording. First surface the candidate and the reason it passes the bar.

## When to update project memory

Update `memory.md` when the project state changes:

- durable decisions
- current status
- work performed
- constraints a future agent should not rediscover

Keep project facts in project memory. Do not promote them into tattoos unless they become a general operating lesson.

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
