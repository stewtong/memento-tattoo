from pathlib import Path

from memento_tattoo.write_through import note_add, tattoo_add


def test_note_add_creates_root_and_is_idempotent(tmp_path: Path):
    applied, marker = note_add("Situation: test\nNote: keep it", sess="sess_abcd", root=tmp_path, kind="seed")
    again, again_marker = note_add("Situation: test\nNote: keep it", sess="sess_abcd", root=tmp_path, kind="seed")

    assert applied is True
    assert again is False
    assert marker == again_marker
    text = (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert text.startswith(marker)
    assert marker in text


def test_tattoo_add_writes_tattoos_file(tmp_path: Path):
    applied, marker = tattoo_add("Check the dominant category before trusting aggregate metrics.", sess="sess_abcd", root=tmp_path)

    assert applied is True
    text = (tmp_path / "tattoos.md").read_text(encoding="utf-8")
    assert text.startswith("# Tattoos\n")
    assert marker in text
    assert "Check the dominant category" in text
