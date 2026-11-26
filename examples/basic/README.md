<!-- register: public example walkthrough | reader: coding-agent users | consumed: read beside the fixture files -->

# Basic failure-loop example

This example shows the correction-retention loop in the smallest public fixture: a monorepo where CI tests only the package that changed.

## Files

```text
examples/basic/
  project/
    memory.md
  memento/
    notes.md
    tattoos.md
    retention_log.jsonl
```

`project/memory.md` holds project-local state, `memento/notes.md` provisional lessons, and `memento/tattoos.md` scarce promoted lessons. `memento/retention_log.jsonl` records the cover-detection decision at a correction or reflection write-time checkpoint.

## The loop

1. The agent renames `format_amount` to `format_money` in the billing package. The billing tests pass, CI is green, and the checkout package, which still calls `format_amount`, breaks after merge. CI never ran the checkout tests because checkout's files did not change.
2. The user corrects the agent. The lesson is captured in `memento/notes.md` as `sess_demo.note.11111111`, with a `Why:` line naming the cause the agent could not see: CI runs only the changed package's tests.
3. A later API change repeats the mistake. That correction becomes `sess_demo.note.22222222`:

```markdown
Situation: an API change passed CI and then broke another package after merge
Note: check whether an existing caller-search lesson should have fired before adding a duplicate note; sharpen its situation so it matches the next API change.
Why: a second note with the same lesson splits future matches, and neither copy gets its trigger repaired.
aliases: correction, repeat, duplicate, retention, downstream, breakage
```

4. The retention log records the decision as `existing-missed`: a relevant lesson existed but did not prevent the correction.
5. The lesson has recurred and applies to every package, so the agent proposes it as a tattoo. The user approves this wording:

```markdown
- Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests.
```

The tattoo follows the shape `<action with its trigger>; <reason clause>.` The reason is a fact about this repo's CI that a model cannot infer from the code, which is what earns it a line that loads every session. The next time an agent is about to change a public function, the tattoo is already in context, before CI can give a false green.

`sess_demo.note.44444444` keeps a general verification reminder, to run the proof command before claiming completion, as a note. Technique reminders like that are retrieved when their situation matches; they do not need the always-loaded layer.

## Try it

From the repo root after installing the package:

```bash
.venv/bin/memento-tattoo --root examples/basic/memento load --project examples/basic/project --query "changing a package public API callers"
.venv/bin/memento-tattoo --root examples/basic/memento doctor --project examples/basic/project
.venv/bin/memento-tattoo --root examples/basic/memento garden
```

`load` ranks `sess_demo.note.11111111` first and the tattoo second. `doctor` reports `why-coverage: hot 3/3 with Why` and `tattoo-reasons: 1/1 with a reason clause`.

## Advanced: local coordination example

The core correction-retention loop above does not require this. Use this shape only when several local sessions may write to the same memento root.

```bash
codex_sess=$(.venv/bin/memento-tattoo --root .tmp/demo-memento --agent codex new-id)
claude_sess=$(.venv/bin/memento-tattoo --root .tmp/demo-memento --agent claude-code new-id)

.venv/bin/memento-tattoo --root .tmp/demo-memento --agent codex note-add \
  --sess "$codex_sess" \
  --kind reflection \
  "Situation: renaming a public function in a shared package
Note: search the other packages for callers before the rename.
Why: CI runs only the changed package's tests."

.venv/bin/memento-tattoo --root .tmp/demo-memento --agent claude-code project-edit \
  --project .tmp/demo-project \
  --sess "$claude_sess" \
  --section "## Current state" \
  --flow-start "2026-06-17T18:24:58Z" \
  "- Situation: billing package API rename
- Note: local project state was updated by a second agent."

.venv/bin/memento-tattoo --root .tmp/demo-memento --agent codex registry-queue \
  --sess "$codex_sess" \
  --action update \
  --slug demo-project \
  "- Demo Project - .tmp/demo-project/ - active"

.venv/bin/memento-tattoo --root .tmp/demo-memento drain
```

The note, project memory edit, and registry delta all go through local lock-protected or queued paths.
