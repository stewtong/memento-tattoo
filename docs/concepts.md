# Concepts

`memento-tattoo` separates memory into layers so an agent can keep lightweight working lessons without pretending every note is permanent.

## When to use the CLI

Plain Markdown is enough to try the correction-retention pattern. Use the CLI when you want guardrails around the files:

- checked writes with provenance markers
- ranked recall for task-specific memory loading
- doctor checks and read-only gardening
- session indexes and rebuild checks
- optional local coordination for parallel sessions

## Command reference

Core loop:

```text
memento-tattoo --root <path> note-add --sess <sess_id> [--kind correction|reflection|seed] [--decision new|existing-missed|existing-repaired|false-positive] [--repair <text>] [--covered-note-id <note_id>] <text>
memento-tattoo --root <path> tattoo-add --sess <sess_id> <text>
memento-tattoo --root <path> project-edit --project <project_dir> --sess <sess_id> [--section "## State"] [--flow-start ISO] [--append|--replace] <text>
memento-tattoo --root <path> load [--project <project_dir>]... --query <query> [--limit N]
```

Maintenance:

```text
memento-tattoo --root <path> doctor [--project <project_dir>]...
memento-tattoo --root <path> garden [--today YYYY-MM-DD] [--promote-threshold N]
memento-tattoo --root <path> rebuild [--check]
```

Advanced local coordination:

```text
memento-tattoo --root <path> --agent <agent_id> new-id
memento-tattoo --root <path> --agent <agent_id> session-add --sess <sess_id> --date "2026-06-17 18:24" --topics "memento-oss,multi-agent" --significance medium --accomplished "Published docs polish" --started "none" --pending "none" --insights "none" --files "README.md; templates/AGENTS.md"
memento-tattoo --root <path> --agent <agent_id> registry-queue --sess <sess_id> --action update --slug memento-oss "- Memento OSS - memento-oss/ - active"
memento-tattoo --root <path> drain
memento-tattoo --root <path> save-commit --spec <json>
```

Set `--agent <agent_id>` or `MEMENTO_AGENT` when several sessions may write to the same root. Agent IDs are provenance, not permissions.

## Notes

Notes are fast lesson captures. They usually come from a correction, reflection, or import. They live in `notes.md` as readable Markdown blocks with a provenance marker:

```markdown
<!-- delta:sess_demo.note.11111111 agent=codex ts=2026-06-17T18:24:58Z -->
Situation: publishing a public repo
Note: scan examples for private names, secret values, and local paths before publishing.
aliases: oss, public, sanitize, release
review_after: 2026-12-31
```

Old markers without `agent=` or `ts=` still load. New writes include agent identity so several local sessions can leave provenance without changing the stable note id.

## Project Memory

Project memory is the middle layer: context local to a project or task area that should survive across sessions. In the public package this lives adjacent to the project as `memory.md`, not inside the Memento root.

Required sections:

```markdown
# Project Memory

## Key Decisions

- Durable decisions that explain why the project is shaped this way.

## State

- Situation: current work surface
- Note: what changed, what matters now, and what a future agent should not rediscover.
```

`project-edit` updates a named `##` section under the Memento lock. It has three modes:

- default `auto`: replace only when doing so will not silently drop existing delta markers; with `--flow-start`, preserve concurrent same-section edits under a `concurrent-edit reconcile` block
- `--append`: add a new delta to an accumulating section such as a worklog
- `--replace`: intentionally rewrite a section, typically for current-state snapshots such as `## State`

Markers without timestamps are preserved conservatively when `--flow-start` is used.

The first implementation keeps parsing deliberately simple. It recognizes adjacent bullet pairs:

```markdown
- Situation: release readiness
- Note: verify installability before publishing
```

## Tattoos

Tattoos are scarce promoted lessons intended to be visible before broad classes of future action. A tattoo is not a good tip, a summary, or a project fact.

Unlike project `memory.md` and `notes.md`, tattoos are intended to be loaded at startup. They pay an always-on context cost, so promotion needs a stricter test:

```text
If this had been loaded at the beginning of the session, would it have dramatically improved the course of action?
```

Promote only when the lesson is durable across unrelated future sessions, behavioral rather than merely informational, broader than the project or file that produced it, short enough to load often, and written as a declarative principle or compact rule. Tattoo promotion still requires explicit user approval before running `tattoo-add`.

## Tattoo Audit

`tattoo-audit` is a read-only maintenance command that flags promoted tattoos due for a keep, demote, or cut review. It is an age gate: a tattoo is flagged once it has gone longer than the review window (30 days by default) since it was promoted or since its last recorded review. The reference date comes from the tattoo's provenance marker, with a `reviewed:` watermark resetting the clock when a reviewer leaves one. A tattoo with no resolvable date, or a watermark that points at a session the audit cannot find, is also flagged so it gets a first look.

Recurrence scoring is deliberately excluded from this command. Whether a tattoo has fired often enough to justify its always-on context cost is a semantic verdict, not a lexical match. A frequency count over raw note text would misclassify paraphrase matches and miss conceptual coverage, producing noisy signals in both directions. The design keeps `tattoo-audit` mechanical and fast, and leaves the keep or demote judgment to the Tier-2 reviewer with full context.

The command produces no writes. Acting on its output requires explicit agent judgment and the same user-approval gate that governs initial promotion.

## Sessions

Sessions are small Markdown save records in `memento/sessions/`. Agents should reserve a session id with `new-id` instead of inventing one by hand, then write one `session-add` record for the work they completed.

Generated indexes live at:

```text
memento/sessions/index.md
memento/sessions/index-recent.md
```

Run `rebuild` to refresh them or `rebuild --check` to detect drift.

## Registry Queue

`registry.md` is an optional compact index of project summaries. Agents write registry changes through `_queue/` first:

```markdown
<!-- registry-delta sess=sess_abcd action=update slug=memento-oss agent=codex ts=2026-06-17T18:24:58Z -->
- Memento OSS - memento-oss/ - active
```

`drain` applies queued deltas under the root lock. Same-slug collisions are deterministic: the newest delta wins, loser files move to `_queue/conflicts/`, and the winner gets a `registry-conflict` comment.

## Save Commit

`save-commit --spec <json>` is a convenience driver for agents that want to update several surfaces in one checked sequence. It validates the spec before writing, then calls the same lower-level commands for sessions, notes, tattoos, project memory, registry queue/drain, and rebuild.

It is not a transaction. If a later verification fails, earlier durable writes remain in place and are reported in the result.

The agent still performs the judgment pass before writing the spec. A typical spec contains the session summary, an optional note, optional retention judgment fields, optional project memory update, optional registry update, and verify strings.

Project memory updates can include `"mode": "auto"`, `"mode": "append"`, or `"mode": "replace"` inside `project_edit`. Use append for accumulating sections and replace for intentional current-state rewrites.

Retention judgment fields:

```json
{
  "retention": {
    "decision": "existing-repaired",
    "repair": "added verification and complete aliases",
    "covered_note_id": "sess_old.note.11111111"
  }
}
```

Use `retention.decision` when the agent has better context than the retrieval classifier. Use `covered_note_id` to attach a repeat miss or repair to the lesson that should have fired, rather than only to the newly written note.

## Checked Retrieval

When adding a `correction` or `reflection` note, the package first ranks existing notes for the new situation. It then records whether the system found a strong existing cover or whether the situation appears new.

This makes repeated correction visible. If the same lesson was already present but did not fire, that is not just a new note; it is evidence that the retrieval trigger may need repair.

By default, `note-add` records the CLI's suggested decision. Agents can override that decision:

```text
memento-tattoo --root <path> note-add \
  --sess <sess_id> \
  --kind correction \
  --decision existing-repaired \
  --repair "added verification and complete aliases" \
  --covered-note-id sess_old.note.11111111 \
  "Situation: repeating an unverified completion claim
Note: strengthened the completion-check lesson so future claims load the proof-command rule."
```

This keeps the CLI mechanical while letting the agent remain the judge.

## Retention Log

`retention_log.jsonl` is append-only. Each checked note write records:

- timestamp
- session id
- note kind
- situation
- written note id
- ranked candidates
- suggested decision
- optional covered note id
- optional repair note
- review flag

The core decisions are:

- `new`: no dominant existing lesson covered the situation.
- `existing-missed`: a likely lesson existed but did not prevent the correction.
- `existing-repaired`: a likely lesson existed and was repaired.
- `false-positive`: retrieval suggested a cover that should not count.

## Gardener Digest

The gardener is read-only. It lists:

- notes past their `review_after` date
- lessons with repeated missed retrievals
- promotion candidates based on recurrence count
- a placeholder section for future merge suggestions

## Repeat-Correction Rate

Repeat-correction rate is:

```text
(existing-missed + existing-repaired) / (new + existing-missed + existing-repaired)
```

It is a useful directional signal, not a benchmark. A high value can mean retrieval is weak, lesson triggers are too narrow, or the operator is repeatedly working in the same failure area. A low value can mean the system is learning new lessons, or it can mean old misses are not being checked carefully.
