# Public-readiness review

## Scope

Reviewed extracted `memento-tattoo` package files, tests, examples, and docs for internal references, reproducibility gaps, and public-facing claim risk.

## Publish Boundary

Target public repo: `https://github.com/stewtong/memento-tattoo`

Included in first release:

- `.github/`
- `scripts/`
- `src/`
- `tests/`
- `examples/`
- `docs/`
- `README.md`
- `pyproject.toml`
- `MANIFEST.in`
- `LICENSE`
- `CONTRIBUTING.md`
- `CHANGELOG.md`

Excluded from first release unless separately sanitized:

- `memory.md`
- `plans/`
- `research/`
- `specs/`
- local session notes or private artifacts

The publish boundary is enforced by `.gitignore` and `scripts/export_public.py`, which exports only the release surface into a clean destination.

## Layer 2 Correction

The public repo must exclude the private local `memento-oss/memory.md` file but include the framework capability for adjacent `{project}/memory.md`. Tests should prove both:

- private root-level `memory.md` is not exported
- public `examples/basic/project/memory.md` is exported

## Name And Package Posture

- Public repo/display name: `memento-tattoo`
- Python package name: `memento-tattoo`
- Import package: `memento_tattoo`
- Rationale: keeps the film hook and the promoted-lesson layer while avoiding the bare `memento` namespace.
- Distribution posture: PyPI-ready package metadata and build artifacts, but no package-index publication for the first GitHub release.

## Sanitization Scan

- Command: internal-reference string scan over `src`, `tests`, `examples`, `docs`, `README.md`, `pyproject.toml`, and `LICENSE`.
- Result: clean on 2026-06-17.

## Reproducibility

- `python3 -m pytest -q`: 36 passed on 2026-06-17.
- Python 3.12 packaging venv: source distribution and wheel built on 2026-06-17.
- Extracted source distribution smoke: 36 passed on 2026-06-17.
- `python scripts/export_public.py .tmp/public-export-layer2-final-*`: exported the clean public GitHub tree with no excluded local artifacts on 2026-06-17.
- `.tmp/install-smoke/bin/memento-tattoo --root examples/basic/memento doctor`: passed on 2026-06-17.
- `.tmp/install-smoke/bin/memento-tattoo --root examples/basic/memento garden --today 2026-06-17`: passed on 2026-06-17.
- `.tmp/install-smoke/bin/memento-tattoo --root examples/basic/memento load --query "sanitize public release"`: returned `sess_demo.note.11111111` on 2026-06-17.
- Staged first-run smoke under `.tmp/staged-workspace-final/memento`: created project context, seed notes, a tattoo, and one checked reflection from the built wheel; `doctor`, `garden`, and recall queries passed on 2026-06-17.
- Installed wheel smoke: `project-edit`, `doctor --project`, and `load --project` passed with adjacent project `memory.md` on 2026-06-17.

## Claim Boundaries

- Positioning is recall-of-lessons, not recall-of-events.
- No claim is made about benchmark superiority.
- No adoption, production-readiness, security, or reliability claims beyond the tested local-file behavior.
