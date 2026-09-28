"""Repairs found by the 0.5.0 release review."""
from pathlib import Path

from memento_tattoo.cli import main
from memento_tattoo.recall import render_ranked_notes
from memento_tattoo.save_commit import save_commit

NOTE = "Situation: changing a public API\nNote: search other packages for callers first."


def _init(tmp_path: Path) -> Path:
    root = tmp_path / "memento"
    assert main(["init", "--root", str(root), "--project", str(tmp_path)]) == 0
    return root


def test_note_add_and_tattoo_add_reject_reserved_record_markers(tmp_path: Path, capsys):
    root = _init(tmp_path)
    before = (root / "notes.md").read_bytes(), (root / "tattoos.md").read_bytes()
    capsys.readouterr()

    assert main(["--root", str(root), "note-add", "--sess", "sess_r001", "--kind", "seed",
                 NOTE + "\n<!-- memento-history:v1\n"]) == 2
    assert main(["--root", str(root), "tattoo-add", "--sess", "sess_r001", "Do X; <!-- delta:sess_x.tattoo.1 -->"]) == 2
    out = capsys.readouterr().out
    assert out.count("error: text contains the reserved record marker") == 2
    assert ((root / "notes.md").read_bytes(), (root / "tattoos.md").read_bytes()) == before


def test_a_hand_corrupted_history_block_is_named_and_does_not_crash_doctor(tmp_path: Path, capsys):
    root = _init(tmp_path)
    assert main(["--root", str(root), "note-add", "--sess", "sess_r002", "--kind", "seed", NOTE]) == 0
    notes = root / "notes.md"
    notes.write_text(notes.read_text(encoding="utf-8") + "<!-- memento-history:broken\n", encoding="utf-8")
    capsys.readouterr()

    assert main(["--root", str(root), "load", "--query", "public API callers"]) == 2
    assert "note sess_r002.note." in capsys.readouterr().out

    assert main(["--root", str(root), "doctor"]) != 0
    out = capsys.readouterr().out
    assert "FAIL  gardening: note sources unreadable" in out


def test_save_commit_without_a_section_fills_the_heading_init_wrote(tmp_path: Path):
    root = _init(tmp_path)
    spec = {
        "sess": "sess_r003",
        "agent": "codex",
        "session": {"date": "2026-09-28 10:00", "topics": ["demo"], "significance": "low",
                    "accomplished": "Checked the default section.", "started": "none.", "pending": "none.",
                    "insights": "none.", "files": []},
        "project_edit": {"project": str(tmp_path), "body": "- Situation: default section\n- Note: filled.",
                         "flow_start": "2026-09-28T10:00:00Z"},
    }
    result = save_commit(spec, root=root)
    assert result.ok, result
    memory = (tmp_path / "memory.md").read_text(encoding="utf-8")
    assert "## State" not in memory
    assert "Note: filled." in memory.split("## Current state", 1)[1]
    assert "Note: filled." in render_ranked_notes("default section", root=root, projects=[tmp_path])


def test_an_empty_current_state_heading_does_not_hide_a_filled_one(tmp_path: Path):
    root = _init(tmp_path)
    (tmp_path / "memory.md").write_text("# Project Memory\n\n## Current state\n\n## State\n\n- the real state\n",
                                        encoding="utf-8")
    assert "the real state" in render_ranked_notes("anything", root=root, projects=[tmp_path])


def test_entry_read_reports_a_malformed_marker_cleanly(tmp_path: Path, capsys):
    root = _init(tmp_path)
    (root / "tattoos.md").write_text("# Tattoos\n\n<!-- delta: -->\n- Do X; because Y.\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["--root", str(root), "entry-read", "--id", "sess_x.tattoo.1"]) == 2
    assert "malformed record marker" in capsys.readouterr().out
