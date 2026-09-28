<!-- delta:sess_demo.note.11111111 -->
Situation: changing a function signature or name in a shared package's public API
Note: search every other package for callers before changing a package's public API, and update them in the same change.
Why: CI runs only the changed package's tests, so a broken caller in another package stays green until it ships.
aliases: monorepo, breaking change, rename, callers, ci, cross-package
review_after: 2026-12-31

<!-- delta:sess_demo.note.22222222 -->
Situation: an API change passed CI and then broke another package after merge
Note: check whether an existing caller-search lesson should have fired before adding a duplicate note; sharpen its situation so it matches the next API change.
Why: a second note with the same lesson splits future matches, and neither copy gets its trigger repaired.
aliases: correction, repeat, duplicate, retention, downstream, breakage

<!-- delta:sess_demo.note.44444444 -->
Situation: claiming a code change is complete
Note: Before claiming work is complete, run the command that proves it and read the output.
Why: an unverified completion claim hands broken work to the reviewer.
aliases: tests, verification, done, finished
