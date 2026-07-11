from pathlib import Path
import pytest

from memento_tattoo.retention import (
    append_retention_event,
    classify,
    read_retention_events,
    recurrence_counts,
    retention_health_rate,
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


def test_retention_health_rate_uses_shipped_decisions_and_legacy_alias(tmp_path: Path):
    append_retention_event({"decision": "new", "note_id": "sess_a.note.11111111"}, root=tmp_path)
    append_retention_event({"decision": "existing-missed", "note_id": "sess_b.note.22222222"}, root=tmp_path)
    append_retention_event({"decision": "existing-repaired", "note_id": "sess_c.note.33333333"}, root=tmp_path)

    assert retention_health_rate(root=tmp_path) == 0.5
    assert repeat_correction_rate(root=tmp_path) == retention_health_rate(root=tmp_path)


def test_classify_new_when_no_dominant_candidate(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_a.note.11111111 -->\n"
        "Situation: proofreading public prose\n"
        "Note: scan for banned punctuation\n",
        encoding="utf-8",
    )

    result = classify("GPU quota planning", root=tmp_path)

    assert result["suggested_decision"] == "new"


def test_strong_cover_with_close_high_neighbor_suggests_existing_missed(tmp_path: Path):
    # The real-world failure the dominance-ratio guard mis-handled: a genuine same-lesson
    # cover scores high in absolute terms (many matched terms) but a vocabulary neighbor
    # also scores high, so top/second is well under 1.5x. The old guard called this 'new'.
    # A strong absolute match is a cover even when a neighbor is close.
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_c1.note.cccccccc -->\n"
        "Situation: configuring a kubernetes deployment rollout with replica readiness probe liveness ingress namespace selector affinity toleration\n"
        "Note: the real covering lesson about deployment rollout\n\n"
        "<!-- delta:sess_c2.note.dddddddd -->\n"
        "Situation: kubernetes deployment rollout replica readiness probe liveness ingress namespace selector\n"
        "Note: a different high-overlap vocabulary neighbor\n",
        encoding="utf-8",
    )
    result = classify(
        "kubernetes deployment rollout replica readiness probe liveness ingress namespace selector affinity toleration",
        root=tmp_path,
    )
    top, second = result["candidates"][0], result["candidates"][1]
    assert top["score"] < 1.5 * second["score"]  # co-high tie, not a dominance case
    assert top["score"] >= 120  # strong absolute match
    assert top["note_id"] == "sess_c1.note.cccccccc"
    assert result["has_cover"] is True
    assert result["suggested_decision"] == "existing-missed"


def test_note_add_logs_checked_reflection(tmp_path: Path):
    applied, marker = note_add("Situation: publish prep\nNote: sanitize examples", sess="sess_new", root=tmp_path)

    events = read_retention_events(root=tmp_path)

    assert applied is True
    assert marker
    assert len(events) == 1
    assert events[0]["kind"] == "reflection"
    assert events[0]["decision"] == "new"


def test_note_add_retention_event_uses_stable_note_id_with_agent_metadata(tmp_path: Path):
    applied, marker = note_add(
        "Situation: publish prep\nNote: sanitize examples",
        sess="sess_abcd",
        root=tmp_path,
        agent="codex",
    )

    events = read_retention_events(root=tmp_path)

    assert applied is True
    assert "agent=codex" in marker
    assert events[0]["note_id"].startswith("sess_abcd.note.")
    assert "agent=" not in events[0]["note_id"]
    assert "ts=" not in events[0]["note_id"]


def test_checked_note_replay_does_not_duplicate_retention_event(tmp_path: Path):
    text = "Situation: publish prep\nNote: sanitize examples"

    first, first_marker = note_add(text, sess="sess_new", root=tmp_path, kind="reflection")
    second, second_marker = note_add(text, sess="sess_new", root=tmp_path, kind="reflection")

    events = read_retention_events(root=tmp_path)

    assert first is True
    assert second is False
    assert first_marker == second_marker
    assert len(events) == 1


def test_note_add_can_record_agent_retention_judgment(tmp_path: Path):
    applied, _ = note_add(
        "Situation: repeated completion claim\nNote: repaired the verification trigger",
        sess="sess_judge",
        root=tmp_path,
        kind="correction",
        decision="existing-missed",
        covered_note_id="sess_old.note.11111111",
    )

    events = read_retention_events(root=tmp_path)

    assert applied is True
    assert events[0]["decision"] == "existing-missed"
    assert events[0]["cover_note_id"] == "sess_old.note.11111111"
    assert "repair" not in events[0]
    assert "review_needed" not in events[0]
    assert "decided_by" not in events[0]
    assert recurrence_counts(root=tmp_path) == {"sess_old.note.11111111": 1}


def test_seed_note_rejects_retention_judgment(tmp_path: Path):
    with pytest.raises(ValueError, match="retention judgment requires correction, reflection, or pattern"):
        note_add(
            "Situation: import\nNote: seed data",
            sess="sess_seed",
            root=tmp_path,
            kind="seed",
            decision="new",
        )


def test_classify_cluster_cover_uses_shared_tags_when_flat_high(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_a.note.aaaaaaaa -->\n"
        "Situation: save work forgets to print the driver stdout block\n"
        "Note: print the save-commit stdout verbatim.\n"
        "tags: save-work, verification\n\n"
        "<!-- delta:sess_b.note.bbbbbbbb -->\n"
        "Situation: save work output replaces the driver summary by hand\n"
        "Note: never hand-compose the save summary.\n"
        "tags: save-work, release\n\n"
        "<!-- delta:sess_c.note.cccccccc -->\n"
        "Situation: work output summary has many generic words\n"
        "Note: unrelated high-overlap neighbor.\n"
        "tags: unrelated\n",
        encoding="utf-8",
    )

    result = classify(
        "save work output summary misses driver stdout replaces hand compose release verification",
        root=tmp_path,
        min_score=60,
    )

    assert result["has_cover"] is True
    assert result["suggested_decision"] == "existing-missed"
    assert result["cover_note_id"] == "sess_b.note.bbbbbbbb"


def test_recurrence_counts_tolerates_legacy_existing_repaired_and_cover_field(tmp_path: Path):
    append_retention_event(
        {"decision": "existing-repaired", "note_id": "sess_new.note.11111111", "cover_note_id": "sess_old.note.22222222"},
        root=tmp_path,
    )

    assert recurrence_counts(root=tmp_path) == {"sess_old.note.22222222": 1}
