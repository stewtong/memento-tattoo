<!-- register: worked example | reader: repo owners adopting memento | consumed: copied and adapted into a repo's instruction file -->

# Example AGENTS.md

This is a sample instruction file for a small monorepo that has adopted memento. The `## Memory (memento)` block is the part to copy; the rest shows where a repo's own rules sit beside it. The memory block stays short because it loads every session. The procedure it points to, `memento/PROTOCOL.md`, is read only when a correction, a recognized situation or "save work" calls for it. Run `memento-tattoo init` to create `memento/PROTOCOL.md` and print the block, or copy both from this package's `templates/` directory.

## Repository

- Packages live under `packages/`. Each has its own tests, run with `make test PKG=<name>`.
- Generated clients under `packages/*/gen/` are rebuilt by `make generate`; edit the schema, not the output.
- Open one pull request per package change unless a rename spans packages.

## Memory (memento)
- At session start, read memento/tattoos.md down to its "## Scoped" heading, or to the end if it has none. Each tattoo is an approved rule that states when it applies and why.
- When working under a directory, read the "## Current state" (or "## State") section of the nearest memory.md, walking up to the repo root.
- Before editing a file, also read the entries under "## Scoped" in memento/tattoos.md whose paths: glob matches it.
- When the user corrects you, when you recognize the situation of a past lesson, or when the user says "save work", read memento/PROTOCOL.md and follow the matching section.
- Add or change a line in memento/tattoos.md only after the user approves its exact wording.
