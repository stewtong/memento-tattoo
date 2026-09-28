"""Mixed-version round trip (plan section 7): unknown fields survive a client.

Drives any memento-tattoo installation through its CLI only, so the same
script checks the current code and an older release. A note carrying fields
the older client does not know (``Why:``, ``paths:``, and a placeholder
future field) is amended with its complete body and then rotated into the
archive; every field line must come through byte for byte.

Usage: python bench/compat/roundtrip.py --python /path/to/python [--keep DIR]
Exit status is nonzero on any failure.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FIELDS = [
    "Why: The billing schema has triggers the ORM does not model.",
    "paths: packages/billing/**, packages/ledger/*.sql",
    "x-future: a field no current client knows",
]
BODY = "\n".join(["Situation: running a migration on billing", "Note: run it against a snapshot first."] + FIELDS)
AMENDED = BODY.replace("run it against a snapshot first.", "run it against a restored snapshot first.")


def cli(python: str, root: Path, *args: str) -> str:
    proc = subprocess.run([python, "-m", "memento_tattoo", "--root", str(root), *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{args[0]} exited {proc.returncode}: {proc.stdout[-300:]} {proc.stderr[-300:]}")
    return proc.stdout


def run(python: str, root: Path) -> list[str]:
    failures = []
    root.mkdir(parents=True, exist_ok=True)
    (root / "notes.md").write_text("", encoding="utf-8")
    (root / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    version = subprocess.run([python, "-m", "memento_tattoo", "--version"], capture_output=True, text=True).stdout.strip()

    added = cli(python, root, "note-add", "--sess", "sess_compat", "--kind", "seed", BODY)
    note_id = re.search(r"delta:(\S+)", added).group(1)
    record = json.loads(cli(python, root, "entry-read", "--id", note_id, "--source", "notes.md"))
    cli(python, root, "note-amend", "--id", note_id, "--source", "notes.md", "--expected-sha256", record["sha256"],
        "--sess", "sess_compat", "--author", "compat", "--reason", "wording", "--evidence", "compat test", AMENDED)
    hot = (root / "notes.md").read_text(encoding="utf-8")
    for line in FIELDS + ["Note: run it against a restored snapshot first."]:
        if line not in hot.split("<!-- memento-history", 1)[0]:
            failures.append(f"after amend, active body lost: {line!r}")

    block_before = hot[hot.index(f"<!-- delta:{note_id}"):]
    filler = "Situation: filler note for rotation\nNote: " + "x" * 900
    for i in range(40):
        cli(python, root, "note-add", "--sess", f"sess_fill{i:02d}", "--kind", "seed", filler + f" {i}")
    archive_path = root / "notes_archive.md"
    archive = archive_path.read_text(encoding="utf-8") if archive_path.exists() else ""
    if f"<!-- delta:{note_id}" not in archive:
        failures.append("rotation did not move the note to the archive")
    else:
        start = archive.index(f"<!-- delta:{note_id}")
        moved = archive[start:start + len(block_before.rstrip())]
        if moved != block_before.rstrip():
            failures.append("rotated block differs from the hot block byte for byte")
    print(json.dumps({"client": version or python, "failures": failures}))
    return failures


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--keep", type=Path)
    args = parser.parse_args(argv)
    if args.keep:
        return 1 if run(args.python, args.keep) else 0
    with tempfile.TemporaryDirectory(prefix="memento-compat-") as tmp:
        return 1 if run(args.python, Path(tmp) / "memento") else 0


if __name__ == "__main__":
    raise SystemExit(main())
