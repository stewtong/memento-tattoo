# Concepts

`memento-tattoo` separates memory into layers so an agent can keep lightweight working lessons without pretending every note is permanent.

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

`project-edit` updates a named `##` section under the Memento lock. If the caller provides `--flow-start`, it preserves the previous same-section body under a `concurrent-edit reconcile` block only when the section contains a marker at or after that timestamp. Markers without timestamps are preserved conservatively.

The first implementation keeps parsing deliberately simple. It recognizes adjacent bullet pairs:

```markdown
- Situation: release readiness
- Note: verify installability before publishing
```

## Tattoos

Tattoos are promoted lessons. A tattoo should be broader and more durable than the original situation that produced it. The package stores them in `tattoos.md` and includes them in recall ranking.

## Sessions

Sessions are small Markdown save records in `memento/sessions/`. Agents should reserve a session id with `new-id` instead of inventing one by hand, then write one `session-add` record for the work they completed.

Full command shape:

```text
memento-tattoo --root <path> --agent <agent_id> session-add --sess <sess_id> --date "2026-06-17 18:24" --topics "memento-oss,multi-agent" --significance medium --accomplished "Published docs polish" --started "none" --pending "none" --insights "none" --files "README.md; templates/AGENTS.md"
```

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

## Checked Retrieval

When adding a `correction` or `reflection` note, the package first ranks existing notes for the new situation. It then records whether the system found a strong existing cover or whether the situation appears new.

This makes repeated correction visible. If the same lesson was already present but did not fire, that is not just a new note; it is evidence that the retrieval trigger may need repair.

## Retention Log

`retention_log.jsonl` is append-only. Each checked note write records:

- timestamp
- session id
- note kind
- situation
- written note id
- ranked candidates
- suggested decision
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
