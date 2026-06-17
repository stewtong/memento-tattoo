# Why memento-tattoo Exists

Most agent memory remembers events: what happened, what got said, which files changed. That is useful, but it is not the failure mode that kept bothering me.

The failure mode was re-teaching the same lesson. The agent could have context and still miss the durable rule that should have changed its next action.

`memento-tattoo` is built around recall of lessons instead of recall of events.

The model is the film: notes for fast captures, project context for the annotated middle layer, and tattoos for the facts that should be visible before acting. The software version adds one thing the film does not have: a retention loop. When a correction happens, the system checks whether an existing lesson should have fired. If the same lesson recurs, that recurrence becomes evidence.

The storage is intentionally plain text. Markdown notes and a JSONL log are easy to inspect, edit, diff, and copy. There is no database to migrate, no service to keep alive, and no embedding index to explain before a human can understand what the agent believes it learned.

That choice does not make concurrency disappear. Multiple writers can still touch the same root. The package handles the short write section with an advisory file lock and content-derived markers, so replayed writes are no-ops and each saved block carries provenance.

The important claim is narrow: this is a small reference implementation for making corrected lessons stick. It is not a general memory benchmark system, not a hosted memory platform, and not a promise that file-based recall beats every other approach. It is a working shape for a specific loop: capture the lesson, check whether it should already have fired, log the outcome, and promote only the lessons that prove broad enough to deserve permanence.
