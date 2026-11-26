"""Parallel save-commit processes appending to one project section.

Records what the package promises under parallel saves: each save either
completes or fails closed with the documented refusal, a completed save is
never lost, a refused save leaves nothing in the project file, and nothing
already there is overwritten. The test does not assert how many saves are
refused; that count is intermittent and may be zero.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

WORKERS = 8
ROUNDS = 3
TIMEOUT = 120
REFUSAL = "pending project operation was superseded or edited"
ORIGINAL = "# Project Memory\n\n## Key Decisions\n\n- keep this decision\n\n## State\n\n- existing state line\n"
SECTION = "## State"


def _spec(sess: str, token: str) -> dict:
    return {
        "sess": sess,
        "agent": "codex",
        "session": {
            "date": "2026-06-17T18:24:00Z",
            "topics": ["parallel", "synthetic"],
            "significance": "low",
            "accomplished": "Synthetic parallel save.",
            "started": "none",
            "pending": "none",
            "insights": "none",
            "files": [],
        },
        "project_edit": {
            "project": "../project",
            "section": SECTION,
            "body": f"- {token}",
            "mode": "append",
            "flow_start": "2026-06-17T18:24:00Z",
        },
    }


def _env() -> dict:
    # No PYTHONPATH: the child imports memento_tattoo from the same
    # interpreter's installed package (editable install or wheel).
    return {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def _write_spec(base: Path, sess: str, token: str) -> Path:
    path = base / f"{sess}.json"
    path.write_text(json.dumps(_spec(sess, token)), encoding="utf-8")
    return path


def _cmd(root: Path, spec: Path) -> list:
    return [sys.executable, "-m", "memento_tattoo", "--root", str(root), "save-commit", "--spec", str(spec)]


def _fresh_layout(base: Path) -> tuple[Path, Path]:
    root = base / "memento"
    project = base / "project"
    project.mkdir(parents=True)
    (project / "memory.md").write_text(ORIGINAL, encoding="utf-8")
    return root, project


def _leftovers(*dirs: Path) -> set[str]:
    found = set()
    for top in dirs:
        for path in top.rglob("*"):
            name = path.name
            if path.is_file() and (name.endswith(".tmp") or "lock" in name.lower()):
                found.add(f"{top.name}/{path.relative_to(top)}")
    return found


def _baseline_leftovers(tmp_path: Path) -> set[str]:
    """Names a single clean save leaves behind, relative to its root and project."""
    base = tmp_path / "baseline"
    base.mkdir()
    root, project = _fresh_layout(base)
    spec = _write_spec(base, "sess_t000", "TOKEN_BASELINE")
    done = subprocess.run(_cmd(root, spec), env=_env(), text=True, capture_output=True, timeout=TIMEOUT)
    assert done.returncode == 0 and "RESULT ok" in done.stdout, done.stdout + done.stderr
    return _leftovers(root, project)


def check_invariants(results, memory_after: str, root: Path, project: Path, allowed_leftovers: set[str]) -> None:
    """Raise AssertionError when any parallel-save invariant is broken.

    results: list of dicts with sess, token, returncode, stdout, stderr.
    """
    ok_tokens, refused_tokens = [], []
    for item in results:
        out = item["stdout"] + item["stderr"]
        assert "Traceback" not in out, f"{item['sess']}: traceback in output: {out}"
        lines = [line for line in item["stdout"].splitlines() if line.startswith("RESULT ")]
        assert len(lines) == 1, f"{item['sess']}: expected one RESULT line, got {out}"
        if item["returncode"] == 0:
            assert lines[0] == "RESULT ok", f"{item['sess']}: {out}"
            ok_tokens.append(item)
        else:
            assert lines[0].startswith("RESULT FAIL"), f"{item['sess']}: {out}"
            assert REFUSAL in lines[0], f"{item['sess']}: undocumented failure: {out}"
            refused_tokens.append(item)

    for item in ok_tokens:
        count = memory_after.count(item["token"])
        assert count == 1, f"ok save {item['sess']}: token appears {count} times in project memory"
        assert (root / "sessions" / f"{item['sess']}.md").is_file(), f"ok save {item['sess']}: session file missing"
    for item in refused_tokens:
        assert item["token"] not in memory_after, f"refused save {item['sess']}: token present (partial write)"

    for item in results:
        assert memory_after.count(item["token"]) <= 1, f"token for {item['sess']} written twice"
    assert memory_after.startswith(ORIGINAL.rstrip("\n")), "pre-existing project content was altered"

    extra = _leftovers(root, project) - allowed_leftovers
    assert not extra, f"unexpected leftover files: {sorted(extra)}"


def _run_round(base: Path, allowed: set[str], round_no: int) -> None:
    base.mkdir()
    root, project = _fresh_layout(base)
    jobs = []
    for index in range(WORKERS):
        sess = f"sess_t{round_no}{index:02d}"
        token = f"PARALLEL_TOKEN_R{round_no}_W{index}_X"
        jobs.append((sess, token, _write_spec(base, sess, token)))
    procs = [
        (sess, token, subprocess.Popen(_cmd(root, spec), env=_env(), text=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        for sess, token, spec in jobs
    ]
    results = []
    try:
        for sess, token, proc in procs:
            try:
                out, err = proc.communicate(timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                pytest.fail(f"{sess}: save-commit timed out after {TIMEOUT}s")
            results.append({"sess": sess, "token": token, "returncode": proc.returncode,
                            "stdout": out, "stderr": err})
    finally:
        for _, _, proc in procs:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
    memory_after = (project / "memory.md").read_text(encoding="utf-8")
    check_invariants(results, memory_after, root, project, allowed)


def test_parallel_save_commit_invariants(tmp_path: Path):
    allowed = _baseline_leftovers(tmp_path)
    for round_no in range(ROUNDS):
        _run_round(tmp_path / f"round{round_no}", allowed, round_no)


def _doctored_inputs(tmp_path: Path):
    root = tmp_path / "root"
    project = tmp_path / "project"
    (root / "sessions").mkdir(parents=True)
    project.mkdir()
    (root / "sessions" / "sess_t900.md").write_text("x", encoding="utf-8")
    memory = ORIGINAL + "\n- TOKEN_A\n"
    result = {"sess": "sess_t900", "token": "TOKEN_A", "returncode": 0,
              "stdout": "RESULT ok\n", "stderr": ""}
    return root, project, memory, result


def test_checker_accepts_consistent_inputs(tmp_path: Path):
    root, project, memory, result = _doctored_inputs(tmp_path)
    check_invariants([result], memory, root, project, set())


def test_checker_rejects_doctored_inputs(tmp_path: Path):
    root, project, memory, result = _doctored_inputs(tmp_path)
    refused = {**result, "returncode": 1, "stdout": f"RESULT FAIL error={REFUSAL}; review\n"}
    cases = {
        "ok token missing": lambda: check_invariants([result], ORIGINAL, root, project, set()),
        "ok token twice": lambda: check_invariants([result], memory + "- TOKEN_A\n", root, project, set()),
        "ok session file missing": lambda: check_invariants(
            [{**result, "sess": "sess_t901"}], memory, root, project, set()),
        "refused token present": lambda: check_invariants([refused], memory, root, project, set()),
        "original overwritten": lambda: check_invariants([result], "# Project Memory\n- TOKEN_A\n", root, project, set()),
        "other failure": lambda: check_invariants(
            [{**result, "returncode": 1, "stdout": "RESULT FAIL error=disk full\n"}], ORIGINAL, root, project, set()),
        "traceback": lambda: check_invariants(
            [{**result, "stderr": "Traceback (most recent call last):"}], memory, root, project, set()),
    }
    for name, call in cases.items():
        with pytest.raises(AssertionError):
            call()
            pytest.fail(f"checker accepted doctored case: {name}")
    (root / "leftover.tmp").write_text("x", encoding="utf-8")
    with pytest.raises(AssertionError):
        check_invariants([result], memory, root, project, set())
