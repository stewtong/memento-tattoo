from pathlib import Path
import json

from memento_tattoo.cli import main


def test_cli_note_add_and_garden(tmp_path: Path, capsys):
    code = main(["--root", str(tmp_path), "note-add", "--sess", "sess_cli", "--kind", "reflection", "Situation: docs\nNote: sanitize"])

    assert code == 0
    assert "applied" in capsys.readouterr().out

    code = main(["--root", str(tmp_path), "garden", "--today", "2026-06-17"])

    assert code == 0
    assert "Memento gardening digest" in capsys.readouterr().out


def test_cli_note_add_accepts_retention_judgment(tmp_path: Path, capsys):
    code = main(
        [
            "--root",
            str(tmp_path),
            "note-add",
            "--sess",
            "sess_cli",
            "--kind",
            "correction",
            "--decision",
            "false-positive",
            "--repair",
            "ranking matched generic words only",
            "--covered-note-id",
            "sess_old.note.11111111",
            "Situation: publish prep\nNote: do not count unrelated retrieval as coverage",
        ]
    )

    events = [json.loads(line) for line in (tmp_path / "retention_log.jsonl").read_text(encoding="utf-8").splitlines()]

    assert code == 0
    assert "applied" in capsys.readouterr().out
    assert events[0]["decision"] == "false-positive"
    assert events[0]["repair"] == "ranking matched generic words only"
    assert events[0]["covered_note_id"] == "sess_old.note.11111111"


def test_cli_note_add_rejects_seed_retention_judgment(tmp_path: Path, capsys):
    code = main(
        [
            "--root",
            str(tmp_path),
            "note-add",
            "--sess",
            "sess_cli",
            "--kind",
            "seed",
            "--decision",
            "new",
            "Situation: import\nNote: seed data",
        ]
    )

    assert code == 2
    assert "retention overrides require correction or reflection notes" in capsys.readouterr().out
    assert not (tmp_path / "retention_log.jsonl").exists()


def test_cli_global_agent_writes_marker_metadata(tmp_path: Path, capsys):
    code = main(
        [
            "--root",
            str(tmp_path),
            "--agent",
            "Codex CLI",
            "note-add",
            "--sess",
            "sess_cli",
            "--kind",
            "seed",
            "Situation: docs\nNote: sanitize",
        ]
    )

    output = capsys.readouterr().out
    text = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert code == 0
    assert "agent=codex-cli" in output
    assert "agent=codex-cli" in text


def test_cli_new_id_session_add_and_rebuild(tmp_path: Path, capsys):
    code = main(["--root", str(tmp_path), "new-id"])
    sid = capsys.readouterr().out.strip()

    assert code == 0
    assert sid.startswith("sess_")

    code = main(
        [
            "--root",
            str(tmp_path),
            "--agent",
            "Codex CLI",
            "session-add",
            "--sess",
            sid,
            "--date",
            "2026-06-17 18:24",
            "--topics",
            "memento-oss,multi-agent",
            "--significance",
            "medium",
            "--accomplished",
            "Published docs polish.",
            "--started",
            "none.",
            "--pending",
            "none.",
            "--insights",
            "none.",
            "--files",
            "README.md; templates/AGENTS.md",
        ]
    )

    assert code == 0
    assert "applied" in capsys.readouterr().out
    session_text = (tmp_path / "sessions" / f"{sid}.md").read_text(encoding="utf-8")
    assert "codex-cli" in session_text

    code = main(["--root", str(tmp_path), "rebuild"])

    assert code == 0
    assert "rebuilt" in capsys.readouterr().out.lower()
    assert sid in (tmp_path / "sessions" / "index.md").read_text(encoding="utf-8")


def test_cli_registry_queue_and_drain(tmp_path: Path, capsys):
    code = main(
        [
            "--root",
            str(tmp_path),
            "--agent",
            "Codex",
            "registry-queue",
            "--sess",
            "sess_abcd",
            "--action",
            "update",
            "--slug",
            "memento-oss",
            "- Memento OSS - memento-oss/ - active",
        ]
    )

    assert code == 0
    assert "queued" in capsys.readouterr().out

    code = main(["--root", str(tmp_path), "drain"])

    output = capsys.readouterr().out
    assert code == 0
    assert "applied" in output
    assert "Memento OSS" in (tmp_path / "registry.md").read_text(encoding="utf-8")


def test_cli_save_commit_from_spec_file(tmp_path: Path, capsys):
    spec_file = tmp_path / "spec.json"
    spec_file.write_text(
        json.dumps(
            {
                "sess": "sess_abcd",
                "agent": "codex",
                "session": {
                    "date": "2026-06-17 18:24",
                    "topics": ["memento-oss"],
                    "significance": "medium",
                    "accomplished": "Published docs polish.",
                    "started": "none.",
                    "pending": "none.",
                    "insights": "none.",
                    "files": ["README.md"],
                },
                "note": "Situation: docs\nNote: verify package contents",
                "verify": ["sess_abcd", "verify package"],
            }
        ),
        encoding="utf-8",
    )

    code = main(["--root", str(tmp_path / "mem"), "save-commit", "--spec", str(spec_file)])

    output = capsys.readouterr().out
    assert code == 0
    assert "RESULT ok" in output


def test_cli_doctor_reports_missing_files(tmp_path: Path, capsys):
    code = main(["--root", str(tmp_path), "doctor"])

    assert code == 1
    assert "notes.md missing" in capsys.readouterr().out


def test_cli_load_query_returns_ranked_note(tmp_path: Path, capsys):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_cli.note.11111111 -->\n"
        "Situation: publishing docs\n"
        "Note: sanitize examples before public release\n"
        "aliases: sanitize, public, release\n",
        encoding="utf-8",
    )

    code = main(["--root", str(tmp_path), "load", "--query", "sanitize public release"])

    output = capsys.readouterr().out
    assert code == 0
    assert "sess_cli.note.11111111" in output
    assert "sanitize examples" in output


def test_cli_load_query_omits_zero_score_notes(tmp_path: Path, capsys):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_match.note.11111111 -->\n"
        "Situation: publishing docs\n"
        "Note: sanitize examples before public release\n"
        "aliases: sanitize, public, release\n\n"
        "<!-- delta:sess_miss.note.22222222 -->\n"
        "Situation: debugging tests\n"
        "Note: reproduce before fixing\n",
        encoding="utf-8",
    )

    code = main(["--root", str(tmp_path), "load", "--query", "sanitize public release"])

    output = capsys.readouterr().out
    assert code == 0
    assert "sess_match.note.11111111" in output
    assert "sess_miss.note.22222222" not in output


def test_cli_project_edit_writes_adjacent_memory(tmp_path: Path, capsys):
    root = tmp_path / ".memento"
    project = tmp_path / "project"

    code = main(
        [
            "--root",
            str(root),
            "project-edit",
            "--project",
            str(project),
            "--sess",
            "sess_abcd",
            "--section",
            "## State",
            "- Added project memory support.",
        ]
    )

    output = capsys.readouterr().out
    text = (project / "memory.md").read_text(encoding="utf-8")
    assert code == 0
    assert "applied" in output
    assert "- Added project memory support." in text


def test_cli_project_edit_append_mode_preserves_worklog(tmp_path: Path, capsys):
    root = tmp_path / ".memento"
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text(
        "# Project Memory\n\n"
        "## Worklog\n\n"
        "<!-- delta:sess_old.project.11111111 agent=codex ts=2026-06-17T00:00:00Z -->\n"
        "- Existing delta.\n",
        encoding="utf-8",
    )

    code = main(
        [
            "--root",
            str(root),
            "project-edit",
            "--project",
            str(project),
            "--sess",
            "sess_abcd",
            "--section",
            "## Worklog",
            "--append",
            "- New delta.",
        ]
    )

    text = (project / "memory.md").read_text(encoding="utf-8")
    assert code == 0
    assert "applied" in capsys.readouterr().out
    assert "- Existing delta." in text
    assert "- New delta." in text


def test_cli_project_edit_auto_rejects_ambiguous_replace(tmp_path: Path, capsys):
    root = tmp_path / ".memento"
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text(
        "# Project Memory\n\n"
        "## Worklog\n\n"
        "<!-- delta:sess_old.project.11111111 agent=codex ts=2026-06-17T00:00:00Z -->\n"
        "- Existing delta.\n",
        encoding="utf-8",
    )

    code = main(
        [
            "--root",
            str(root),
            "project-edit",
            "--project",
            str(project),
            "--sess",
            "sess_abcd",
            "--section",
            "## Worklog",
            "- New delta.",
        ]
    )

    output = capsys.readouterr().out
    text = (project / "memory.md").read_text(encoding="utf-8")
    assert code == 2
    assert "--append or --replace" in output
    assert "- Existing delta." in text
    assert "- New delta." not in text


def test_cli_load_can_include_project_memory(tmp_path: Path, capsys):
    root = tmp_path / ".memento"
    root.mkdir()
    (root / "notes.md").write_text("", encoding="utf-8")
    (root / "tattoos.md").write_text("# Tattoos\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "memory.md").write_text(
        "# Project Memory\n\n"
        "## State\n\n"
        "- Situation: public release readiness\n"
        "- Note: publish from the sanitized export tree.\n",
        encoding="utf-8",
    )

    code = main(["--root", str(root), "load", "--project", str(project), "--query", "sanitized export"])

    output = capsys.readouterr().out
    assert code == 0
    assert "project/memory.md" in output
    assert "sanitized export tree" in output


def test_cli_tattoo_audit_reports_aged_tattoo(tmp_path: Path, capsys):
    # Seed an aged tattoo (ts in January, well outside 30-day window).
    sessions = tmp_path / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / "sess_anch.md").write_text(
        "---\n[sess_anch | 2026-06-17 10:00 | codex | test | low]\n"
        "Accomplished: x\nStarted: none\nPending: none\nInsights: none\nFiles: none\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "tattoos.md").write_text(
        "# Tattoos\n\n"
        "<!-- delta:sess_old.tattoo.aaaaaaaa agent=codex ts=2026-01-01T00:00:00Z -->\n"
        "- Old aged tattoo bullet.\n",
        encoding="utf-8",
    )

    code = main(["--root", str(tmp_path), "tattoo-audit"])

    output = capsys.readouterr().out
    assert code == 0
    assert "Old aged tattoo bullet" in output


def test_cli_tattoo_audit_window_days_flag(tmp_path: Path, capsys):
    # Tattoo that is 7 days old; default window (30) does not flag it, but window=5 does.
    sessions = tmp_path / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / "sess_anch.md").write_text(
        "---\n[sess_anch | 2026-06-17 10:00 | codex | test | low]\n"
        "Accomplished: x\nStarted: none\nPending: none\nInsights: none\nFiles: none\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "tattoos.md").write_text(
        "# Tattoos\n\n"
        "<!-- delta:sess_x.tattoo.bbbbbbbb agent=codex ts=2026-06-10T00:00:00Z -->\n"
        "- Seven day old tattoo.\n",
        encoding="utf-8",
    )

    # Default window (30d): should not be flagged, report says "Nothing due"
    code_default = main(["--root", str(tmp_path), "tattoo-audit"])
    out_default = capsys.readouterr().out
    assert code_default == 0
    assert "Nothing due" in out_default

    # Narrow window (5d): should flag it
    code_narrow = main(["--root", str(tmp_path), "tattoo-audit", "--window-days", "5"])
    out_narrow = capsys.readouterr().out
    assert code_narrow == 0
    assert "Seven day old tattoo" in out_narrow


def test_cli_garden_defaults_to_today(tmp_path: Path, capsys, monkeypatch):
    import memento_tattoo.cli as cli

    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_future.note.11111111 -->\n"
        "Situation: future review\n"
        "Note: this should not be stale yet\n"
        "review_after: 2026-12-31\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(cli, "now_iso", lambda: "2026-06-17T00:00:00Z")

    code = main(["--root", str(tmp_path), "garden"])

    output = capsys.readouterr().out
    assert code == 0
    assert "sess_future.note.11111111" not in output
