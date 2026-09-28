<!-- register: agent procedure | reader: a coding agent that was just triggered | consumed: read on demand, one section at a time -->

# Memento protocol

The memory block in the repo's instruction file sends you here when the user corrects you, when you recognize the situation of a past lesson, or when the user says "save work". The user may also send you here to bring in rules they already keep elsewhere. Read the section for that trigger and the formats it uses. How the tool counts and stores records is in the [concepts reference](https://github.com/stewtong/memento-tattoo/blob/main/docs/concepts.md); following this file does not require it.

Paths assume the memory root is `memento/` at the repo root; if the repo put it elsewhere, use that path.

## Modes

The repo uses one of two modes. Check which before writing anything.

- **Plain-file mode.** You search and edit the Markdown files directly. Nothing coordinates writers, so work as the only writer and read back every change, because an unnoticed partial write is how plain files lose data.
- **CLI mode.** The `memento-tattoo` command is installed; pass the repo's memory root (`--root memento`). Its commands lock, mark provenance and check their writes, so do not hand-edit a file it manages while another session may be writing.

Sessions, archives, the registry and automation are optional. If the repo has not adopted one, do not create it or mention it.

## Files

- `memory.md` beside the work: project decisions and a short `## Current state`. Facts about one project live here, close to the code they explain.
- `memento/notes.md`: provisional lessons, usually from corrections. `memento/notes_archive.md` holds older notes when notes rotate; it is still searched.
- `memento/tattoos.md`: the few approved rules loaded at every session start.
- `memento/retention_log.jsonl`: one JSON object per line, recording what the search found each time a correction note was written. Append only; never rewrite past lines, because the history is the evidence.

## When the user corrects you

1. Name the situation in words a future agent on a different task would recognize: a symptom or an intent, not a project label. The situation is what retrieval matches on.
2. Search for a lesson that should already have applied: `memento/tattoos.md`, then notes. In plain-file mode, search `notes.md` and `notes_archive.md` for situation words, lesson words and likely synonyms. In CLI mode, run `memento-tattoo --root memento load --query "<situation and action>"`, which ranks both note stores and tattoos.
3. If a note already covers the lesson, repair that note (see [Revising a note](#revising-a-note)) instead of adding a near duplicate. Two notes with one lesson split future matches and neither gets fixed.
4. Otherwise add a note in the [note format](#note-format). Include `Why:` when you know the cost or mechanism behind the lesson, because the reason is how a later reader decides whether a new case is covered.
5. Record what the search found. After repairing an existing note (step 3), do not add a note to record the miss: put the observation, meaning which lesson should have applied and the task evidence, in the amendment's reason and evidence, since the CLI has no standalone command for observations. For a new note (step 4):
   - In CLI mode, `memento-tattoo --root memento note-add --sess <session_id> --kind correction "<note body>"` writes the note and appends the retention event. When you know better than the classifier, pass `--decision` and `--covered-note-id`. Do not append a second event by hand.
   - In plain-file mode, save the note, then append one JSON object to `retention_log.jsonl` with a timestamp, a session or source reference, the note ID, the decision, `"decision_source": "author"`, and the covering note's ID when there is one. Read back both files.
6. Choose the decision from what you observed, not from word overlap alone:
   - `new`: no existing lesson covered the situation.
   - `related`: a search found a possible covering lesson, and you have not judged whether it should have fired.
   - `existing-missed`: a relevant lesson existed and did not prevent the mistake. Record it only when you can say which lesson and why it should have applied; similarity alone is `related`.
   - `applied`: a lesson was used and helped.
   - `overapplied`: a lesson was applied where it did not fit and caused harm or wasted work.

A miss you record is a reason to sharpen that lesson's situation or aliases, since it failed to surface when needed.

## When you recognize a past situation

Before acting on a task whose situation you recognize, read the matching lessons, but only the ones that could change your next action. Loading everything costs attention and makes loosely related rules look binding.

- Read the `## Current state` of the nearest `memory.md` together with lessons about the action you are about to take. In CLI mode, `memento-tattoo --root memento load --query "<situation and action>" --project <directory>` returns both.
- A match suggests relevance. Current user instructions and the source files decide what applies; a lesson applies only inside its stated situation.
- Previews can be clipped. Before relying on an exception or qualification, read the complete entry: in CLI mode, run the `read_reference` command the match prints (`entry-read`).
- A search result is bounded. Not finding a lesson does not show that none exists; widen the search when the decision is consequential or the evidence conflicts.
- A newer summary does not replace an owner's decision just by being newer. Superseded entries stay labelled; follow the successor.

## When the user says "save work"

Do a judgment pass before writing anything. Ask one question of the session: what from it should change a future action? Then decide:

- whether project state changed enough to update `memory.md`;
- whether a correction or reflection should become a note, or should strengthen an existing note;
- whether the repo keeps session records and one is due;
- whether one lesson is strong enough to propose as a tattoo.

Most sessions update project state and produce no new note. Do not dump the transcript; memory holds what should change behavior.

The strongest material is what the repo cannot cheaply reconstruct: why an option was rejected, the basis of a decision, a technique that worked, and the conditions and exceptions attached to a correction. Keep successful approaches as well as corrections.

In CLI mode, reserve a session ID with `new-id`. If the repo keeps session records, draft one JSON spec and run `save-commit --spec <file>` once; it writes the session, note, project and registry changes through the same checked commands, and it requires a session record. If the repo does not keep session records, write each surface with its own command instead: `project-edit` for `memory.md` and `note-add` for a note. The spec format is in the [save walkthrough](https://github.com/stewtong/memento-tattoo/blob/main/docs/save-work.md). Surface any tattoo candidate separately.

## When the user asks you to bring in existing rules

The user may already keep rules and lessons elsewhere: an `AGENTS.md`, `CLAUDE.md` or rules folder, or a harness's own memory directory. Bringing them in is a one-time review of that source, done only when the user asks.

1. Read the source the user names. Do not edit or delete it; it stays in force until the user changes it.
2. Sort each rule or passage by where it belongs:
   - Build commands, repo layout and conventions every session needs stay in the instruction file.
   - Current project status or a recorded decision goes to `memory.md`.
   - A lesson tied to a situation, such as a past mistake, a trap in the codebase or a technique that worked, becomes a candidate note.
   - A lesson that also clears the [tattoo bar](#proposing-a-tattoo) becomes a candidate note plus a separate tattoo proposal.
   - A lesson an existing note or tattoo already covers is skipped; name the covering entry. Search as in step 2 of [When the user corrects you](#when-the-user-corrects-you).
   - General advice that would change no action is skipped.
3. Show the user the list before writing anything: for each candidate, its source line, where it would go, and the proposed wording in the [note format](#note-format). Rewrite each one as a situation and a rule, because a copied instruction without a situation rarely surfaces in a search. Keep the source's reason as `Why:` when it gives one.
4. Write only the items the user approves. In CLI mode, reserve a session ID with `new-id` and add each note with `memento-tattoo --root memento note-add --sess <session_id> --kind seed "<note body>"`. The `seed` kind records no retention event, because an imported rule is not an observed correction. In plain-file mode, add the notes without retention events. Read back what you wrote.
5. Propose tattoos through [Proposing a tattoo](#proposing-a-tattoo). An import approves nothing on its own.
6. Tell the user which rules now exist in both places. Two live copies drift apart, so the user decides which one to keep; do not remove the original yourself.

## Proposing a tattoo

A tattoo is loaded at every session start, so each one costs every future session. Propose one only when the answer to this is yes:

```text
If this had been loaded at the beginning of the session, would it have dramatically improved the course of action?
```

and the lesson has recurred, holds across unrelated sessions, changes behavior rather than adding information, reaches beyond the file or project that produced it, and fits in one compact rule with its reason.

Before proposing, search `memento/tattoos.md` for a sibling that already covers the same action; if one exists, propose revised wording for it instead. Keep rules separate when they sound alike but tell the agent to do different things. Write the rule for the situation where it helps and keep its necessary exceptions, so a local correction does not become a universal restriction.

At session end, show the user the strongest candidate, its exact wording, and why it clears the bar. Then:

- **Approved wording:** for a new rule, add it to `memento/tattoos.md` (in CLI mode, `tattoo-add`). For a revision, replace the existing rule's text in place, keeping its marker line if it has one, and read the file back; `tattoo-add` only appends, so using it for a revision leaves both versions active. Nothing else authorizes a tattoo.
- **Rejected:** keep any useful lesson as an ordinary note, and drop the candidate.
- **No answer:** park the candidate somewhere durable that is not loaded at startup, such as a tagged note or a session record, for later review. Silence is never approval. A parked candidate is evidence, not an instruction.

A proposal repeated across sessions is still a proposal. Changing an approved tattoo's meaning or scope needs the same explicit approval as adding one.

## Revising a note

You may capture and revise ordinary working notes when you have evidence, keeping their history visible. An owner's decision keeps its authority; do not rewrite it into something else.

- In CLI mode, read the complete note first: `entry-read --id <note_id> --source <store>`. Keep the `sha256` it returns and pass it to `note-amend` with the complete new body, your session ID, author, reason and an evidence reference. The note keeps its ID and creation marker, and the previous body is stored with the change. If the digest is stale, someone changed the note since you read it: reread and reconcile, never guess a digest. Read back the result and search for it to confirm it still surfaces for its situation.
- In plain-file mode, edit the block in place, keep its marker line, and keep the previous wording visible (for example, under a dated "Previously:" line). Read the file back.
- Do not add a second note just to edit the first.
- In CLI mode, `entry-read --format markdown` shows a note's earlier versions.
- An edit is not evidence that a lesson was applied or missed. Record an observation separately, with its source, and only when task evidence supports it; the CLI has no standalone command for observations.

## Note format

```markdown
<!-- delta:sess_example.note.shortid agent=codex ts=2026-06-17T18:24:58Z -->
Situation: an API change passes CI but breaks another package after merge
Note: search every other package for callers before changing a package's public API.
Why: CI runs only the changed package's tests, so a broken caller elsewhere stays green until release.
aliases: monorepo, breaking change, rename, signature, callers
review_after: 2026-12-31
```

- `Situation:` a moment an agent on a different task would recognize.
- `Note:` the rule first, then at most one clause of the specific case.
- `Why:` optional. One or two sentences naming the cost or mechanism. Leave it out rather than write filler.
- `aliases:` query words a future search might use that the situation and note do not already contain.
- `review_after:` optional date for a later look.
- The marker line identifies the note. In CLI mode the command writes it. In plain-file mode, write a unique ID and never change it afterward, because other notes link to it.

Link a related note or tattoo by its ID instead of restating it. Write a note when a correction could recur, when a task teaches a reusable technique, or when an existing lesson needs a sharper trigger. Do not write one for a transcript, a one-off fact (that is project state), a private detail that would be unsafe as a general lesson, or a vague preference that changes no action.

## Tattoo format

```markdown
<!-- delta:sess_example.tattoo.shortid agent=codex ts=2026-06-17T18:24:58Z -->
- Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests.
```

Shape: `<action with its trigger>; <reason clause>.` The trigger says when the rule applies, and the reason lets a reader tell whether an unstated case is covered. A rule without a reason cannot be reviewed for fit later, because nobody can check whether the reason still holds. Keep supporting evidence in the linked note.

A rule that applies only to some files goes under a `## Scoped` heading at the end of `tattoos.md`, with an indented `paths:` line holding a glob:

```markdown
## Scoped

<!-- delta:sess_example.tattoo.shortid2 agent=codex ts=2026-06-17T18:24:58Z -->
- Before editing a migration, make it reversible; the deploy rolls back on failure.
  paths: db/migrations/**
```

Rules above the heading load at session start; a scoped rule is read when you edit a file its glob matches. The CLI does not parse `paths:` yet, so you match the glob yourself. `tattoo-add` appends to the end of the file, so after adding an unscoped rule to a file that has a `## Scoped` heading, move it above the heading.

## Project memory

Update `memory.md` when a durable decision is made, the current status changes, or you learn a constraint a future agent should not have to rediscover. Keep `## Current state` short and current, and keep history below it. Facts about one project stay here; they become a tattoo only if they turn into a general operating lesson.

In CLI mode, `project-edit --project <directory> --sess <session_id> --section "## Current state" --replace "<body>"` rewrites the current-state snapshot, and `--append` adds to an accumulating section such as a worklog. The default mode refuses to drop another writer's entries.

## Several agents in one repo

Plain files work best with one writer at a time. When several sessions may write to the same memory root, use the CLI:

- Set `MEMENTO_AGENT` (or pass `--agent`) so each write records who made it.
- Reserve every session ID with `new-id`; never invent one, because two sessions could pick the same ID.
- Use `save-commit` when one session writes several files.
- For the optional registry, queue changes with `registry-queue` and apply them with `drain`. When updating an entry, pass the exact line you read as the expected line, or an empty string when the entry was absent; a stale draft then fails instead of overwriting newer work. If `drain` cannot get the lock, leave the queued change for a later drain.
- Keep the receipts and archives the CLI writes. Retries depend on them.

## Maintenance

Maintenance follows the repo's own cadence, not every save. Report deferred maintenance as deferred.

- Search `notes.md` and `notes_archive.md` together; archiving must not hide a lesson.
- Repair aliases deliberately when coverage is low. Never generate them automatically.
- Review tattoos when the set grows past the repo's thresholds (the defaults start at 25 tattoos, 7,168 bytes, or 300 characters for one tattoo). Crossing a threshold starts a keep, demote, merge or cut review with the user. It never authorizes removing a tattoo on your own.
- Sparse citations alone do not justify cutting a rare safeguard that matters when it fires.
- If the repo archives session records, keep their IDs stable, preview the exact moves, check for collisions, and never archive while another writer may be active unless a lock serializes writes.
