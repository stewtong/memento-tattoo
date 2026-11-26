from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Optional

from . import __version__
from .doctor import (
    DEFAULT_TATTOO_REASON_WARN,
    DEFAULT_WHY_COVERAGE_WARN,
    RECOMMENDED_ALIAS_COVERAGE_PERCENT,
    RECOMMENDED_TATTOO_BYTES,
    RECOMMENDED_TATTOO_COUNT,
    RECOMMENDED_TATTOO_LENGTH,
    run_doctor,
)
from .garden import DEFAULT_DIGEST_LIMIT, build_digest
from ._time import now_iso
from .project_memory import default_state_section
from .recall import render_ranked_notes
from .retention import DECISIONS
from .tattoo_audit import tattoo_audit_report
from .write_through import note_add, project_edit, tattoo_add


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="memento-tattoo", description="File-based lesson-retention memory for LLM agents.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", default=None, help="memento root; defaults to ./memento")
    parser.add_argument("--agent", default=None, help="agent id for provenance; defaults to MEMENTO_AGENT or unknown")
    subparsers = parser.add_subparsers(dest="command", required=True)

    note = subparsers.add_parser("note-add", help="append a checked lesson note")
    note.add_argument("--sess", required=True)
    note.add_argument("--kind", choices=["correction", "reflection", "seed", "pattern"], default="reflection")
    note.add_argument("--author", default=None, help="author code for retention events, such as cc, cdx, or oc")
    note.add_argument("--decision", choices=DECISIONS, default=None, help="override the checked retrieval decision")
    note.add_argument("--covered-note-id", default=None, help="existing lesson note id this note should have matched")
    note.add_argument("text")

    entry = subparsers.add_parser("entry-read", help="read one complete source-scoped memory entry")
    entry.add_argument("--id", default=None)
    entry.add_argument("--source", default=None, help="exact store path, or path relative to the memory root")
    entry.add_argument("--project", action="append", default=[], help="explicit project directory to include")
    entry.add_argument("--format", choices=["json", "markdown"], default="json")

    amend = subparsers.add_parser("note-amend", help="revise an ordinary note with a digest guard and visible history")
    amend.add_argument("--id", required=True)
    amend.add_argument("--source", default=None)
    amend.add_argument("--expected-sha256", required=True)
    amend.add_argument("--sess", required=True)
    amend.add_argument("--author", required=True)
    amend.add_argument("--reason", required=True)
    amend.add_argument("--evidence", required=True, help="source reference supporting the editorial change")
    amend.add_argument("text", help="complete replacement active note body, without creation marker or history")

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
    project.add_argument("--section", default=None, help="h2 section to edit; defaults to the file's existing current-state heading ('## Current state' or '## State')")
    project.add_argument("--flow-start", default=None)
    project_mode = project.add_mutually_exclusive_group()
    project_mode.add_argument("--append", action="store_true", help="append this body to an accumulating section")
    project_mode.add_argument("--replace", action="store_true", help="replace the section intentionally")
    project.add_argument("text")

    garden = subparsers.add_parser("garden", help="emit a read-only gardening digest")
    garden.add_argument("--today", required=False, default=None)
    garden.add_argument("--promote-threshold", type=int, default=2)
    garden.add_argument("--limit", type=int, default=DEFAULT_DIGEST_LIMIT, help="max items per section; 0 means all")

    doctor = subparsers.add_parser("doctor", help="run root health checks")
    doctor.add_argument("--project", action="append", default=[], help="project directory whose memory.md should be checked")
    doctor.add_argument(
        "--alias-coverage-warn",
        type=_nonnegative_float,
        default=RECOMMENDED_ALIAS_COVERAGE_PERCENT,
        metavar="PERCENT",
    )
    doctor.add_argument("--tattoo-count-warn", type=_nonnegative_int, default=RECOMMENDED_TATTOO_COUNT, metavar="COUNT")
    doctor.add_argument("--tattoo-bytes-warn", type=_nonnegative_int, default=RECOMMENDED_TATTOO_BYTES, metavar="BYTES")
    doctor.add_argument("--tattoo-length-warn", type=_nonnegative_int, default=RECOMMENDED_TATTOO_LENGTH, metavar="CHARS")
    doctor.add_argument(
        "--why-coverage-warn",
        type=_nonnegative_float,
        default=DEFAULT_WHY_COVERAGE_WARN,
        metavar="PERCENT",
        help="warn when hot or archived Why: coverage is below PERCENT; 0 (default) reports only",
    )
    doctor.add_argument(
        "--tattoo-reason-warn",
        type=_nonnegative_float,
        default=DEFAULT_TATTOO_REASON_WARN,
        metavar="PERCENT",
        help="warn when reason-clause coverage of tattoos is below PERCENT; 0 (default) reports only",
    )

    init = subparsers.add_parser("init", help="create a memory root, install PROTOCOL.md, and print the instruction stub")
    init.add_argument("--root", dest="init_root", default=None, help="memento root; same as the global --root")
    init.add_argument("--project", default=None, help="directory for project memory.md; defaults to the current directory when it contains the root, otherwise the root's parent")
    init.add_argument("--adapter", choices=["generic", "skill", "claude-md-import"], default="generic")
    init.add_argument("--dir", dest="skill_dir", default=None, help="skills directory for --adapter skill; defaults to .agents/skills")
    init.add_argument("--write", action="store_true", help="with --adapter claude-md-import, create CLAUDE.md when it is absent")

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

    session_list = subparsers.add_parser("session-list", help="list hot and archived session records")
    session_list.add_argument("--limit", type=_nonnegative_int, default=50, help="max records; 0 means all")
    session_filter = session_list.add_mutually_exclusive_group()
    session_filter.add_argument("--hot-only", action="store_true")
    session_filter.add_argument("--archive-only", action="store_true")

    session_archive = subparsers.add_parser("session-archive", help="preview or apply bounded session archival")
    session_archive.add_argument("--days", type=_nonnegative_int, required=True, help="archive sessions strictly older than this age")
    session_archive.add_argument("--limit", type=_nonnegative_int, default=100, help="max moves; 0 means all")
    session_archive.add_argument("--apply", action="store_true", help="apply the displayed moves; default is dry-run")

    tattoo_audit_p = subparsers.add_parser("tattoo-audit", help="report tattoos due for review")
    tattoo_audit_p.add_argument("--window-days", type=int, default=30, help="age threshold in days (default 30)")

    rebuild_parser = subparsers.add_parser("rebuild", help="rebuild generated session indexes")
    rebuild_parser.add_argument("--check", action="store_true")

    registry = subparsers.add_parser("registry-queue", help="queue a registry delta")
    registry.add_argument("--sess", required=True)
    registry.add_argument("--action", choices=["add", "update", "archive"], required=True)
    registry.add_argument("--slug", required=True)
    registry.add_argument("--expected-line", default=None, help="exact entry read before drafting; empty means absent")
    registry.add_argument("line")

    drain_parser = subparsers.add_parser("drain", help="drain queued registry deltas")
    drain_parser.add_argument("--timeout", type=float, default=10.0)

    queue_maintenance = subparsers.add_parser("queue-maintenance", help="archive old or excess registry conflicts")
    queue_maintenance.add_argument("--days", type=int, default=30)
    queue_maintenance.add_argument("--max-hot", type=int, default=200)
    queue_maintenance.add_argument("--apply", action="store_true")

    save = subparsers.add_parser("save-commit", help="run a validated multi-surface save from a JSON spec")
    save.add_argument("--spec", required=True)
    save.add_argument("--allow-deferred-drain", action="store_true")

    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path.cwd() / "memento"

    if args.command == "init":
        from .init import run_init

        init_root = Path(args.init_root).resolve() if args.init_root else root
        if args.skill_dir is not None and args.adapter != "skill":
            print("error: --dir applies only to --adapter skill")
            return 2
        if args.write and args.adapter != "claude-md-import":
            print("error: --write applies only to --adapter claude-md-import")
            return 2
        try:
            result = run_init(
                init_root,
                project=Path(args.project) if args.project else None,
                adapter=args.adapter,
                skill_dir=Path(args.skill_dir) if args.skill_dir else None,
                write_claude_md=args.write,
            )
        except (ValueError, OSError) as exc:
            print(f"error: {exc}")
            return 2
        print("\n".join(result.lines))
        return 0

    if args.command == "entry-read":
        from .entries import resolve_entry, render_markdown
        try:
            result = resolve_entry(args.id, root=root, source=args.source, projects=[Path(p) for p in args.project])
            output = render_markdown(result) if args.format == "markdown" else json.dumps(result.record(), ensure_ascii=False, indent=2)
        except (ValueError, OSError) as exc:
            print(f"error: {exc}")
            return 2
        print(output)
        return 0

    if args.command == "note-amend":
        from .entries import amend_note
        try:
            applied, result = amend_note(args.id, args.text, root=root, source=args.source,
                expected_sha256=args.expected_sha256, sess=args.sess, author=args.author,
                reason=args.reason, evidence=args.evidence)
        except (ValueError, OSError) as exc:
            print(f"error: {exc}")
            return 2
        print(json.dumps({"applied": applied, **result.record()}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "note-add":
        if args.kind in ("seed", "pattern") and (args.decision is not None or args.covered_note_id is not None):
            print("error: retention overrides require correction or reflection notes")
            return 2
        try:
            applied, marker = note_add(
                args.text,
                sess=args.sess,
                root=root,
                kind=args.kind,
                agent=args.agent,
                author=args.author,
                decision=args.decision,
                covered_note_id=args.covered_note_id,
            )
        except (ValueError, OSError) as exc:
            print(f"error: {exc}")
            return 2
        print(f"{'applied' if applied else 'skipped (already applied)'} {marker}")
        return 0

    if args.command == "tattoo-add":
        try:
            applied, marker = tattoo_add(args.text, sess=args.sess, root=root, agent=args.agent)
        except (ValueError, OSError) as exc:
            print(f"error: {exc}")
            return 2
        print(f"{'applied' if applied else 'skipped (already applied)'} {marker}")
        return 0

    if args.command == "project-edit":
        mode = "append" if args.append else "replace" if args.replace else "auto"
        try:
            applied, marker = project_edit(
                args.text,
                sess=args.sess,
                root=root,
                project=Path(args.project),
                section=args.section or default_state_section(Path(args.project)),
                flow_start=args.flow_start,
                agent=args.agent,
                mode=mode,
            )
        except ValueError as exc:
            print(f"error: {exc}")
            return 2
        print(f"{'applied' if applied else 'skipped (already applied)'} {marker}")
        return 0

    if args.command == "load":
        try:
            print(render_ranked_notes(args.query, root=root, limit=args.limit, projects=[Path(item) for item in args.project]))
        except (ValueError, OSError) as exc:
            print(f"error: {exc}")
            return 2
        return 0

    if args.command == "tattoo-audit":
        print(tattoo_audit_report(root, window_days=args.window_days))
        return 0

    if args.command == "garden":
        print(build_digest(root=root, today=args.today or now_iso()[:10], promote_threshold=args.promote_threshold, limit=args.limit))
        return 0

    if args.command == "doctor":
        ok, output = run_doctor(
            root,
            projects=[Path(item) for item in args.project],
            alias_coverage_warn=args.alias_coverage_warn,
            tattoo_count_warn=args.tattoo_count_warn,
            tattoo_bytes_warn=args.tattoo_bytes_warn,
            tattoo_length_warn=args.tattoo_length_warn,
            why_coverage_warn=args.why_coverage_warn,
            tattoo_reason_warn=args.tattoo_reason_warn,
        )
        print(output)
        return 0 if ok else 1

    if args.command == "new-id":
        from .new_id import generate_session_id

        print(generate_session_id(root))
        return 0

    if args.command == "session-add":
        from .new_id import prune_reservations
        from .session_store import render_session_block, write_session_block

        try:
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
        except (ValueError, FileExistsError) as exc:
            print(f"error: {exc}")
            return 2
        prune_reservations(root)
        print(f"applied {path}")
        return 0

    if args.command == "session-list":
        from .session_store import load_sessions, parse_session_date

        try:
            records = load_sessions(root)
            records.sort(key=lambda record: (parse_session_date(record.date), record.sess), reverse=True)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}")
            return 1
        archive_dir = (root / "sessions" / "archive").resolve()
        if args.hot_only:
            records = [record for record in records if record.path.parent.resolve() != archive_dir]
        elif args.archive_only:
            records = [record for record in records if record.path.parent.resolve() == archive_dir]
        if args.limit:
            records = records[: args.limit]
        print(f"SESSION_LIST {len(records)} record(s)")
        print("session_id\tdate\tagent\tsignificance\ttopics\tlocation")
        for record in records:
            location = "archive" if record.path.parent.resolve() == archive_dir else "hot"
            print(
                f"{record.sess}\t{record.date}\t{record.agent}\t{record.significance}\t"
                f"{', '.join(record.topics)}\t{location}"
            )
        return 0

    if args.command == "session-archive":
        from .session_archive import apply_archive, archive_candidates, render_archive_plan

        try:
            moves = archive_candidates(root, days=args.days, limit=args.limit)
            plan = render_archive_plan(moves, root, applied=args.apply)
            print(plan)
            if args.apply:
                moved = apply_archive(moves, root)
                print(f"archived {moved} session(s)")
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"error: {exc}")
            return 1
        return 0

    if args.command == "rebuild":
        from .rebuild import rebuild

        ok, output = rebuild(root, check=args.check)
        print(output)
        return 0 if ok else 1

    if args.command == "registry-queue":
        from .registry import registry_queue

        path = registry_queue(args.sess, args.action, args.slug, args.line, root, agent=args.agent, expected_line=args.expected_line)
        print(f"queued {path}")
        return 0

    if args.command == "drain":
        from .registry import drain

        result = drain(root, timeout=args.timeout)
        print(result.render())
        return 0 if result.ok else 1

    if args.command == "queue-maintenance":
        from .registry import archive_registry_conflicts, conflict_archive_candidates

        candidates = conflict_archive_candidates(root, days=args.days, max_hot=args.max_hot)
        print(f"QUEUE_MAINTENANCE {len(candidates)} candidate(s)")
        for path in candidates:
            print(path.relative_to(root))
        if args.apply and candidates:
            print(f"archived {archive_registry_conflicts(root, days=args.days, max_hot=args.max_hot)} conflict artifact(s)")
        return 0

    if args.command == "save-commit":
        from .save_commit import save_commit

        try:
            spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
            print(f"RESULT FAIL error=cannot read spec {args.spec}: {type(exc).__name__}: {exc}")
            return 1
        result = save_commit(spec, root=root, allow_deferred_drain=args.allow_deferred_drain)
        print(result.render())
        return 0 if result.ok else 1

    parser.error(f"unknown command {args.command}")
    return 2


def _csv_arg(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _semi_arg(text: str) -> list[str]:
    return [item.strip() for item in text.split(";") if item.strip()]


def _nonnegative_int(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return value


def _nonnegative_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("must be finite and nonnegative")
    return value
