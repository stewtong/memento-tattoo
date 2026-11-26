<!-- register: public CLI walkthrough | reader: coding-agent users | consumed: terminal execution and task lookup -->

# Save work with the CLI

`save-commit` takes one JSON file describing the session and any memory changes. The agent decides which changes are useful before drafting it. Most sessions need no new lesson or tattoo.

## Save a session, project state, and registry entry

Run these commands in Bash or Zsh from a checkout installed with [the README instructions](../README.md#install-from-a-checkout). Keep the same shell for all blocks. The example creates a disposable directory, reserves a session ID, and writes a complete JSON spec. It records a synthetic example, so substitute your own observed work when adapting it.

```bash
mkdir -p .tmp
demo_dir=$(mktemp -d "$PWD/.tmp/save-demo.XXXXXX")
demo_sess=$(.venv/bin/memento-tattoo --root "$demo_dir/memento" new-id)
demo_date=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

cat > "$demo_dir/save.json" <<EOF
{
  "sess": "$demo_sess",
  "agent": "codex",
  "session": {
    "date": "$demo_date",
    "topics": ["demo", "save-work"],
    "significance": "low",
    "accomplished": "Prepared a synthetic save example.",
    "started": "none",
    "pending": "none",
    "insights": "none",
    "files": ["../project/memory.md", "registry.md"]
  },
  "project_edit": {
    "project": "../project",
    "body": "- Situation: checking the save example\n- Note: the example is ready for read-back.",
    "mode": "replace",
    "flow_start": "$demo_date"
  },
  "registry_delta": {
    "action": "add",
    "slug": "demo",
    "line": "- Demo - ../project/ - Example saved - active",
    "expected_line": ""
  }
}
EOF

.venv/bin/memento-tattoo --root "$demo_dir/memento" save-commit --spec "$demo_dir/save.json"
```

The command should exit zero and end with `RESULT ok`. `project_edit.section` is optional and defaults to the current-state heading the project's `memory.md` already uses (`## Current state` or `## State`). `project_edit.project` resolves relative to the Memento root, so `../project` above creates a sibling directory. Absolute project paths are also supported. The spec filename passed to `--spec` resolves from the shell's working directory. `session.files` records references; it does not create or validate those files.

The required top-level fields are `sess`, `agent`, and `session`. Every field shown inside `session` is required. `topics` and `files` are lists of strings; the other session values are strings. `significance` accepts `low`, `medium`, or `high`. Use a parseable ISO date with an explicit UTC offset, as above. The spec's `agent` supplies save provenance. Reserve a new ID for each new save, then retain that ID and unchanged spec for retries.

For a session-only save, omit `project_edit` and `registry_delta`, and set `session.files` to the actual references or `[]`. A `verify` list of strings is still accepted and optional, but it is discouraged. The check runs as the last step, after every write is already durable, and searches the files the save touched for the strings the spec supplies, so a missing string reports a failed save whose content is already saved. To confirm where the content landed, use the read-back commands in the next section.

## Read back the saved files and replay

```bash
cat "$demo_dir/memento/sessions/$demo_sess.md"
cat "$demo_dir/project/memory.md"
cat "$demo_dir/memento/registry.md"
.venv/bin/memento-tattoo --root "$demo_dir/memento" session-list --limit 5
.venv/bin/memento-tattoo --root "$demo_dir/memento" load --project "$demo_dir/project" --query "checking the save example"
.venv/bin/memento-tattoo --root "$demo_dir/memento" rebuild --check

# Retry the identical save before making any further changes.
.venv/bin/memento-tattoo --root "$demo_dir/memento" save-commit --spec "$demo_dir/save.json"
```

The saved session should appear once, project state should contain the example text, and the registry should contain one `demo` entry. The identical retry should succeed without adding another session, project marker, or registry receipt. Registry receipts live under `_queue/applied/` and, after maintenance, `_queue/applied/archive/`. Project receipts live under `_project_receipts/` even when no registry delta is supplied. Preserve both for replay checks.

## Adapt the spec to an existing project

Read current project memory and the [complete registry file](concepts.md#registry-queue) before drafting changes. Capture `flow_start` before that read. For an intentional current-state rewrite, supply the full replacement section body and `mode: "replace"`. Use `mode: "append"` for an accumulating worklog. Concurrent same-section edits may be preserved in a reconcile block that needs review.

For a registry update, use `action: "update"` and copy the exact inspected summary into `expected_line`. For example, after the walkthrough's first save:

```json
{
  "registry_delta": {
    "action": "update",
    "slug": "demo",
    "line": "- Demo - ../project/ - Read-back verified - active",
    "expected_line": "- Demo - ../project/ - Example saved - active"
  }
}
```

This fragment belongs in a new complete spec with a newly reserved session ID. An empty `expected_line` asserts that the slug is absent. If the guard rejects a stale draft, reread and reconcile the entry before saving. A completed save that has since been superseded cannot be replayed to restore old state.

A new lesson can be supplied as a `note` string with `Situation:`, `Note:`, optional `Why:`, and `aliases:` lines, plus `note_kind` (`correction`, `reflection`, `seed`, or `pattern`). Search existing notes first; repair a covering lesson as [the protocol](../templates/PROTOCOL.md#when-the-user-corrects-you) describes instead of creating a duplicate. See [retention judgment fields](concepts.md#save-commit) for author observations. Add a `tattoo` field only after explicit user approval of its wording.

If a command fails, inspect its step output and the files already written. A save consists of separately verified writes; a later failure can leave earlier changes in place. Retry an unchanged spec when the failure is recoverable. An identical archived session can be replayed while its project and registry operations remain current. If a required receipt is missing, or an operation was superseded or changed during an interrupted save, review current state and reserve a new session ID for further work. See [save recovery](concepts.md#retry-saves-without-restoring-old-state).
