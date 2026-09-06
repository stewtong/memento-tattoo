# Why memento-tattoo Exists

I kept re-teaching the same lesson. An agent could retain what happened in a session and still miss the rule that should have changed its next action.

`memento-tattoo` stores lessons for later retrieval alongside project state. Its model comes from the film: notes for quick observations, project context beside the work it explains, and tattoos for the few rules that should be visible before acting.

When a correction or reflection is saved, the reference CLI searches for possible covering lessons and records `new` or `related`. An author can separately record evidence that a lesson was missed, applied usefully, or applied unnecessarily. Similarity alone does not establish any of those outcomes.

Markdown notes and a JSONL log are easy to inspect, edit, diff, and copy. There is no database to migrate, no service to keep alive, and no embedding index to interpret before a human can read what the agent saved.

Multiple writers can still touch the same root. The package coordinates short writes with an advisory file lock and uses content-derived markers to deduplicate supported identical retries. A retry may repair an interrupted write or reject an operation whose state has been superseded. See the [save and retry limits](concepts.md#retry-saves-without-restoring-old-state).

The reference implementation supports capturing a lesson, retrieving candidates, recording judgments with provenance, and proposing recurring lessons for promotion. Promotion requires a broad behavioral lesson and the user's approval. The included evaluation tests cover detection; it does not establish behavioral improvement, full agent save latency, or superiority over other memory approaches.
