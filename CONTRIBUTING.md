# Contributing

Thanks for taking a look at `memento-tattoo`.

This project is early and intentionally small. The useful contribution shape is usually:

- a failing test for a concrete recall, retention, CLI, or packaging issue
- a small fix that keeps the file-based model understandable
- documentation that makes first-run usage clearer

Report a suspected vulnerability privately, as described in [SECURITY.md](SECURITY.md), not in a public issue.

When reporting a bug, include the package version, Python version, and, for a source checkout, the output of `git rev-parse HEAD`. Include a small synthetic reproduction and the observed result.

## Local setup

Use Python 3.11 or newer. The examples below use Python 3.12; use `python3.11` if that is the supported interpreter on your system.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest -q
```

Build artifacts:

```bash
.venv/bin/python -m pip install build
.venv/bin/python -m build
```

## Agent templates

`templates/PROTOCOL.md` and `templates/memento-stub.md` are the readable sources. `init` installs them from byte-identical copies in `src/memento_tattoo/templates/`, which ship as package data. After editing either template, copy it over its package copy; a test fails when the two differ. The pattern contract and `templates/AGENTS.md` quote the stub, and a test checks those quotes too.

## Design boundaries

- Keep runtime dependencies at zero unless there is a strong reason.
- Keep storage as Markdown plus JSONL.
- Avoid hosted services, databases, vector stores, and background daemons in the core package.
- Prefer readable behavior over clever ranking.
- Do not add organization-specific, credential-bearing, or local-machine examples.
