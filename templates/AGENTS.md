# Agent memory instructions

Use this template to add a lightweight correction-retention loop to a repo. Adjust paths to match the local project.

## Memory surfaces

- `memory.md`: project-local state, decisions, and work history that should survive across sessions.
- `memento/notes.md`: provisional lessons, usually from corrections or reflections.
- `memento/tattoos.md`: scarce promoted lessons that should change behavior across broad task classes.
- `memento/retention_log.jsonl`: append-only record of checked retrieval decisions.

## Startup loading

1. Read this instruction file.
2. Read `memory.md` when the task is about this project.
3. When the task has a recognizable situation name, search `memento/notes.md` and `memento/tattoos.md` for that name and close aliases before acting.
4. Load only the lessons that could change the next action.

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

Propose a tattoo only when a note passes this bar:

- it recurred or would have prevented a meaningful mistake
- it applies beyond one file or one unusual moment
- it can be written as a short imperative
- loading it before a future task would change the next action

Keep tattoos scarce. If everything is promoted, nothing is visible.

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
<!-- delta:sess_example.note.shortid -->
Situation: publishing a public repo
Note: scan examples for private names, secret values, and local paths before publishing.
aliases: oss, public, sanitize, release
review_after: 2026-12-31
```

Use this tattoo shape:

```markdown
<!-- delta:sess_example.tattoo.shortid -->
- Before sharing a package, prove it works from the built artifact in a clean workspace.
```

Use one JSON object per line in `retention_log.jsonl`.
