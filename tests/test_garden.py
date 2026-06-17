from pathlib import Path

from memento_tattoo.garden import build_digest
from memento_tattoo.retention import append_retention_event


def test_garden_digest_lists_stale_and_promotion_candidates(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "<!-- delta:sess_a.note.11111111 -->\n"
        "Situation: publishing docs\n"
        "Note: sanitize examples\n"
        "review_after: 2026-01-01\n",
        encoding="utf-8",
    )
    append_retention_event({"decision": "existing-missed", "note_id": "sess_a.note.11111111"}, root=tmp_path)
    append_retention_event({"decision": "existing-repaired", "note_id": "sess_a.note.11111111"}, root=tmp_path)

    digest = build_digest(root=tmp_path, today="2026-06-17")

    assert "Stale review items" in digest
    assert "sess_a.note.11111111" in digest
    assert "Promotion candidates" in digest
    assert "recurred 2x" in digest
