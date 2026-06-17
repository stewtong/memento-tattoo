from pathlib import Path

from memento_tattoo.retention import (
    append_retention_event,
    classify,
    read_retention_events,
    recurrence_counts,
    repeat_correction_rate,
)
from memento_tattoo.write_through import note_add


def test_append_and_read_retention_events(tmp_path: Path):
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=tmp_path)
    append_retention_event({"decision": "existing-missed", "note_id": "sess_a.note.11111111"}, root=tmp_path)

    events = read_retention_events(root=tmp_path)

    assert [event["decision"] for event in events] == ["new", "existing-missed"]
    assert recurrence_counts(root=tmp_path) == {"sess_a.note.11111111": 1}
    assert repeat_correction_rate(root=tmp_path) == 0.5


def test_classify_new_when_no_dominant_candidate(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_a.note.11111111 -->\n"
        "Situation: proofreading public prose\n"
        "Note: scan for banned punctuation\n",
        encoding="utf-8",
    )

    result = classify("GPU quota planning", root=tmp_path)

    assert result["suggested_decision"] == "new"


def test_note_add_logs_checked_reflection(tmp_path: Path):
    applied, marker = note_add("Situation: publish prep\nNote: sanitize examples", sess="sess_new", root=tmp_path)

    events = read_retention_events(root=tmp_path)

    assert applied is True
    assert marker
    assert len(events) == 1
    assert events[0]["kind"] == "reflection"
    assert events[0]["decision"] == "new"


def test_checked_note_replay_does_not_duplicate_retention_event(tmp_path: Path):
    text = "Situation: publish prep\nNote: sanitize examples"

    first, first_marker = note_add(text, sess="sess_new", root=tmp_path, kind="reflection")
    second, second_marker = note_add(text, sess="sess_new", root=tmp_path, kind="reflection")

    events = read_retention_events(root=tmp_path)

    assert first is True
    assert second is False
    assert first_marker == second_marker
    assert len(events) == 1
