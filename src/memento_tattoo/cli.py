from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .doctor import run_doctor
from .garden import build_digest
from ._time import now_iso
from .recall import render_ranked_notes
from .write_through import note_add, project_edit, tattoo_add


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="memento-tattoo", description="File-based lesson-retention memory for LLM agents.")
    parser.add_argument("--root", default=None, help="memento root; defaults to ./memento")
    subparsers = parser.add_subparsers(dest="command", required=True)

    note = subparsers.add_parser("note-add", help="append a checked lesson note")
    note.add_argument("--sess", required=True)
    note.add_argument("--kind", choices=["correction", "reflection", "seed"], default="reflection")
    note.add_argument("text")

    tattoo = subparsers.add_parser("tattoo-add", help="append a promoted lesson")
    tattoo.add_argument("--sess", required=True)
    tattoo.add_argument("text")

    load = subparsers.add_parser("load", help="rank lessons for a query")
    load.add_argument("--query", required=True)
    load.add_argument("--limit", type=int, default=8)
    load.add_argument("--project", action="append", default=[], help="project directory whose memory.md should participate in recall")

    project = subparsers.add_parser("project-edit", help="update adjacent project memory.md")
    project.add_argument("--project", required=True, help="project directory that owns memory.md")
    project.add_argument("--sess", required=True)
    project.add_argument("--section", default="## State")
    project.add_argument("--flow-start", default=None)
    project.add_argument("text")

    garden = subparsers.add_parser("garden", help="emit a read-only gardening digest")
    garden.add_argument("--today", required=False, default=None)
    garden.add_argument("--promote-threshold", type=int, default=2)

    doctor = subparsers.add_parser("doctor", help="run root health checks")
    doctor.add_argument("--project", action="append", default=[], help="project directory whose memory.md should be checked")

    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path.cwd() / "memento"

    if args.command == "note-add":
        applied, marker = note_add(args.text, sess=args.sess, root=root, kind=args.kind)
        print(f"{'applied' if applied else 'skipped (already applied)'} {marker}")
        return 0

    if args.command == "tattoo-add":
        applied, marker = tattoo_add(args.text, sess=args.sess, root=root)
        print(f"{'applied' if applied else 'skipped (already applied)'} {marker}")
        return 0

    if args.command == "project-edit":
        applied, marker = project_edit(
            args.text,
            sess=args.sess,
            root=root,
            project=Path(args.project),
            section=args.section,
            flow_start=args.flow_start,
        )
        print(f"{'applied' if applied else 'skipped (already applied)'} {marker}")
        return 0

    if args.command == "load":
        print(render_ranked_notes(args.query, root=root, limit=args.limit, projects=[Path(item) for item in args.project]))
        return 0

    if args.command == "garden":
        print(build_digest(root=root, today=args.today or now_iso()[:10], promote_threshold=args.promote_threshold))
        return 0

    if args.command == "doctor":
        ok, output = run_doctor(root, projects=[Path(item) for item in args.project])
        print(output)
        return 0 if ok else 1

    parser.error(f"unknown command {args.command}")
    return 2
