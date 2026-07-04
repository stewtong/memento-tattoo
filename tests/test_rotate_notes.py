from pathlib import Path

from memento_tattoo.recall import load_memento_notes
from memento_tattoo.write_through import note_add, rotate_hot_notes


def _block(i: int, pad: str = "") -> str:
    return (
        f"<!-- delta:sess_{i:04d}.note.{i:08x} agent=cc ts=2026-07-04T00:00:0{i % 10}Z -->\n"
        f"Situation: situation number {i} {pad}\n"
        f"Note: lesson body {i} {pad}\n\n"
    )


PREAMBLE = "# Notes\n<!-- header -->\n\n"


def _write_hot(root: Path, n: int, pad: str = "") -> Path:
    hot = root / "notes.md"
    hot.write_text(PREAMBLE + "".join(_block(i, pad) for i in range(n)), encoding="utf-8")
    return hot


def test_under_threshold_is_noop(tmp_path):
    hot = _write_hot(tmp_path, 3)
    arc = tmp_path / "notes_archive.md"
    before = hot.read_text()
    assert rotate_hot_notes(hot, arc, threshold=100_000, target=90_000) == 0
    assert hot.read_text() == before
    assert not arc.exists()


def test_over_threshold_moves_oldest_and_stays_under_target(tmp_path):
    hot = _write_hot(tmp_path, 12)
    arc = tmp_path / "notes_archive.md"
    moved = rotate_hot_notes(hot, arc, threshold=700, target=600)
    assert moved > 0
    assert len(hot.read_text().encode()) <= 700
    assert "sess_0000.note" not in hot.read_text()
    assert "sess_0000.note" in arc.read_text()
    assert "sess_0011.note" in hot.read_text()
    assert hot.read_text().startswith(PREAMBLE)


def test_no_blocks_lost_across_rotation(tmp_path):
    hot = _write_hot(tmp_path, 12)
    arc = tmp_path / "notes_archive.md"
    rotate_hot_notes(hot, arc, threshold=700, target=600)
    combined = hot.read_text() + arc.read_text()
    for i in range(12):
        assert f"sess_{i:04d}.note.{i:08x}" in combined


def test_no_delta_markers_is_noop(tmp_path):
    hot = tmp_path / "notes.md"
    big = "# Notes\n" + ("<!-- pad -->\n" * 200)
    hot.write_text(big, encoding="utf-8")
    arc = tmp_path / "notes_archive.md"
    assert rotate_hot_notes(hot, arc, threshold=500, target=400) == 0
    assert hot.read_text() == big


def test_archive_created_when_missing(tmp_path):
    hot = _write_hot(tmp_path, 12)
    arc = tmp_path / "notes_archive.md"
    assert not arc.exists()
    assert rotate_hot_notes(hot, arc, threshold=700, target=600) > 0
    assert arc.exists()
    assert "sess_0000.note" in arc.read_text()


def test_keeps_at_least_the_newest_block(tmp_path):
    hot = _write_hot(tmp_path, 1, pad="x" * 2000)
    arc = tmp_path / "notes_archive.md"
    assert rotate_hot_notes(hot, arc, threshold=500, target=400) == 0
    assert "sess_0000.note" in hot.read_text()


def test_missing_hot_is_noop(tmp_path):
    hot = tmp_path / "notes.md"
    arc = tmp_path / "notes_archive.md"
    assert rotate_hot_notes(hot, arc, threshold=500, target=400) == 0


def test_note_add_rotates_when_over_line(tmp_path, monkeypatch):
    _write_hot(tmp_path, 12)
    hot = tmp_path / "notes.md"
    arc = tmp_path / "notes_archive.md"
    monkeypatch.setattr("memento_tattoo.write_through.HOT_NOTES_ROTATE_BYTES", 700)
    monkeypatch.setattr("memento_tattoo.write_through.HOT_NOTES_TARGET_BYTES", 600)
    note_add("Situation: brand new lesson\nNote: keep me hot", sess="sess_new1", root=tmp_path, kind="reflection")
    assert "sess_new1.note" in hot.read_text()
    assert len(hot.read_text().encode()) <= 700
    assert "sess_0000.note" in arc.read_text()
    # rotated-out note still retrievable (recall reads hot + archive)
    ids = {n.note_id for n in load_memento_notes(tmp_path)}
    assert "sess_0000.note.00000000" in ids


def test_seed_note_also_rotates(tmp_path, monkeypatch):
    _write_hot(tmp_path, 12)
    hot = tmp_path / "notes.md"
    arc = tmp_path / "notes_archive.md"
    monkeypatch.setattr("memento_tattoo.write_through.HOT_NOTES_ROTATE_BYTES", 700)
    monkeypatch.setattr("memento_tattoo.write_through.HOT_NOTES_TARGET_BYTES", 600)
    note_add("Situation: bulk imported\nNote: seed body", sess="sess_seed1", root=tmp_path, kind="seed")
    assert "sess_seed1.note" in hot.read_text()
    assert len(hot.read_text().encode()) <= 700
    assert "sess_0000.note" in arc.read_text()
