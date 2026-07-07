# Authoring standards: tattoos and notes

How to write the two lessons that earn a place in memory. A note is provisional and gets retrieved when its situation recurs. A tattoo is scarce and gets loaded before broad classes of work. Each has a gate. Apply it before writing.

## How to write a tattoo

A tattoo is an always-loaded rule. Every future session pays to read it, so it earns that place or it does not ship. All five gates must pass.

1. Counterfactual filter. Known at the start of the session, would it have changed the course of action here, not merely been nice to know? And would it change behavior in unrelated future sessions? The default answer is no tattoo.
2. Merge first. Search `memento/tattoos.md` for two or three keywords of the candidate. If a sibling already covers the theme, edit that line to absorb the new case instead of appending a variant. One caveat: a genuine sibling shares the action, not just the theme. Rules that sound alike but tell the agent to do different things (verify the artifact, verify the user-facing result, match the metric to the claim) are kept separate on purpose. Do not collapse distinct actions into one vague line; over-merging trades away the situational specificity that makes each one fire.
3. Domain free. No product, tool, platform, file type, or project name. If the sentence needs a specific command or config key to be true, it is a note, not a tattoo. Test: name three unrelated future domains where it fires as written.
4. Actionable. It tells the agent what to do differently (it contains the verb), not what to believe.
5. Shape. One declarative principle, short enough to load often, with at most one clause of mechanism. If you are writing a second sentence, the overflow belongs in the note that produced it, not in the tattoo.

Provenance: the delta marker names the session whose record actually contains the lesson. If you rewrote the lesson beyond what the session record says, update that record or do not stamp the marker. A marker that points at a session with no trace of the lesson is a false provenance claim, and it is checkable.

Shape on disk:
```markdown
<!-- delta:sess_example.tattoo.shortid agent=codex ts=... -->
- Before sharing a package, prove it works from the built artifact in a clean workspace.
```

## How to write a note

A note is what a future agent needs when it cold-starts a different task and hits the same situation. It is not a diary of this session. Decide it should exist before drafting.

1. Deduplicate with the ranked tool, not just a grep. Run `memento-tattoo load --query "<situation>"`, which reads the hot notes and the rotated archive and ranks them. A same-lesson hit means extend or sharpen that note, never append a near duplicate.
2. Routing test. Can you name the specific file, tool, or task that prompted the lesson, and does it only matter when you touch that thing again? Then it is project state (`memory.md`), not a note. If the note and the project record would say the same thing in different words, the note is wrong; abstract up a level or skip it.
3. Project-status check. If the draft reads as a present-tense description of what a tool or system is now, or what a phase did, it is project memory, not a note.
4. The default is no note. Most sessions should produce none.

Per-field rules:

- Situation is a moment an agent on a different task would recognize. Write it as a symptom or an intent, in the present tense: "an edit fails because the file changed since it was read"; "about to fix a bad ticket through the API". Never a project or phase label. A Situation that names one specific project can only fire inside that project, which is the tell that the note is misfiled.
- Note leads with the rule, then the instance. State the transferable imperative first, then compress the specific case to one clause of evidence. If the rule is already a tattoo, keep only the technique detail here and reference the tattoo.
- aliases are load-bearing, not decoration. Retrieval matches terms literally, with no synonym layer, so a note with no aliases becomes invisible to a paraphrased future query once it rotates to the archive. Write the aliases in the words you did not already use in the note.
- Reference, do not restate. When a note relates to another note or a tattoo, link it by id rather than re-typing the lesson. If your note narrows or replaces an older one, mark the older one superseded in the same save.

Shape on disk:
```markdown
<!-- delta:sess_example.note.shortid agent=codex ts=... -->
Situation: publishing a public repo
Note: scan examples for private names, secret values, and local paths before publishing.
aliases: oss, public, sanitize, release
review_after: 2026-12-31
```

## The line between the layers

The routing test decides the layer. A lesson you can only apply by re-touching one file or tool is project memory. A lesson that recurs across different tasks, but only when its situation shows up, is a note. A lesson that should be in front of you before broad classes of work, and that would have changed the course of a session if it had loaded early, is a tattoo candidate. Most learning stays a note. Promotion is rare by design: if everything is a tattoo, nothing is visible.
