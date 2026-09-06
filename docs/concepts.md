<!-- register: public reference documentation | reader: coding-agent implementers | consumed: task lookup -->

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
memento-tattoo --root <path> note-add --sess <sess_id> [--kind correction|reflection|seed|pattern] [--decision new|related|existing-missed|applied|overapplied] [--covered-note-id <note_id>] <text>
memento-tattoo --root <path> tattoo-add --sess <sess_id> <text>
memento-tattoo --root <path> project-edit --project <project_dir> --sess <sess_id> [--section "## State"] [--flow-start ISO] [--append|--replace] <text>
memento-tattoo --root <path> load [--project <project_dir>]... --query <query> [--limit N]
```

Maintenance:

```text
memento-tattoo --root <path> doctor [--project <project_dir>]... [--alias-coverage-warn PERCENT] [--tattoo-count-warn N] [--tattoo-bytes-warn N] [--tattoo-length-warn N]
memento-tattoo --root <path> garden [--today YYYY-MM-DD] [--promote-threshold N] [--limit N]
memento-tattoo --root <path> rebuild [--check]
memento-tattoo --root <path> queue-maintenance [--days N] [--max-hot N] [--apply]
memento-tattoo --root <path> session-list [--limit N] [--hot-only|--archive-only]
memento-tattoo --root <path> session-archive --days N [--limit N] [--apply]
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

For how to write a note that stays retrievable (situation as a recognizable symptom, rule before instance, load-bearing aliases), see [authoring-standards.md](authoring-standards.md).

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

Promote only when the lesson has recurred and is durable across unrelated future sessions, behavioral rather than merely informational, broader than the project or file that produced it, short enough to load often, and written as a declarative principle or compact rule. Tattoo promotion still requires explicit user approval before running `tattoo-add`.

At session end, the agent manually proposes the strongest candidate and its reason for clearing the bar. The CLI neither proposes nor parks candidates. Explicit approval promotes the proposed wording. Rejection leaves any useful lesson as an ordinary note. No action parks the candidate in a durable non-tattoo surface, such as a session marker or tagged note, for later review. Silence is never approval.

For the full five-gate promotion standard, including merge-first and the provenance rule, see [authoring-standards.md](authoring-standards.md).

## Tattoo Audit

`tattoo-audit` is a read-only maintenance command that flags promoted tattoos due for a keep, demote, or cut review. It is an age gate: a tattoo is flagged once it has gone longer than the review window (30 days by default) since it was promoted or since its last recorded review. The reference date comes from the tattoo's provenance marker, with a `reviewed:` watermark resetting the clock when a reviewer leaves one. A tattoo with no resolvable date, or a watermark that points at a session the audit cannot find, is also flagged so it gets a first look.

Recurrence scoring is deliberately excluded from the review gate. The report displays citation telemetry from `tattoo_firing.json` and durable `[[tattoo_id]]` references in notes and sessions, but those counts do not decide whether a tattoo is due for review or whether it should be kept. Conceptual coverage remains an agent judgment.

The command produces no writes. Acting on its output requires explicit agent judgment and the same user-approval gate that governs initial promotion.

## Sessions

Sessions are small Markdown save records in `memento/sessions/`. Agents should reserve a session id with `new-id` instead of inventing one by hand, then write one `session-add` record for the work they completed.

`session-list` reads hot and archived session records, newest first, and prints stable tab-separated fields for ID, date, agent, significance, topics, and location. Use `--hot-only` or `--archive-only` to narrow the result.

`session-archive --days N` selects hot records strictly older than the parsed-date cutoff. It previews exact source and destination paths by default. `--apply` moves a prevalidated batch, limited to 100 records unless `--limit` changes it. The CLI validates every source, destination, and duplicate ID before its first move, then rebuilds the indexes. The command preserves session content and IDs; archived sessions remain in lookup, rebuild, and collision checks. The caller chooses `N`; the package does not impose a retention period.

Generated indexes live at:

```text
memento/sessions/index.md
memento/sessions/index-recent.md
```

Run `rebuild` to refresh them or `rebuild --check` to detect drift.

## Doctor recommendations

`doctor` reports hot and archived note alias coverage separately as `aliased/total`. The default archived-note recommendation is 60 percent. It also reports tattoo count, aggregate UTF-8 bytes, and tattoos longer than the configured length. Its recommended starting values are 25 tattoos, 7,168 bytes, and 300 characters per tattoo.

These values are review triggers, not validity requirements or quotas. Each warning accepts an override, and `0` disables that warning while preserving the measurement. Low archive coverage asks for alias review; it never causes aliases to be generated. Tattoo pressure starts a keep, demote, merge, or cut review; it never removes a lesson automatically.

## Registry Queue

`registry.md` is an optional compact index of project summaries. A complete generated file looks like this:

```markdown
# Registry

<!-- registry-entry slug=demo status=active updated=2026-09-05T12:00:00Z agent=codex sess=sess_abcd -->
- Demo - ../project/ - Example saved - active
```

The heading is exactly `# Registry` and appears first, apart from blank lines. Each entry has a `registry-entry` comment immediately followed by one nonempty summary line. Keep each slug unique. The CLI generates the timestamp, session, agent, and status metadata; `status` is `active` or `archived`. Legacy entries may omit provenance fields. Additional headings, free-standing bullets, and unrelated prose are rejected when the registry is read for an update.

For a new root, let `save-commit` or `registry-queue` followed by `drain` create the file. An existing empty registry can contain just `# Registry` and a newline. Use [the save walkthrough](save-work.md) to create an entry and replay the save.

For a guarded update, read the current file and copy only the summary line, including its leading `- `, into `registry_delta.expected_line`. Put the replacement summary in `registry_delta.line`. Use an empty expected line only when that slug is absent; omitting the field disables the guard. Registry summaries are stored as text: their paths are reader-facing references, not directories that drain opens or validates.

Agents write registry changes through `_queue/` first. A queued delta has a different marker from a stored entry:

```markdown
<!-- registry-delta sess=sess_abcd action=update slug=memento-oss agent=codex ts=2026-06-17T18:24:58Z -->
- Memento OSS - memento-oss/ - active
```

`drain` validates every existing registry entry before rewriting the registry; malformed entries, duplicate slugs, or unrecognized content fail without consuming the queue. It applies queued deltas under the root lock. Same-slug collisions are deterministic: the newest delta wins, loser files move to `_queue/conflicts/`, and the winner gets a `registry-conflict` comment.

`queue-maintenance` previews conflicts older than 30 days or beyond the newest 200 by default. Add `--apply` to move those files into `_queue/conflicts/archive/`; no conflict artifact is deleted.

## Save Commit

`save-commit --spec <json>` is the preferred driver when one session updates several surfaces. It validates the submitted schema before writing, then calls the same lower-level commands for sessions, notes, tattoos, project memory, registry queue/drain, and rebuild.

[Save work with the CLI](save-work.md) provides a complete runnable spec, the required field types, and persistence and replay checks.

It is not a transaction. If a later verification fails, earlier durable writes remain in place and are reported in the result.

The agent still performs the judgment pass before writing the spec. A typical spec contains the session summary, an optional note, optional retention judgment fields, optional project memory update, optional registry update, and verify strings.

Project memory updates can include `"mode": "auto"`, `"mode": "append"`, or `"mode": "replace"` inside `project_edit`. Use append for accumulating sections and replace for intentional current-state rewrites.

Retention judgment fields:

```json
{
  "retention": {
    "decision": "existing-missed",
    "covered_note_id": "sess_old.note.11111111"
  }
}
```

Use these fields only with correction or reflection notes. Seed and pattern notes do not log retention events and reject explicit retention judgments. Use `retention.decision` when the agent has better context than the retrieval classifier. Use `covered_note_id` to attach a repeat miss or repair to the lesson that should have fired, rather than only to the newly written note.

## Checked Retrieval

When adding a `correction` or `reflection` note, the package first ranks existing notes for the new situation. It records `related` for a possible covering lesson or `new` when the classifier finds none.

These matches identify candidates for review. An author must inspect the task evidence to record a missed lesson or useful application. An observed miss can justify repairing the retrieval trigger.

By default, `note-add` records the CLI's suggested decision. Agents can override that decision:

```text
memento-tattoo --root <path> note-add \
  --sess <sess_id> \
  --kind correction \
  --decision existing-missed \
  --covered-note-id sess_old.note.11111111 \
  "Situation: repeating an unverified completion claim
Note: strengthened the completion-check lesson so future claims load the proof-command rule."
```

This keeps the CLI mechanical while letting the agent remain the judge.

## Retention Log

The retention history is logically append-only across `retention_log.jsonl` and `retention_log_archive.jsonl`. Each checked note write appends to the hot log. When the hot file exceeds its byte target, complete older events move to the archive and readers combine both files.

Rotation atomically replaces each file, archiving before trimming the hot log. New events carry unique `event_id` values; legacy hot events receive distinct IDs before a new rotation copies them. Readers ignore matching event IDs at the archive boundary, and a later note retry or rotation removes those copies. Separate identical observations remain distinct. Identical legacy events already split across stores have no such proof: readers preserve them and warn that source evidence is needed to reconcile the ambiguity. There is no history-wide deduplication.

Each checked note write records:

- unique event id

- timestamp
- session id
- note kind
- situation
- written note id
- ranked candidates
- decision and its source (`author` or `classifier`)
- optional covered note id

The shipped decisions are:

- `new`: no dominant existing lesson covered the situation.
- `related`: automatic retrieval found a possible covering lesson.
- `existing-missed`: the author recorded a missed lesson.
- `applied`: the author recorded useful application.
- `overapplied`: the author recorded harmful or unnecessary application.

Older logs may contain `existing-repaired` or `false-positive`; readers tolerate those legacy values, but current writes do not produce them.

## Gardener Digest

The read-only gardener reports:

- notes past their `review_after` date
- author-recorded missed lessons for review
- promotion candidates based on author-recorded recurrence
- a placeholder section for future merge suggestions

## Retention Health

Retention health is:

```text
existing-missed / (new + existing-missed)
```

It is a note-write classification signal, not a benchmark or a measure of prevention. Optional author observations can record useful application or overapplication. The log has no comprehensive retrieval-exposure or opportunity denominator, so application rate and recurrence against opportunities remain unmeasured. The old `repeat_correction_rate` function name remains as a compatibility alias.

## Interpret evidence within its scope

Automatic classification records `new` or `related`. Author judgments record their source separately. Historical events without that provenance remain unverified classifications; gardening retains their count but excludes them from observed-miss promotion counts. Citation counts establish mentions. Behavioral effectiveness requires evidence from the task. Sparse citations alone do not justify removing a rare, consequential safeguard.

Use the named project's current state together with transferable lessons matching the action. Expand the search when evidence conflicts, a needed source is absent, or a consequential decision needs more support. A bounded result cannot establish absence. A newer summary does not supersede an authoritative decision merely by being newer. Preserve useful successful approaches as well as corrections.

A tattoo states when its action helps and preserves necessary exceptions. Its wording must not turn a local correction into a universal restriction. Review scope, overlap, and the cost of unnecessary application before proposing it. Existing approval and candidate-parking rules still apply.

## Retry saves without restoring old state

Identical registry operations reuse their original receipts and timestamps. Applied receipts retain a bounded hot window; older receipts move to `_queue/applied/archive/`. Preserve those files for replay checks. If an existing session lacks a matching receipt, review current state and use a new session ID. A superseded save returns failure instead of reapplying its older registry line.

Note rotation writes the archive before removing hot content. A retry reconciles overlap and checks both stores for existing note IDs. Each surface is verified separately; the complete save is not an all-or-nothing transaction. A failure may leave earlier verified steps in place. Rebuild writes only changed indexes.

A save whose completed registry operation has been superseded fails before writing project snapshots. This check does not serialize a whole save against concurrent writers. Use expected-line guards for registry drafts and reconcile concurrent project edits. Replaying a session already moved to the session archive is rejected by the session collision check; review current state and reserve a new session ID for further work.

If a note was persisted but its retention event failed, retrying the note repairs the missing event. Automatic classification is evaluated again at retry time with that note excluded from candidates; it does not reconstruct the earlier task. Existing events retain their original judgment and provenance.
