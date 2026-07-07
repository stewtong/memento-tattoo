import json
from pathlib import Path

from memento_tattoo.retention import read_retention_events
from memento_tattoo.write_through import note_add


def _last_event(root: Path) -> dict:
    lines = (root / "retention_log.jsonl").read_text(encoding="utf-8").splitlines()
    return json.loads([line for line in lines if line.strip()][-1])


def test_author_recorded_on_retention_event(tmp_path: Path):
    applied, _ = note_add(
        "Situation: a novel zebra quantum topic\nNote: x",
        sess="sess_a1",
        root=tmp_path,
        kind="reflection",
        author="cc",
    )

    assert applied is True
    assert _last_event(tmp_path)["author"] == "cc"


def test_author_defaults_none_when_unset(tmp_path: Path):
    note_add("Situation: another novel aardvark topic\nNote: x", sess="sess_a2", root=tmp_path)

    assert _last_event(tmp_path)["author"] is None


def test_pattern_kind_writes_note_but_logs_no_event(tmp_path: Path):
    applied, _ = note_add(
        "Situation: when you need a fast cold read from a different model\n"
        "Note: reach for a second-opinion pass.",
        sess="sess_p1",
        root=tmp_path,
        kind="pattern",
        author="cc",
    )

    assert applied is True
    assert "second-opinion" in (tmp_path / "notes.md").read_text(encoding="utf-8")
    assert read_retention_events(root=tmp_path) == []


def test_pattern_does_not_pollute_correction_metric(tmp_path: Path):
    note_add("Situation: novel narwhal topic\nNote: x", sess="sess_r", root=tmp_path, kind="reflection")
    for index in range(3):
        note_add(
            f"Situation: when you hit worked-case {index}\nNote: do X",
            sess=f"sess_pat{index}",
            root=tmp_path,
            kind="pattern",
        )

    events = read_retention_events(root=tmp_path)
    assert len(events) == 1
    assert events[0]["kind"] == "reflection"
