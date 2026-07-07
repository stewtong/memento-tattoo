from pathlib import Path

from memento_tattoo.write_through import note_situation_altitude_hint


def test_phase_label_situation_warns(tmp_path: Path):
    note = "Situation: Example parser Phase 3 Operator Health v2 implementation\nNote: shipped the health surface."

    hint = note_situation_altitude_hint(note, root=tmp_path)

    assert hint is not None
    assert "project's memory.md" in hint


def test_symptom_situation_passes_clean(tmp_path: Path):
    note = (
        "Situation: an Edit tool call fails with 'File has been modified since read' "
        "after a concurrent write.\nNote: reconcile by reading the live file."
    )

    assert note_situation_altitude_hint(note, root=tmp_path) is None


def test_trigger_clause_passes_clean(tmp_path: Path):
    note = "Situation: when a search returns no results for a canonical entity, suspect the default filter.\nNote: pass the broadest scope."

    assert note_situation_altitude_hint(note, root=tmp_path) is None


def test_empty_situation_returns_none(tmp_path: Path):
    assert note_situation_altitude_hint("", root=tmp_path) is None


def test_generic_noun_phrase_without_label_shape_does_not_warn(tmp_path: Path):
    note = "Situation: a passing thought about nothing in particular\nNote: keep it if useful."

    assert note_situation_altitude_hint(note, root=tmp_path) is None
