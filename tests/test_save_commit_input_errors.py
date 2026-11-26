"""save-commit input errors: bad --spec files and reserved markers fail before any write."""
import json
from pathlib import Path

import pytest

from memento_tattoo.cli import main
from memento_tattoo.save_commit import save_commit


def _init(tmp_path: Path) -> Path:
    root = tmp_path / "memento"
    assert main(["init", "--root", str(root), "--project", str(tmp_path)]) == 0
    return root


def _spec(sess: str = "sess_t001") -> dict:
    return {
        "sess": sess,
        "agent": "codex",
        "session": {
            "date": "2026-11-25 10:00",
            "topics": ["synthetic"],
            "significance": "low",
            "accomplished": "Synthetic work.",
            "started": "none.",
            "pending": "none.",
            "insights": "none.",
            "files": ["a.txt"],
        },
        "note": "Situation: checking inputs\nNote: validate before writing.",
        "note_kind": "reflection",
        "tattoo": "Validate inputs before writing.",
        "project_edit": {
            "project": "project",
            "section": "## State",
            "body": "- Synthetic project state.",
        },
        "registry_delta": {
            "action": "add",
            "slug": "demo",
            "line": "- Demo - project/ - Synthetic entry - active",
            "expected_line": "",
        },
    }


def _snapshot(root: Path) -> dict:
    return {
        str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
        for p in sorted(root.rglob("*"))
    }


def _run_cli(root: Path, spec_path: Path, capsys):
    capsys.readouterr()
    code = main(["--root", str(root), "save-commit", "--spec", str(spec_path)])
    out = capsys.readouterr()
    return code, out


def test_cli_missing_spec_reports_fail_without_traceback(tmp_path: Path, capsys):
    root = _init(tmp_path)
    missing = tmp_path / "does-not-exist.json"
    code, out = _run_cli(root, missing, capsys)
    assert code != 0
    assert "RESULT FAIL" in out.out
    assert "error=" in out.out and str(missing) in out.out
    assert "Traceback" not in out.out + out.err


def test_cli_invalid_json_spec_reports_fail_without_traceback(tmp_path: Path, capsys):
    root = _init(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    code, out = _run_cli(root, bad, capsys)
    assert code != 0
    assert "RESULT FAIL" in out.out
    assert str(bad) in out.out
    assert "Traceback" not in out.out + out.err


def test_cli_non_utf8_spec_reports_fail_without_traceback(tmp_path: Path, capsys):
    root = _init(tmp_path)
    bad = tmp_path / "binary.json"
    bad.write_bytes(b"\xff\xfe\x00{")
    code, out = _run_cli(root, bad, capsys)
    assert code != 0
    assert "RESULT FAIL" in out.out
    assert "Traceback" not in out.out + out.err


def test_cli_directory_spec_reports_fail_without_traceback(tmp_path: Path, capsys):
    root = _init(tmp_path)
    folder = tmp_path / "spec-dir"
    folder.mkdir()
    code, out = _run_cli(root, folder, capsys)
    assert code != 0
    assert "RESULT FAIL" in out.out
    assert "Traceback" not in out.out + out.err


def test_cli_deeply_nested_spec_reports_fail_without_traceback(tmp_path: Path, capsys):
    root = _init(tmp_path)
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
    code, out = _run_cli(root, deep, capsys)
    assert code != 0
    assert "RESULT FAIL" in out.out
    assert "Traceback" not in out.out + out.err


@pytest.mark.parametrize("field", ["note", "tattoo"])
@pytest.mark.parametrize("marker", [
    "<!-- delta:sess_x.note.1 -->",
    "<!-- memento-history: x -->",
    "<!--delta:sess_x.note.1 -->",
    "<!--\tdelta:sess_x.note.1 -->",
    "<!--\n delta:sess_x.note.1 -->",
])
def test_reserved_marker_rejected_before_any_write_and_retry_succeeds(tmp_path: Path, field: str, marker: str):
    root = _init(tmp_path)
    project = root / "project"
    project.mkdir()
    (project / "memory.md").write_text("# Project Memory\n\n## State\n\n- Old state.\n", encoding="utf-8")
    before = _snapshot(root)

    spec = _spec()
    clean = spec[field]
    spec[field] = f"{clean} {marker}"
    result = save_commit(spec, root=root)

    assert not result.ok
    assert "reserved record marker" in result.error
    assert _snapshot(root) == before
    assert not (root / "sessions" / "sess_t001.md").exists()

    spec[field] = clean
    retry = save_commit(spec, root=root)
    assert retry.ok, retry.error
    assert (root / "sessions" / "sess_t001.md").exists()
