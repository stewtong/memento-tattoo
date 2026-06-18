from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import paths_for
from .rebuild import rebuild
from .registry import drain, registry_queue
from .retention import DECISIONS
from .session_store import render_session_block, write_session_block
from .write_through import note_add, project_edit, tattoo_add


_ALLOWED_KEYS = {
    "sess",
    "agent",
    "session",
    "note",
    "note_kind",
    "retention",
    "tattoo",
    "project_edit",
    "registry_delta",
    "verify",
}


@dataclass(frozen=True)
class StepResult:
    name: str
    ok: bool
    path: Path | None = None
    message: str = ""


@dataclass(frozen=True)
class SaveCommitResult:
    ok: bool
    steps: list[StepResult]
    touched: list[Path]
    deferred: bool = False
    error: str = ""

    def render(self) -> str:
        lines = []
        for step in self.steps:
            status = "ok" if step.ok else "FAIL"
            detail = f" {step.path}" if step.path else ""
            if step.message:
                detail += f" {step.message}"
            lines.append(f"[{status}] {step.name}{detail}")
        result = "ok" if self.ok else "FAIL"
        suffix = " deferred=true" if self.deferred else ""
        if self.error:
            suffix += f" error={self.error}"
        lines.append(f"RESULT {result}{suffix}")
        return "\n".join(lines)


def save_commit(
    spec: dict[str, Any],
    *,
    root: Path | None = None,
    allow_deferred_drain: bool = False,
) -> SaveCommitResult:
    paths = paths_for(root)
    error = _validate(spec)
    if error:
        return SaveCommitResult(ok=False, steps=[], touched=[], error=error)

    touched: list[Path] = []
    steps: list[StepResult] = []
    sess = spec["sess"]
    agent = spec["agent"]

    try:
        session = spec["session"]
        block = render_session_block(
            sess,
            date=session["date"],
            agent=agent,
            topics=session["topics"],
            significance=session["significance"],
            accomplished=session["accomplished"],
            started=session["started"],
            pending=session["pending"],
            insights=session["insights"],
            files=session["files"],
        )
        session_path = write_session_block(paths.root, block, sess)
        touched.append(session_path)
        steps.append(StepResult("session", True, session_path))

        if spec.get("note"):
            retention = spec.get("retention") or {}
            note_add(
                spec["note"],
                sess=sess,
                root=paths.root,
                kind=spec.get("note_kind", "reflection"),
                agent=agent,
                decision=retention.get("decision"),
                repair=retention.get("repair", ""),
                covered_note_id=retention.get("covered_note_id"),
            )
            touched.append(paths.notes)
            steps.append(StepResult("note", True, paths.notes))

        if spec.get("tattoo"):
            tattoo_add(spec["tattoo"], sess=sess, root=paths.root, agent=agent)
            touched.append(paths.tattoos)
            steps.append(StepResult("tattoo", True, paths.tattoos))

        project_spec = spec.get("project_edit")
        if project_spec:
            project_path = _project_path(paths.root, project_spec["project"])
            project_edit(
                project_spec["body"],
                sess=sess,
                root=paths.root,
                project=project_path,
                section=project_spec.get("section", "## State"),
                flow_start=project_spec.get("flow_start"),
                agent=agent,
                mode=project_spec.get("mode", "auto"),
            )
            touched.append(project_path / "memory.md")
            steps.append(StepResult("project_edit", True, project_path / "memory.md"))

        registry_spec = spec.get("registry_delta")
        queued = False
        if registry_spec and not _registry_has_line(paths.registry, registry_spec["line"]):
            queue_path = registry_queue(
                sess,
                registry_spec["action"],
                registry_spec["slug"],
                registry_spec["line"],
                paths.root,
                agent=agent,
            )
            touched.append(queue_path)
            steps.append(StepResult("registry_queue", True, queue_path))
            queued = True

        drain_result = drain(paths.root)
        if drain_result.skipped:
            steps.append(StepResult("drain", allow_deferred_drain, message="deferred"))
            if allow_deferred_drain:
                return SaveCommitResult(ok=True, steps=steps, touched=touched, deferred=True)
            return SaveCommitResult(ok=False, steps=steps, touched=touched, error="drain skipped")
        if drain_result.errors:
            steps.append(StepResult("drain", False, message="; ".join(drain_result.errors)))
            return SaveCommitResult(ok=False, steps=steps, touched=touched, error="drain failed")
        if queued or registry_spec:
            touched.append(paths.registry)
        steps.append(StepResult("drain", True, message=drain_result.render()))

        rebuilt, rebuild_output = rebuild(paths.root)
        steps.append(StepResult("rebuild", rebuilt, message=rebuild_output))
        if not rebuilt:
            return SaveCommitResult(ok=False, steps=steps, touched=touched, error=rebuild_output)

        missing = _missing_verify_strings(spec.get("verify", []), touched)
        if missing:
            message = f"verify string missing: {missing[0]}"
            steps.append(StepResult("verify", False, message=message))
            return SaveCommitResult(ok=False, steps=steps, touched=touched, error=message)
        steps.append(StepResult("verify", True))
        return SaveCommitResult(ok=True, steps=steps, touched=touched)
    except Exception as exc:
        return SaveCommitResult(ok=False, steps=steps, touched=touched, error=str(exc))


def _validate(spec: dict[str, Any]) -> str:
    unknown = sorted(set(spec) - _ALLOWED_KEYS)
    if unknown:
        return f"unknown top-level keys: {', '.join(unknown)}"
    sess = spec.get("sess")
    if not isinstance(sess, str) or not sess.startswith("sess_"):
        return "sess must start with sess_"
    if not spec.get("agent"):
        return "agent is required"
    session = spec.get("session")
    if not isinstance(session, dict):
        return "session is required"
    required_session = {"date", "topics", "significance", "accomplished", "started", "pending", "insights", "files"}
    missing = sorted(required_session - set(session))
    if missing:
        return f"session missing keys: {', '.join(missing)}"
    if session.get("significance") not in {"low", "medium", "high"}:
        return "session.significance must be low, medium, or high"
    registry_delta = spec.get("registry_delta")
    if registry_delta and registry_delta.get("action") not in {"add", "update", "archive"}:
        return "registry_delta.action must be add, update, or archive"
    project_edit_spec = spec.get("project_edit")
    if project_edit_spec:
        mode = project_edit_spec.get("mode", "auto")
        if mode not in {"auto", "append", "replace"}:
            return "project_edit.mode must be auto, append, or replace"
    retention = spec.get("retention")
    if retention:
        if not isinstance(retention, dict):
            return "retention must be an object"
        if not spec.get("note"):
            return "retention requires note"
        if spec.get("note_kind", "reflection") == "seed":
            return "retention requires correction or reflection note"
        allowed_retention = {"decision", "repair", "covered_note_id"}
        unknown_retention = sorted(set(retention) - allowed_retention)
        if unknown_retention:
            return f"retention unknown keys: {', '.join(unknown_retention)}"
        decision = retention.get("decision")
        if decision and decision not in DECISIONS:
            return "retention.decision must be new, existing-missed, existing-repaired, or false-positive"
    return ""


def _project_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _registry_has_line(path: Path, line: str) -> bool:
    return path.exists() and line.rstrip() in path.read_text(encoding="utf-8")


def _missing_verify_strings(verify: list[str], touched: list[Path]) -> list[str]:
    corpus = []
    for path in touched:
        if path.exists() and path.is_file():
            corpus.append(path.read_text(encoding="utf-8"))
    text = "\n".join(corpus)
    return [item for item in verify if item not in text]
