# Contributing

Thanks for taking a look at `memento-tattoo`.

This project is early and intentionally small. The useful contribution shape is usually:

- a failing test for a concrete recall, retention, CLI, or packaging issue
- a small fix that keeps the file-based model understandable
- documentation that makes first-run usage clearer

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

## Design boundaries

- Keep runtime dependencies at zero unless there is a strong reason.
- Keep storage as Markdown plus JSONL.
- Avoid hosted services, databases, vector stores, and background daemons in the core package.
- Prefer readable behavior over clever ranking.
- Do not add organization-specific, credential-bearing, or local-machine examples.
