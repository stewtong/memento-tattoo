from pathlib import Path

from memento_tattoo.rebuild import build_generated_files, rebuild


def test_rebuild_writes_session_indexes(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess_a111.md").write_text(
        "---\n[sess_a111 | 2026-06-17 10:00 | codex | docs, tests | medium]\n"
        "Accomplished: A.\nStarted: none.\nPending: none.\nInsights: none.\nFiles: README.md\n---\n",
        encoding="utf-8",
    )

    ok, output = rebuild(tmp_path)

    assert ok, output
    assert "sess_a111" in (sessions / "index.md").read_text(encoding="utf-8")
    assert "sess_a111" in (sessions / "index-recent.md").read_text(encoding="utf-8")


def test_rebuild_check_detects_stale_index(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess_a111.md").write_text(
        "---\n[sess_a111 | 2026-06-17 10:00 | codex | docs | low]\n"
        "Accomplished: A.\nStarted: none.\nPending: none.\nInsights: none.\nFiles: README.md\n---\n",
        encoding="utf-8",
    )
    (sessions / "index.md").write_text("# stale\n", encoding="utf-8")

    ok, output = rebuild(tmp_path, check=True)

    assert not ok
    assert "stale" in output.lower() or "would change" in output.lower()


def test_build_generated_files_sorts_recent_descending(tmp_path: Path):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess_old.md").write_text(
        "---\n[sess_old | 2026-06-01 10:00 | codex | docs | low]\nAccomplished: Old.\n---\n",
        encoding="utf-8",
    )
    (sessions / "sess_new.md").write_text(
        "---\n[sess_new | 2026-06-17 10:00 | claude | tests | high]\nAccomplished: New.\n---\n",
        encoding="utf-8",
    )

    generated = build_generated_files(tmp_path)
    recent = generated[sessions / "index-recent.md"]

    assert recent.index("sess_new") < recent.index("sess_old")


def test_recent_order_normalizes_offsets(tmp_path):
    from memento_tattoo.session_store import render_session_block, write_session_block
    from memento_tattoo.rebuild import rebuild
    for sess, stamp in [('sess_late', '2026-09-05T17:00:00-07:00'), ('sess_early', '2026-09-06T00:30:00+02:00')]:
        block = render_session_block(sess, date=stamp, agent='codex', topics=[], significance='low', accomplished='synthetic', started='none', pending='none', insights='none', files=[])
        write_session_block(tmp_path, block, sess)
    assert rebuild(tmp_path)[0]
    text = (tmp_path / 'sessions/index-recent.md').read_text()
    assert text.index('sess_late') < text.index('sess_early')
