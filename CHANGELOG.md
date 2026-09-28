<!-- register: public release history | reader: users and contributors | consumed: version lookup -->

# Changelog

## 0.5.0 - 2026-09-28

The first tagged release. Install it from GitHub with `uvx --from git+https://github.com/stewtong/memento-tattoo@v0.5.0 memento-tattoo init`; it is not published to PyPI. It also includes the 0.4.0 changes, which were never released on their own; see the [full changelog](https://github.com/stewtong/memento-tattoo/blob/v0.5.0/CHANGELOG.md).

- Splits the agent instructions into a short always-on stub (`templates/memento-stub.md`) and an on-demand procedure (`templates/PROTOCOL.md`) covering corrections, retrieval, the save judgment pass, record formats and promotion gates in plain-file and CLI modes. The pattern contract's agent-instructions block is now the stub.
- Adds `memento-tattoo init`, which creates the memory root files and project `memory.md`, copies `PROTOCOL.md`, prints the stub, and never overwrites an existing file. `--adapter skill` writes an Agent Skills `SKILL.md` that points to the protocol; `--adapter claude-md-import` prints or creates the `CLAUDE.md` import line. The protocol and stub ship as package data.
- Adds an optional `Why:` note field and a documented tattoo shape, `<action with its trigger>; <reason clause>.` `doctor` reports `Why:` coverage for hot and archived notes and reason-clause coverage for tattoos. Both are report-only by default, with `--why-coverage-warn` and `--tattoo-reason-warn` thresholds that are off unless set.
- `doctor` accepts `## Current state` as well as `## State` as a project memory's state section.
- Replaces the flagship example. The bundled example, README loop and quickstart now teach a monorepo lesson: search other packages for callers before changing a public API, because CI runs only the changed package's tests. The earlier verification rule, "Before claiming work is complete, run the command that proves it and read the output.", remains as a note in the example, since technique reminders belong in notes.
- `templates/AGENTS.md` becomes a worked example: the stub beside a sample repo's own rules.
- Replaces the README's compatibility sentence with the design intent (harness- and model-agnostic) and states that no harness and model combination has a recorded cross-harness test yet.
- Keeps one copy of "Interpret evidence within its scope", in `docs/concepts.md`, with links from the pattern. Moves tool semantics out of the agent instructions into `docs/concepts.md`.
- `load` ranks with field-weighted BM25 (BM25F) instead of fixed bonuses per matched word, so a rare word such as `ledger` outweighs common ones such as `agent` or `test`, and the `Why:` field now counts toward matching. Queries and notes match whole words instead of substrings, with plural folding, so `art` no longer matches `start` and `rollbacks` matches `rollback`. End-to-end `load` over 5,000 synthetic notes takes about 0.45 s, against 0.35 s in 0.4.0. The retention classifier also matches whole words but keeps fixed-bonus scoring, since its thresholds are calibrated to it.
- Adds `memento-tattoo --version`.
- `note-add` and `tattoo-add` reject text containing a record marker (`<!-- delta:` or `<!-- memento-history:`), which would corrupt the file it lands in. A hand-edited, malformed history block now makes `load` exit with an error naming the note, and `doctor` reports it as a failed check instead of crashing. `note-add` and `tattoo-add` report errors instead of printing a traceback.
- `save-commit` without a `project_edit.section` edits the current-state heading the project's `memory.md` already has, so a project created by `init` (`## Current state`) no longer gains a second, `## State` section. `load` skips an empty current-state heading when a later one has content.
- `load` and the cover check in `note-add` refuse a root file that resolves outside the memory root, such as a `notes.md` symlinked to another directory. Keep the memory files inside the root.
- Adds a protocol section for bringing in rules a repo already keeps (`AGENTS.md`, `CLAUDE.md`, rules folders, harness memory): the agent proposes candidate notes for approval, writes approved ones as `seed` notes, and leaves the source unchanged.
- Adds `SECURITY.md`: private reporting through GitHub, scope, and supported versions.
- Adds issue and pull request templates, and a release workflow that builds each tagged version and publishes it as a GitHub release, with the changelog entry as its notes.
- Publishes the evaluation code under `bench/`, including the repeated-correction benchmark built from public code review. Its first results, on prometheus/prometheus, found no advantage for memento-tattoo over any of five baselines, including a short curated file and no memory, on 50 queries that searched with the raw diff; the sample detects only differences of about 18 percentage points or more at 80% power: [results](https://github.com/stewtong/memento-tattoo/blob/v0.5.0/bench/w9b/RESULTS.md).

## 0.4.0 - not released separately

These changes first ship in 0.5.0.


- Adds complete source-scoped entry reads, explicit preview clipping and read references, including content snapshots for unmarked project records.
- Adds guarded ordinary-note amendments with stable creation IDs, visible prior content and provenance, byte-stable immediate retry and stale-write rejection.
- Keeps editorial revision history out of active recall and citation counts; amendments create no retention observations or tattoo changes.

- Repositions the README around persistent memory for coding agents: a category-first opening with the notes/Polaroids/tattoos mapping, the film's unreliable-records rationale, the correction-to-recall example up front, and consolidated positioning sections. The displayed hero now appears in the README itself, and the park-on-silence rule matches the pattern contract.
- Aligns the package description with the coding-agent positioning.
- Rejects superseded project replays without requiring a registry delta; preserves independent receipts and recovers interrupted project writes by recorded content hashes.
- Validates session IDs, serialized headers, field structure and destination containment before persistence; reuses identical archived sessions in place.
- Preserves multiline note qualifications and session narratives, including continuation-only recall matches from hot and archived notes.

- Adds a runnable save JSON walkthrough and the complete registry-file format, with guarded-update and replay guidance.
- Recovers interrupted retention rotation without counting copied events twice; gives new events distinct identities.
- Verifies registry save ownership, applied receipt, status, and exact line; rejects malformed existing registry content before rewriting.
- Verifies replayed notes in their actual archive location and rejects unsupported retention judgments on pattern notes.
- Aligns plain-file adoption, promotion gates, alias guidance, and replay claims with the public contract.

- Includes Markdown test fixtures in source distributions so the packaged test suite can run independently.
- Rejects existing export destinations and source symlinks before copying public files.
- Rejects superseded registry saves before project snapshot writes and reports malformed save options without raising type errors.
- Recovers missing retention events on note retry, excludes the note itself from cover detection, and reads drain indexes under the memory lock.
- Adds optional expected-line checks to prevent stale registry drafts from overwriting newer state; preflight and drain both validate the source.
- Includes explicit current project state alongside action-matched lessons and removes duplicate index generation from saves.

- Preserves registry replay receipts through archival and prevents old saves from restoring superseded state. Ambiguous historical replay fails with a recovery instruction.
- Preserves note content before rotation removes hot blocks, reconciles interrupted writes, and deduplicates replay across both note stores.
- Applies registry archive operations by action and slug, normalizes recent-session ordering across offsets, and avoids rewriting unchanged indexes.
- Records automatic similarity as `related`; separates author-recorded misses, useful application, and overapplication. Historical classifications remain readable without being treated as observed recurrence.
- Clarifies conditional tattoo guidance and preserves the qualifications needed to avoid overapplication.

## Source update - 2026-08-30

Published to the source repository with package version 0.3.1.

- Adds session inspection and caller-controlled, dry-run-first archival. Archived sessions remain readable and retain their IDs and content.
- Adds doctor recommendations for separate hot and archived alias coverage, tattoo count, aggregate UTF-8 bytes, and tattoo length. Recommendations are configurable review triggers and never modify lessons.
- Establishes `MEMENTO-PATTERN.md` as the canonical standalone contract for plain-file adaptation and the reference CLI, including explicit approval and no-action parking for tattoo candidates.
- Clarifies the public file layout, retention-log rotation, multi-surface save path, tattoo approval boundary, and local HTML demo instructions.

## 0.3.1 - 2026-08-28

- Hardens checked saves with complete preflight validation, per-surface marker checks, and registry verification.
- Preserves complete retention history while bounding the hot log by bytes, and bounds registry conflicts through lossless archival.
- Prevents cross-store session-id collisions and reports duplicate session ids, malformed firing telemetry, queue corruption, and actionable gardening state in `doctor`.
- Derives tattoo citation counts from durable notes and sessions when the JSON cache is stale or missing.
- Bounds gardener output by default, fixes recurrence attribution, and adds explicit full-output and queue-maintenance controls.
- Adds the public seven-slide HTML demo and its visual asset, and documents the POSIX platform requirement.

## 0.3.0 - 2026-07-11

- Adds a deterministic cover-detection evaluation with independently phrased positive and negative queries; the seeded baseline is 3/3 true covers flagged and 0/3 negative queries flagged.
- Relabels the operational repeat metric as retention health, adds the `retention_health_rate` API with a compatibility alias, and makes doctor/garden output explicit about what the signal does not measure.
- Aligns public retention documentation and examples with the shipped `new` / `existing-missed` write vocabulary while keeping legacy event values readable.
- Tightens the README thesis around the promotion gate, situation-recognition recall, and checked retrieval.

## 0.2.3 - 2026-07-07

- Tightens retention logging to the two decisions the writer produces, while keeping legacy repeat events readable.
- Adds cluster-cover detection for flat, high-scoring same-tag note families and records the covering note id on new retention events.
- Adds Situation-line altitude hints for label-shaped notes, tattoo firing counters for cited tattoo ids, and tattoo-audit usage annotations.
- Adds retention event author provenance and the `pattern` note kind, which writes live notes without diluting correction metrics.
- Adds doctor checks for low repeat-correction rate at volume and optional recall probes.

## 0.2.2 - 2026-07-07

- Adds `docs/authoring-standards.md`: a gated standard for how to write a tattoo (five checks) and a note (four checks plus per-field rules), with the merge-first caveat that a genuine sibling shares the action and not just the theme. Linked from `docs/concepts.md`.
- Fixes an agent-guidance blind spot introduced with the hot/cold split: `templates/AGENTS.md` now tells the agent to retrieve with `memento-tattoo load` (which reads both `notes.md` and `notes_archive.md`) or, when grepping, to search the whole `memento/` directory. Grepping only the hot `notes.md` silently misses lessons that have rotated to the archive.

## 0.2.1 - 2026-07-03

- Bounds the hot `notes.md` file: `note-add` now auto-rotates the oldest note blocks to a new cold `notes_archive.md` whenever the hot file exceeds 30 KB, under the same lock as the write. Rotation is not lossy: `load_memento_notes` (and therefore recall and the retention loop) reads both files, so a rotated note still ranks and still covers a repeat. Fires for every writer (correction/reflection/seed).
- Tightens the README by subtraction: single canonical file-layout diagram, a scannable capability block, the retention loop promoted to a named feature, and neutral maintainer guidance in place of internal "development checkout" framing.

## 0.2.0 - 2026-07-03

- Adds guarded `project-edit` modes: default `auto`, explicit `--append`, and explicit `--replace`.
- Documents selective loading, agent judgment, and the stricter tattoo promotion bar.
- Adds a read-only `tattoo-audit` command that flags promoted tattoos due for a keep, demote, or cut review, based on an age and watermark gate. Adds a matching warn-only `doctor` check.
- Fixes near-dead `existing-missed` detection in the retention loop: a strong absolute match (`STRONG_COVER_SCORE`) now counts as a cover even when a close vocabulary neighbor keeps the top/second ratio under `DOMINANCE_RATIO`. Genuine same-lesson covers routinely share high scores with neighbors, so the ratio guard alone classified almost every real repeat as `new`. Adds a populated-tree regression test.
- Bounds `_queue/applied/` growth: `drain` now prunes the applied-delta audit trail to the most recent 100 files (previously unbounded).

## 0.1.0 - 2026-06-17

- Initial reference implementation.
- Adds file-based notes, project memory, tattoos, and retention log.
- Adds checked retrieval for correction/reflection notes.
- Adds `doctor`, `garden`, `load`, `note-add`, `project-edit`, and `tattoo-add` CLI commands.
- Adds example root and package smoke tests.
