from pathlib import Path

from memento_tattoo.save_commit import save_commit
from memento_tattoo.retention import read_retention_events


def _spec(sess: str = "sess_abcd") -> dict:
    return {
        "sess": sess,
        "agent": "codex",
        "session": {
            "date": "2026-06-17 18:24",
            "topics": ["memento-oss", "multi-agent"],
            "significance": "medium",
            "accomplished": "Published docs polish.",
            "started": "none.",
            "pending": "none.",
            "insights": "none.",
            "files": ["README.md", "templates/AGENTS.md"],
        },
        "note": "Situation: claiming work complete\nNote: run the relevant proof command before saying the work is complete.",
        "note_kind": "reflection",
        "tattoo": "Before claiming work is complete, run the proof command.",
        "project_edit": {
            "project": "project",
            "section": "## State",
            "body": "- Situation: claiming work complete\n- Note: run the relevant proof command before saying the work is complete.",
            "flow_start": "2026-06-17T18:24:58Z",
        },
        "registry_delta": {
            "action": "update",
            "slug": "memento-oss",
            "line": "- Memento OSS - memento-oss/ - active",
        },
        "verify": ["Memento OSS", "sess_abcd"],
    }


def test_malformed_spec_fails_before_any_write(tmp_path: Path):
    result = save_commit({"sess": "sess_abcd", "unexpected": True}, root=tmp_path)

    assert not result.ok
    assert "unknown top-level keys" in result.error
    assert not any(tmp_path.iterdir())


def test_bad_session_id_rejected(tmp_path: Path):
    result = save_commit(_spec(sess="bad"), root=tmp_path)

    assert not result.ok
    assert "sess_" in result.error
    assert not (tmp_path / "sessions").exists()


def test_full_spec_writes_all_surfaces_and_rerun_is_idempotent(tmp_path: Path):
    spec = _spec()

    first = save_commit(spec, root=tmp_path)
    second = save_commit(spec, root=tmp_path)

    assert first.ok, first.error
    assert second.ok, second.error
    assert (tmp_path / "sessions" / "sess_abcd.md").exists()
    assert "claiming work complete" in (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert "proof command" in (tmp_path / "tattoos.md").read_text(encoding="utf-8")
    assert "Memento OSS" in (tmp_path / "registry.md").read_text(encoding="utf-8")
    assert "claiming work complete" in (tmp_path / "project" / "memory.md").read_text(encoding="utf-8")
    assert not list((tmp_path / "_queue").glob("*.registry.md"))


def test_save_commit_passes_retention_judgment(tmp_path: Path):
    spec = _spec()
    spec.pop("tattoo")
    spec["retention"] = {
        "decision": "existing-repaired",
        "repair": "added completion aliases",
        "covered_note_id": "sess_old.note.11111111",
    }

    result = save_commit(spec, root=tmp_path)
    events = read_retention_events(root=tmp_path)

    assert result.ok, result.error
    assert events[0]["decision"] == "existing-repaired"
    assert events[0]["repair"] == "added completion aliases"
    assert events[0]["covered_note_id"] == "sess_old.note.11111111"


def test_save_commit_project_edit_append_mode_preserves_existing_section(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text(
        "# Project Memory\n\n"
        "## Worklog\n\n"
        "<!-- delta:sess_old.project.11111111 agent=codex ts=2026-06-17T00:00:00Z -->\n"
        "- Existing delta.\n",
        encoding="utf-8",
    )
    spec = _spec()
    spec["project_edit"] = {
        "project": "project",
        "section": "## Worklog",
        "body": "- New delta.",
        "mode": "append",
    }
    spec["verify"] = ["Existing delta", "New delta"]

    result = save_commit(spec, root=tmp_path)

    text = (project / "memory.md").read_text(encoding="utf-8")
    assert result.ok, result.error
    assert "- Existing delta." in text
    assert "- New delta." in text


def test_save_commit_rejects_unknown_project_edit_mode(tmp_path: Path):
    spec = _spec()
    spec["project_edit"]["mode"] = "merge"

    result = save_commit(spec, root=tmp_path)

    assert not result.ok
    assert result.error == "project_edit.mode must be auto, append, or replace"
    assert not (tmp_path / "sessions").exists()


def test_save_commit_rejects_retention_without_note(tmp_path: Path):
    spec = _spec()
    spec.pop("note")
    spec["retention"] = {"decision": "new"}

    result = save_commit(spec, root=tmp_path)

    assert not result.ok
    assert result.error == "retention requires note"
    assert not (tmp_path / "sessions").exists()


def test_save_commit_rejects_retention_for_seed_note(tmp_path: Path):
    spec = _spec()
    spec["note_kind"] = "seed"
    spec["retention"] = {"decision": "new"}

    result = save_commit(spec, root=tmp_path)

    assert not result.ok
    assert result.error == "retention requires correction or reflection note"
    assert not (tmp_path / "sessions").exists()


def test_existing_different_session_file_refuses_to_clobber(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess_abcd.md").write_text("different\n", encoding="utf-8")

    result = save_commit(_spec(), root=tmp_path)

    assert not result.ok
    assert "different content" in result.error
    assert result.touched == []


def test_artifact_verification_failure_reports_touched_artifacts(tmp_path: Path):
    spec = _spec()
    spec["verify"] = ["definitely absent"]

    result = save_commit(spec, root=tmp_path)

    assert not result.ok
    assert "verify string missing" in result.error
    assert result.touched
    assert (tmp_path / "sessions" / "sess_abcd.md").exists()
