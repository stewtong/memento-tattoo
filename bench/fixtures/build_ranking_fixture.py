"""Build the public synthetic ranking fixture.

A 200-note store for a fictional monorepo, written to ``ranking-200/``. The
target notes and every expected result are hand-written below; only the
distractor notes are generated, from a fixed seed, to supply realistic
common-word flooding. Rerunning the script reproduces the files byte for byte.

Each case in ``expected.json`` names the behavior it guards and the ranker
it applies to (the labels are development milestones):

- ``now``: holds for the current package ranker.
- ``w4``: fails on the 0.4.0 package ranker and must pass once whole-word
  matching and BM25 land; each documents a defect being fixed. ``fixed_by``
  names the change that fixes it: ``tokenizer`` (whole words, plural folding)
  or ``bm25`` (term weighting).
- ``w7``: needs path scoping or the memory.md path chain.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "ranking-200"

# (id suffix, situation, note, why, aliases, extra fields)
TARGETS = [
    # Plural and suffix variants
    ("plural01", "running database migrations on the billing service",
     "Run migrations against a snapshot first; the billing schema has triggers that the ORM does not model.",
     "A failed migration left invoices half-written last quarter.", "schema, orm, invoices", {}),
    ("plural02", "editing retry policies for the job queue",
     "Change the policy file, not the worker defaults; workers read the policy at start and ignore later env changes.",
     "Two outages came from edits that never took effect.", "backoff, worker, queue", {}),
    ("plural03", "adding dependencies to a leaf package",
     "Declare the dependency in the leaf package manifest; the root lockfile is regenerated in CI and hand edits are lost.",
     "", "lockfile, manifest", {}),
    ("plural04", "planning a rollback of the auth service",
     "Roll back auth by redeploying the previous image; database changes in auth are forward-only.",
     "A schema downgrade once locked every user out.", "redeploy, image", {}),
    # Substring traps: the query word appears only inside longer words elsewhere
    ("substr01", "choosing the art direction for the marketing site",
     "Use the brand kit colors; the design team rejects ad hoc palettes.", "", "design, brand, palette", {}),
    ("substr02", "reading service logs during an incident",
     "Query the log index by trace ID first; grepping raw log files misses rotated segments.",
     "Rotated segments hold most of an incident's first minutes.", "trace, incident", {}),
    # Rare term among common words
    ("rare01", "agent changed the ledger rounding mode in billing",
     "Ledger rounding must stay banker's rounding; finance reconciles against it nightly.",
     "A rounding change produced a one-cent drift across 40,000 invoices.", "rounding, finance, reconcile", {}),
    ("rare02", "the agent ran the full test suite for a docs-only change",
     "For changes under docs/, run only the docs link check; the full suite takes forty minutes and proves nothing here.",
     "", "docs, link check", {}),
    # Superseded pair
    ("sup01old", "rotating the payments API key",
     "Rotate the key in the vault UI, then restart the gateway by hand.", "", "vault, gateway, secret",
     {"Superseded-by": "synth.note.sup01new"}),
    ("sup01new", "rotating the payments API key",
     "Rotate the key with the rotate-secret job; it restarts the gateway and records the rotation.",
     "Manual restarts were missed twice and left the old key live.", "vault, gateway, secret", {}),
    # Archived target
    ("arch01", "upgrading the web app's bundler major version",
     "Upgrade the bundler in a branch with the visual regression suite on; CSS ordering changes silently between majors.",
     "The last major upgrade reordered stylesheets and broke checkout.", "webpack, css, visual regression", {}),
    # Monorepo boundary (the flagship example)
    ("mono01", "changing a public function signature in a shared package",
     "Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests.",
     "A renamed export in auth broke web and billing while CI stayed green.", "api, callers, breaking change", {}),
    # Scoped notes (path scope is read in phase w7; the text is ordinary today)
    ("scope01", "editing billing webhooks",
     "Webhook handlers must be idempotent; the provider retries on any non-2xx for 72 hours.",
     "Duplicate refunds followed a handler that returned 500 after committing.", "idempotent, retries, provider",
     {"paths": "packages/billing/**"}),
    ("scope02", "editing web route handlers",
     "Route handlers must not import from packages/billing directly; go through the billing client.",
     "Direct imports bypassed the client's auth checks.", "import boundary, client",
     {"paths": "apps/web/**"}),
    ("scope03", "changing auth session lifetimes",
     "Session lifetime changes need the security review label; the mobile client caches tokens for the old lifetime.",
     "", "tokens, security review, mobile", {"paths": "packages/auth/**"}),
]

EXPECTED = [
    {"id": "plural-migration", "query": "run a migration on billing", "phase": "now",
     "top": 3, "must_include": ["synth.note.plural01"],
     "why": "A singular query finds a plural note; substring matching already does this, so it guards against regression."},
    {"id": "plural-policy", "query": "change a retry policy", "phase": "now",
     "top": 3, "must_include": ["synth.note.plural02"],
     "why": "Substring matching already finds 'policy' inside 'policy file'; kept as a regression guard."},
    {"id": "plural-dependency", "query": "add a dependency to a package", "phase": "now",
     "top": 3, "must_include": ["synth.note.plural03"],
     "why": "Found today through other terms; guards against regression."},
    {"id": "plural-query-singular-note", "query": "rollbacks", "phase": "w4", "fixed_by": "tokenizer",
     "top": 3, "must_include": ["synth.note.plural04"],
     "why": "A plural query must match a singular note, which substring matching cannot do."},
    {"id": "flood-ledger", "query": "agent run test ledger", "phase": "w4", "fixed_by": "bm25",
     "top": 1, "must_include": ["synth.note.rare01"],
     "why": "One rare term must outweigh three common ones; fixed bonuses per matched term cannot."},
    {"id": "substring-art", "query": "art", "phase": "w4", "fixed_by": "tokenizer",
     "top": 5, "must_include": ["synth.note.substr01"], "must_exclude_any_other_than": ["synth.note.substr01"],
     "why": "'art' must not match 'start', 'part' or 'restart'."},
    {"id": "substring-log", "query": "log", "phase": "w4", "fixed_by": "tokenizer",
     "top": 5, "must_include": ["synth.note.substr02"], "max_results": 3,
     "why": "'log' must not match 'catalog', 'login' or 'blog'."},
    {"id": "rare-term-ledger", "query": "agent changed rounding in the ledger", "phase": "now",
     "top": 1, "must_include": ["synth.note.rare01"],
     "why": "Rare terms ('ledger', 'rounding') must outweigh common ones ('agent', 'changed')."},
    {"id": "rare-term-docs", "query": "ran the whole test suite for a docs change", "phase": "now",
     "top": 3, "must_include": ["synth.note.rare02"],
     "why": "Common words ('test', 'run') appear in many distractors."},
    {"id": "superseded-order", "query": "rotate the payments api key", "phase": "now",
     "top": 2, "order": ["synth.note.sup01new", "synth.note.sup01old"],
     "why": "The successor must rank above the note it supersedes."},
    {"id": "archived-found", "query": "upgrade the bundler major version", "phase": "now",
     "top": 3, "must_include": ["synth.note.arch01"],
     "why": "Archived notes stay searchable."},
    {"id": "flagship-callers", "query": "rename an exported function in a shared package", "phase": "now",
     "top": 3, "must_include": ["synth.note.mono01"],
     "why": "The flagship lesson must surface for a paraphrased API change."},
    {"id": "scope-billing", "query": "handler returns an error after committing", "path": "packages/billing/src/webhooks/refund.ts",
     "phase": "w7", "top": 3, "must_include": ["synth.note.scope01"], "must_exclude": ["synth.note.scope02"],
     "why": "In-scope notes are boosted; notes scoped only to other paths are dropped."},
    {"id": "scope-web", "query": "import the billing package from a route", "path": "apps/web/routes/checkout.ts",
     "phase": "w7", "top": 3, "must_include": ["synth.note.scope02"],
     "why": "The scoped rule for apps/web applies."},
    {"id": "path-chain", "query": "anything", "path": "packages/billing/src/invoice.ts", "phase": "w7",
     "current_state_chain": ["packages/billing/memory.md", "packages/memory.md", "memory.md"],
     "why": "load --path returns each memory.md current state from nearest to the root."},
]

COMMON = ["agent", "file", "run", "test", "change", "update", "service", "package", "config", "check",
          "before", "after", "build", "deploy", "review", "branch", "error", "fix", "start", "restart",
          "part", "catalog", "login", "blog", "apart", "smart", "partial", "starting"]
TOPICS = ["cache warmup", "feature flag cleanup", "pagination cursor", "timezone handling", "image resizing",
          "email templates", "search indexing", "rate limiting", "csv export", "health checks", "cron schedule",
          "locale strings", "pdf rendering", "metrics labels", "queue depth alerts", "session storage",
          "dark mode styles", "api versioning", "file uploads", "audit trail"]
VERBS = ["adjusting", "debugging", "reviewing", "refactoring", "testing", "documenting", "migrating", "profiling"]


def distractors(n: int, seed: int = 52) -> list[tuple]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        topic = rng.choice(TOPICS)
        common = rng.sample(COMMON, 4)
        situation = f"{rng.choice(VERBS)} {topic} for the {rng.choice(['web app', 'worker', 'admin panel', 'api'])}"
        note = (f"When the agent {common[0]}s the {topic} code, {common[1]} the {common[2]} output and "
                f"{common[3]} the related {rng.choice(TOPICS)} settings before merging.")
        out.append((f"d{i:03d}", situation, note, "", ", ".join(rng.sample(COMMON, 2)), {}))
    return out


def block(item: tuple) -> str:
    suffix, situation, note, why, aliases, extra = item
    lines = [f"<!-- delta:synth.note.{suffix} -->", f"Situation: {situation}", f"Note: {note}"]
    if why:
        lines.append(f"Why: {why}")
    if aliases:
        lines.append(f"aliases: {aliases}")
    for key, value in extra.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def main() -> None:
    notes = TARGETS + distractors(200 - len(TARGETS))
    assert len(notes) == 200
    archive_ids = {"arch01"}
    hot = [n for n in notes[:20] if n[0] not in archive_ids]
    archive = [n for n in notes if n not in hot]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "notes.md").write_text("\n".join(block(n) for n in hot), encoding="utf-8")
    (OUT / "notes_archive.md").write_text("\n".join(block(n) for n in archive), encoding="utf-8")
    (OUT / "tattoos.md").write_text(
        "# Tattoos\n\n- Before changing a package's public API, search the other packages for callers; "
        "CI runs only the changed package's tests.\n", encoding="utf-8")
    chain = {
        "memory.md": "Monorepo root: apps/ and packages/, one CI job per package.",
        "packages/memory.md": "Shared packages publish on merge to main; semver is enforced by the release job.",
        "packages/billing/memory.md": "Billing is mid-migration from the legacy ledger; do not add new ledger writers.",
    }
    for rel, state in chain.items():
        path = OUT / "repo" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Project memory\n\n## Current state\n\n{state}\n", encoding="utf-8")
    (OUT / "expected.json").write_text(json.dumps(EXPECTED, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
