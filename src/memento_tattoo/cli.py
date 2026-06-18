from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--agent", default=None, help="agent id for provenance; defaults to MEMENTO_AGENT or unknown")
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

    subparsers.add_parser("new-id", help="generate and reserve a collision-safe session id")

    session = subparsers.add_parser("session-add", help="write an idempotent session record")
    session.add_argument("--sess", required=True)
    session.add_argument("--date", required=True)
    session.add_argument("--topics", default="")
    session.add_argument("--significance", choices=["low", "medium", "high"], default="low")
    session.add_argument("--accomplished", required=True)
    session.add_argument("--started", default="none.")
    session.add_argument("--pending", default="none.")
    session.add_argument("--insights", default="none.")
    session.add_argument("--files", default="")

    rebuild_parser = subparsers.add_parser("rebuild", help="rebuild generated session indexes")
    rebuild_parser.add_argument("--check", action="store_true")

    registry = subparsers.add_parser("registry-queue", help="queue a registry delta")
    registry.add_argument("--sess", required=True)
    registry.add_argument("--action", choices=["add", "update", "archive"], required=True)
    registry.add_argument("--slug", required=True)
    registry.add_argument("line")

    drain_parser = subparsers.add_parser("drain", help="drain queued registry deltas")
    drain_parser.add_argument("--timeout", type=float, default=10.0)

    save = subparsers.add_parser("save-commit", help="run a validated multi-surface save from a JSON spec")
    save.add_argument("--spec", required=True)
    save.add_argument("--allow-deferred-drain", action="store_true")

    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path.cwd() / "memento"

    if args.command == "note-add":
        applied, marker = note_add(args.text, sess=args.sess, root=root, kind=args.kind, agent=args.agent)
        print(f"{'applied' if applied else 'skipped (already applied)'} {marker}")
        return 0

    if args.command == "tattoo-add":
        applied, marker = tattoo_add(args.text, sess=args.sess, root=root, agent=args.agent)
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
            agent=args.agent,
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

    if args.command == "new-id":
        from .new_id import generate_session_id

        print(generate_session_id(root))
        return 0

    if args.command == "session-add":
        from .new_id import prune_reservations
        from .session_store import render_session_block, write_session_block

        block = render_session_block(
            args.sess,
            date=args.date,
            agent=args.agent,
            topics=_csv_arg(args.topics),
            significance=args.significance,
            accomplished=args.accomplished,
            started=args.started,
            pending=args.pending,
            insights=args.insights,
            files=_semi_arg(args.files),
        )
        path = write_session_block(root, block, args.sess)
        prune_reservations(root)
        print(f"applied {path}")
        return 0

    if args.command == "rebuild":
        from .rebuild import rebuild

        ok, output = rebuild(root, check=args.check)
        print(output)
        return 0 if ok else 1

    if args.command == "registry-queue":
        from .registry import registry_queue

        path = registry_queue(args.sess, args.action, args.slug, args.line, root, agent=args.agent)
        print(f"queued {path}")
        return 0

    if args.command == "drain":
        from .registry import drain

        result = drain(root, timeout=args.timeout)
        print(result.render())
        return 0 if result.ok else 1

    if args.command == "save-commit":
        from .save_commit import save_commit

        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        result = save_commit(spec, root=root, allow_deferred_drain=args.allow_deferred_drain)
        print(result.render())
        return 0 if result.ok else 1

    parser.error(f"unknown command {args.command}")
    return 2


def _csv_arg(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _semi_arg(text: str) -> list[str]:
    return [item.strip() for item in text.split(";") if item.strip()]
