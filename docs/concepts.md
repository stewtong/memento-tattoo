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

Setup:

```text
memento-tattoo init [--root <path>] [--project <project_dir>] [--adapter generic|skill|claude-md-import] [--dir <skills_dir>] [--write]
```

Core loop:

```text
memento-tattoo --root <path> note-add --sess <sess_id> [--kind correction|reflection|seed|pattern] [--decision new|related|existing-missed|applied|overapplied] [--covered-note-id <note_id>] <text>
memento-tattoo --root <path> tattoo-add --sess <sess_id> <text>
memento-tattoo --root <path> project-edit --project <project_dir> --sess <sess_id> [--section "## State"] [--flow-start ISO] [--append|--replace] <text>
memento-tattoo --root <path> load [--project <project_dir>]... --query <query> [--limit N]
memento-tattoo --root <path> entry-read [--id <entry_id>] [--source <store_path>] [--project <project_dir>]... [--format json|markdown]
memento-tattoo --root <path> note-amend --id <note_id> [--source <store_path>] --expected-sha256 <digest> --sess <sess_id> --author <author> --reason <reason> --evidence <source_reference> <complete_active_body>
```

Maintenance:

```text
memento-tattoo --root <path> doctor [--project <project_dir>]... [--alias-coverage-warn PERCENT] [--tattoo-count-warn N] [--tattoo-bytes-warn N] [--tattoo-length-warn N] [--why-coverage-warn PERCENT] [--tattoo-reason-warn PERCENT]
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

## Instruction surface and init

Agents get memento's instructions in two layers. A short stub (five instructions under one heading) goes in the always-on instruction file (`AGENTS.md`, `CLAUDE.md`, or a rules file). It loads tattoos at session start, points at the nearest project `## Current state`, and tells the agent to read `memento/PROTOCOL.md` on a correction, a recognized past situation, or "save work". The protocol holds the procedure and is read only when one of those triggers fires, so its size costs nothing in sessions that do not need it. Both files ship in the package and in `templates/`.

`memento-tattoo init` sets up a repo:

- It creates `notes.md`, `tattoos.md`, `retention_log.jsonl` and `PROTOCOL.md` in the memory root (`./memento` by default, or `--root`), and a project `memory.md` with `## Key Decisions` and `## Current state` in `--project` (default: the current directory when it contains the root, otherwise the root's parent directory).
- It never overwrites. An existing file is reported as `skipped (exists)` and left untouched, so running `init` again is safe and repairs only missing files.
- It prints the stub for you to paste. When the root is not `memento/` under the project directory, the printed paths point at the actual root.

`--adapter` adds a harness-specific pointer. Each adapter points at `memento/PROTOCOL.md` and contains none of its text, so there is one copy of the procedure to maintain:

- `generic` (the default): the stub only.
- `skill`: writes `memento-tattoo/SKILL.md` under `.agents/skills/` in the project directory, or under `--dir <skills_dir>` for a client that reads skills from another directory. The file follows the [Agent Skills specification](https://agentskills.io/specification.md): its `name` matches the `memento-tattoo` directory, and its `description` names the triggers. Its body tells the agent to open `memento/PROTOCOL.md` from the repository root. Format conformance is tested; whether a given client discovers and activates the skill depends on that client.
- `claude-md-import`: prints the `@AGENTS.md` line that makes a `CLAUDE.md` import `AGENTS.md`. With `--write`, it creates `CLAUDE.md` containing that line when the file is absent, and otherwise reports whether the line is already present.

## Notes

Notes are fast lesson captures. They usually come from a correction, reflection, or import. They live in `notes.md` as readable Markdown blocks with a provenance marker:

```markdown
<!-- delta:sess_demo.note.11111111 agent=codex ts=2026-06-17T18:24:58Z -->
Situation: publishing a public repo
Note: scan examples for private names, secret values, and local paths before publishing.
Why: a published file stays in forks and caches after it is deleted.
aliases: oss, public, sanitize, release
review_after: 2026-12-31
```

`Situation:` and `Note:` are required. `Why:` is optional: one or two sentences naming the cost or mechanism behind the lesson. `aliases:` and `review_after:` are optional. Notes written before `Why:` existed load unchanged, and `doctor` reports how many notes carry it.

Old markers without `agent=` or `ts=` still load. New writes include agent identity so several local sessions can leave provenance without changing the stable note id.

For how to write a note that stays retrievable (situation as a recognizable symptom, rule before instance, load-bearing aliases), see [authoring-standards.md](authoring-standards.md).

## Project Memory

Project memory is the middle layer: context local to a project or task area that should survive across sessions. In the public package this lives adjacent to the project as `memory.md`, not inside the Memento root.

Required sections are `## Key Decisions` and a state section, headed `## Current state` or `## State`. `init` writes `## Current state`, the heading the instruction stub names; `project-edit` creates `## State` when it makes a new file, and recall reads either.

```markdown
# Project Memory

## Key Decisions

- Durable decisions that explain why the project is shaped this way.

## Current state

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

A tattoo's documented shape is `<action with its trigger>; <reason clause>.`, for example:

```markdown
- Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests.
```

`doctor` counts a tattoo as having a reason clause when a semicolon separates nonempty action text from nonempty reason text. The count is a shape check; it cannot judge whether the reason is true or still holds.

At session end, the agent manually proposes the strongest candidate and its reason for clearing the bar. The CLI neither proposes nor parks candidates. Explicit approval promotes the proposed wording. Rejection leaves any useful lesson as an ordinary note. If the user takes no action, park the candidate in a durable non-tattoo surface, such as a session marker or tagged note, for later review. Silence is never approval.

For the full five-gate promotion standard, including merge-first and the provenance rule, see [authoring-standards.md](authoring-standards.md).

## Tattoo Audit

`tattoo-audit` is a read-only maintenance command that flags promoted tattoos due for a keep, demote, or cut review. It is an age gate: a tattoo is flagged once it has gone longer than the review window (30 days by default) since it was promoted or since its last recorded review. The reference date comes from the tattoo's provenance marker, with a `reviewed:` watermark resetting the clock when a reviewer leaves one. A tattoo with no resolvable date, or a watermark that points at a session the audit cannot find, is also flagged so it gets a first look.

Recurrence scoring is deliberately excluded from the review gate. The report displays citation telemetry from `tattoo_firing.json` and durable `[[tattoo_id]]` references in notes and sessions, but those counts do not decide whether a tattoo is due for review or whether it should be kept. Conceptual coverage remains an agent judgment.

The command produces no writes. Acting on its output requires explicit agent judgment and the same user-approval gate that governs initial promotion.

## Sessions

Sessions are small Markdown save records in `memento/sessions/`. Agents should reserve a session id with `new-id` instead of inventing one by hand, then write one `session-add` record for the work they completed.

New session IDs must match `sess_[A-Za-z0-9_]+`. The shared writer checks the ID, serialized header, field order and destination before creating files. Header values cannot contain pipes, brackets or control characters. Narrative fields support multiple lines, including qualifications, but a line containing a record delimiter or a reserved field label starts structure and cannot be embedded as narrative. Prefix quoted structural lines with `> ` to keep them inside the narrative. Existing three-field legacy headers remain readable. Session destinations resolving outside the memory root or sessions directory are rejected, including symlink escapes; the writer rechecks under the root lock. External processes that replace directories without taking that lock are outside this cooperative-write guarantee.

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

`doctor` also reports reason coverage:

- `why-coverage: hot X/Y with Why; archive X/Y with Why` counts valid note records carrying a nonempty `Why:` field, over the same records as alias coverage.
- `tattoo-reasons: X/Y with a reason clause` counts tattoos in the `<action with its trigger>; <reason clause>.` shape.

Both are report-only by default. `--why-coverage-warn PERCENT` warns when the hot or archived store falls below that share, and `--tattoo-reason-warn PERCENT` does the same for tattoos. Their default of `0` keeps the warning off. A store with no `Why:` fields reports zero coverage and passes.

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

`load` and the classifier match whole words. Text is lowercased and split on anything that is not a letter or digit, so `save-commit` matches `save` and `commit`, and `art` does not match `start`. Plurals fold to their singular with Harman's three S-stemmer rules (`policies` matches `policy`, `rollbacks` matches `rollback`); `ing` and `ed` endings are not folded, and `indexes` does not match `index`. Words shorter than three characters are ignored unless they contain a digit (`s3`, `v2`).

`load` ranks with BM25F, computed when the query runs, with no index to maintain. A word that appears in few notes counts for more than a common one, a word repeated within one field saturates instead of adding linearly, and long fields are normalized for length. Fields are weighted: situation 3, aliases 2, note 1.5, `Why:` 1, tags 0.5 (k1 1.2, b 0.75). A superseded note keeps half its score, so its successor ranks first. The retention classifier keeps the earlier fixed-bonus scoring, because its cover thresholds are set on that scale.

When adding a `correction` or `reflection` note, the package first ranks existing notes for the new situation. It records `related` for a possible covering lesson or `new` when the classifier finds none.

These matches identify candidates for review. An author must inspect the task evidence to record a missed lesson or useful application. An observed miss can justify repairing the retrieval trigger.

By default, `note-add` records the CLI's suggested decision. Agents can override that decision:

```text
memento-tattoo --root <path> note-add \
  --sess <sess_id> \
  --kind correction \
  --decision existing-missed \
  --covered-note-id sess_old.note.11111111 \
  "Situation: an API change passed CI and then broke another package after merge
Note: sharpened the caller-search lesson so it matches the next public API change."
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

Project operations retain independent JSON receipts in `_project_receipts/`, keyed by the resolved project path and delta ID. This protects both `project-edit` and `save-commit`, including saves without a registry delta. Each receipt records the operation, original marker, before/after SHA-256 values and pending/applied status. Keep this directory with the memory root; receipts are retained when sessions are archived and have no automatic pruning.

Under the root lock, the writer reserves a pending receipt before replacing project content, then marks the receipt applied after the project write. `save-commit` reserves its project operation before writing the session. A retry of a pending operation proceeds only when current content matches its recorded before state; matching after content repairs the missing acknowledgement without rewriting the project. Any other content causes failure with instructions to review state and use a new session. Receipt reads, checks and each project write share the same lock. Writers for the same project must use the same memory root.

An applied operation returns unchanged only while its delta marker remains in the intended section. A later replacement that removes that marker makes an older replay fail before restoring content. A remaining marker is replay evidence, not a proof that manually edited prose still has its original meaning. New operations still use the existing append, replace or concurrent-edit rules. A whole save spans several separately locked writes, so an intervening writer can cause a prepared operation to fail safely; the caller must reconcile that conflict.

For legacy saves with an existing hot or archived session but no project receipt, a surviving project marker can establish a receipt without rewriting the project. If the marker is gone, the save fails closed: the tool cannot distinguish an interrupted historical save from an obsolete completed one. A standalone project edit made before receipts, without a session record or surviving marker, has no recoverable replay identity. Review current state and use a new session ID for that historical operation. Deleting receipts removes replay protection for standalone operations. Malformed or conflicting receipts fail rather than being replaced automatically.

An identical session already in the archive is reused in place; different content for the same ID still fails. Superseded registry operations retain their existing rejection rules. Use expected-line guards for registry drafts and reconcile concurrent project edits.

If a note was persisted but its retention event failed, retrying the note repairs the missing event. Automatic classification is evaluated again at retry time with that note excluded from candidates; it does not reconstruct the earlier task. Existing events retain their original judgment and provenance.


## Read complete evidence and revise ordinary notes

`load` retains its current ranking and preview limits. Each match now includes `source_path`, `entry_id`, `content_sha256`, `excerpt_clipped`, and a shell-quoted `read_reference`. Follow that reference when an exception may be clipped or a decision needs its full source. Historical project `note_id` positions remain in previews for compatibility; use `entry_id` with the exact source for complete reads.

`entry-read` emits JSON containing the exact source, entry kind, identity type, content and its SHA-256. It reads hot/archive notes, marked tattoos, hot/archive sessions, root `project.md`, and project `memory.md` files explicitly declared with `--project`. `--source` disambiguates matching IDs; duplicate records within one source still require reconciliation. Unknown IDs and undeclared source paths fail. A source-scoped read parses that source only, so an unrelated malformed session does not block reading a note. Symlink targets outside declared roots are rejected.

For marked records, `content` preserves the block from its marker, with trailing whitespace normalized to one newline. Its digest covers the UTF-8 bytes of exactly that returned string, including stored revision history. Session records and whole-file snapshots preserve their complete file bytes. Full reads have no preview limit. `--format markdown` displays active content and each revision's previous active text and provenance as readable sections.

Unmarked project pair previews and project state use `project-file:<sha256>` references to the complete project file, so continuation lines and exceptions remain available. Pair previews mark omitted source context explicitly. Any file-content change invalidates that snapshot, including insertion elsewhere; refresh recall to obtain the new reference. These are content snapshots, not durable logical IDs. A source-only read, such as `entry-read --source tattoos.md`, returns the complete declared file, including unmarked legacy content, with a `store-file:<sha256>` reference. Snapshot references require a fresh read after their content changes. Ordinary note IDs remain their original creation identities after amendment; the hash suffix in that ID is not the current-content digest.

To amend a note, read it first, retain the returned `sha256`, and pass the complete revised active body to `note-amend`. Supply the amendment session, author, reason and supporting source reference. `--source` is the store selector; `--evidence` describes the evidence for the change. The CLI checks that provenance fields are supplied, but does not verify their truth or grant authority to change an owner decision.

```sh
memento-tattoo --root ./memento entry-read --id sess_example.note.12345678 --source notes.md
memento-tattoo --root ./memento note-amend --id sess_example.note.12345678 --source notes.md --expected-sha256 <returned_sha256> --sess sess_revision --author codex --reason "Preserve the migration exception" --evidence "owner-review:2026-09-07" "Situation: failed health check
Note: Inspect migration status before restarting.
Exception: while migration is active, preserve the running service."
```

These command shapes use placeholder IDs and digests. Use the values returned by your own source read.

The writer retains the creation marker and atomically replaces the selected Markdown block under the existing root lock. A `memento-history:v1` JSON comment keeps each prior active body, source/reason, author, amendment session, timestamp and operation identity. Each revision stores only its prior active body, so history is not recursively copied. History is excluded from active recall, aliases and supersession fields; historical tattoo references cannot add citation counts. Readable revision output is available through `entry-read --format markdown`.

The expected digest rejects stale changes. An identical immediate retry recognizes the last amendment and preserves file bytes; replay after a later revision fails. All writers must share the same memory root and lock. The atomic replacement uses the existing filesystem guarantees and does not add a power-loss durability claim. Preserve the history comment and creation marker when moving or backing up a block; deleting them removes replay evidence.

The active body requires nonempty `Situation:` and `Note:` fields and cannot inject delta/history comments, record delimiters or duplicate recognized field headers. `Superseded-by:` may point to one existing ordinary note; missing or ambiguous successors, self-reference and cycles fail before writing. Both old and successor records remain available for full reads.

Amendment is an editorial action. It never appends retention observations, bumps firing telemetry or changes tattoos. Capture and evidence-backed revision of working notes may be automatic under the adopted policy. Durable rules, changes to their meaning or scope, and changes to an owner decision require the owner's authorization. Repetition of an agent proposal does not provide it. Record an observed application or miss separately only when the task evidence supports that observation; an edit alone is not evidence of either.
