<!-- register: authoring reference | reader: agent authors | consumed: lesson review -->

# Authoring standards: tattoos and notes

How to write the two lessons that earn a place in memory. A note is provisional and gets retrieved when its situation recurs. A tattoo is scarce and gets loaded before broad classes of work.

## How to write a tattoo

A tattoo is an always-loaded rule. Every future session pays to read it, so it earns that place or it does not ship. All five gates must pass.

1. Recurrence and counterfactual filter. The lesson must have recurred. Had it been loaded at the beginning of the session, would it have dramatically improved the course of action? Would it change behavior in unrelated future sessions? A one-off insight or a merely useful reminder stays a note.
2. Merge first. Search `memento/tattoos.md` for two or three keywords of the candidate. If a sibling already covers the theme, propose revised wording that absorbs the new case. Apply the revision only after the user explicitly approves it. One caveat: a genuine sibling shares the action, not just the theme. Rules that sound alike but tell the agent to do different things (verify the artifact, verify the user-facing result, match the metric to the claim) are kept separate on purpose. Do not collapse distinct actions into one vague line; over-merging trades away the situational specificity that makes each one fire.
3. Scope. The lesson must reach beyond the narrow project or file that produced it. State the situation where the action helps. Tool-specific techniques usually belong in notes. Preserve necessary exceptions and generalize only as far as the evidence supports. A local correction cannot create a universal restriction or new approval requirement.
4. Actionable. It tells the agent what to do differently (it contains the verb), not what to believe.
5. Shape. Write `<action with its trigger>; <reason clause>.` The trigger is the condition under which the action helps; the reason is the cost or mechanism the reader cannot see. Keep the action concise while retaining the condition and exceptions needed to apply it correctly. Supporting evidence belongs in the linked note. Do not remove a necessary qualification to meet a sentence or character target.

A rule without a reason cannot be reviewed for fit later: a reviewer checks whether the reason still holds for the current repo and models, and without one the only review signal is age. The same holds for a note's `Why:`.

Provenance: the delta marker names the session whose record actually contains the lesson. If you rewrote the lesson beyond what the session record says, update that record or do not stamp the marker. A marker that points at a session with no trace of the lesson is a false provenance claim, and it is checkable.

Shape on disk:
```markdown
<!-- delta:sess_example.tattoo.shortid agent=codex ts=... -->
- Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests.
```

## How to write a note

A note is what a future agent needs when it cold-starts a different task and hits the same situation. It is not a diary of this session. Decide it should exist before drafting.

1. Search before adding. With the CLI, run `memento-tattoo load --query "<situation>"`, which ranks hot and archived notes. In plain-file mode, search both stores using situation, lesson, and alias terms. A same-lesson hit means extend or sharpen that note, never append a near duplicate.
2. Routing test. Can you name the specific file, tool, or task that prompted the lesson, and does it only matter when you touch that thing again? Then it is project state (`memory.md`), not a note. If the note and the project record would say the same thing in different words, the note is wrong; abstract up a level or skip it.
3. Project-status check. If the draft reads as a present-tense description of what a tool or system is now, or what a phase did, it is project memory, not a note.
4. The default is no note. Most sessions should produce none.

Per-field rules:

- Situation is a moment an agent on a different task would recognize. Write it as a symptom or an intent, in the present tense: "an edit fails because the file changed since it was read"; "about to fix a bad ticket through the API". Never a project or phase label. A Situation that names one specific project can only fire inside that project, which is the tell that the note is misfiled.
- Note leads with the rule, then the instance. State the transferable imperative first, then compress the specific case to one clause of evidence. If the rule is already a tattoo, keep only the technique detail here and reference the tattoo.
- Why is optional. When you know the cost or mechanism behind the lesson, state it in one or two sentences: "CI runs only the changed package's tests, so a broken caller elsewhere stays green." Leave it out rather than write a filler reason.
- aliases add query vocabulary that is absent from the situation and lesson. Retrieval scores situation, lesson, aliases, and tags in both hot and archived stores. Write aliases using likely query words the note does not already contain. Archiving does not make an unaliased note invisible.
- Reference, do not restate. When a note relates to another note or a tattoo, link it by id rather than re-typing the lesson. If your note narrows or replaces an older one, mark the older one superseded in the same save.

Shape on disk:
```markdown
<!-- delta:sess_example.note.shortid agent=codex ts=... -->
Situation: publishing a public repo
Note: scan examples for private names, secret values, and local paths before publishing.
Why: a published file stays in forks and caches after it is deleted.
aliases: oss, public, sanitize, release
review_after: 2026-12-31
```

## The line between the layers

The routing test decides the layer. A lesson you can only apply by re-touching one file or tool is project memory. A lesson that recurs across different tasks, but only when its situation shows up, is a note. A lesson that should be in front of you before broad classes of work, and that has recurred and would have dramatically improved a session if it had loaded early, is a tattoo candidate. Most learning stays a note. Promotion is rare by design: if everything is a tattoo, nothing is visible.
