# Changelog

## Unreleased

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
