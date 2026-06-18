# Basic failure-loop example

This example shows the correction-retention loop in the smallest public fixture.

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

`project/memory.md` holds project-local state. `memento/notes.md` holds provisional lessons. `memento/tattoos.md` holds scarce promoted lessons. `memento/retention_log.jsonl` records whether retrieval worked when a correction or reflection was added.

## The loop

1. The agent changes code and says the work is complete without running the test command that would prove it.
2. The user corrects the agent. The lesson is captured in `memento/notes.md` as `sess_demo.note.11111111`.
3. The correction becomes `sess_demo.note.22222222`:

```markdown
Situation: repeating an unverified completion claim
Note: check whether an existing verification lesson should have fired before adding a duplicate note.
aliases: correction, verification, duplicate, retention, complete
```

4. The retention log records the decision as `existing-repaired`, which means a relevant lesson existed and was improved rather than treated as brand new.
5. If the user approves the wording, the broader operating rule is promoted to a tattoo:

```markdown
- Before claiming work is complete, run the command that proves it and read the output.
```

That is the behavior change: the next time an agent is about to say a change is done, it should load the tattoo, run the proof command, and report the output instead of relying on confidence.

## Try it

From the repo root after installing the package:

```bash
.venv/bin/memento-tattoo --root examples/basic/memento load --project examples/basic/project --query "claiming complete verification"
.venv/bin/memento-tattoo --root examples/basic/memento garden
```

## Advanced: local coordination example

The core correction-retention loop above does not require this. Use this shape only when several local sessions may write to the same memento root.

```bash
codex_sess=$(.venv/bin/memento-tattoo --root .tmp/demo-memento --agent codex new-id)
claude_sess=$(.venv/bin/memento-tattoo --root .tmp/demo-memento --agent claude-code new-id)

.venv/bin/memento-tattoo --root .tmp/demo-memento --agent codex note-add \
  --sess "$codex_sess" \
  --kind reflection \
  "Situation: claiming complete
Note: run the proof command before saying done."

.venv/bin/memento-tattoo --root .tmp/demo-memento --agent claude-code project-edit \
  --project .tmp/demo-project \
  --sess "$claude_sess" \
  --section "## State" \
  --flow-start "2026-06-17T18:24:58Z" \
  "- Situation: verification loop
- Note: local project state was updated by a second agent."

.venv/bin/memento-tattoo --root .tmp/demo-memento --agent codex registry-queue \
  --sess "$codex_sess" \
  --action update \
  --slug demo-project \
  "- Demo Project - .tmp/demo-project/ - active"

.venv/bin/memento-tattoo --root .tmp/demo-memento drain
```

The note, project memory edit, and registry delta all go through local lock-protected or queued paths.
