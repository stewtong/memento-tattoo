from __future__ import annotations

from pathlib import Path

from .recall import load_memento_notes
from .retention import recurrence_counts, read_retention_events, repeat_correction_rate


def build_digest(*, root: Path, today: str, promote_threshold: int = 2) -> str:
    today = today[:10]
    notes = load_memento_notes(root)
    lines = ["# Memento gardening digest", "", f"Repeat-correction rate: {repeat_correction_rate(root=root):.2f}", ""]

    def section(title: str, items: list[str]) -> None:
        lines.append(f"## {title}")
        lines.extend(items if items else ["- none"])
        lines.append("")

    section(
        "Stale review items",
        [
            f"- {note.note_id} (review_after {note.review_after}): {note.situation}"
            for note in notes
            if note.review_after and note.review_after <= today
        ],
    )

    missed: dict[str, int] = {}
    for event in read_retention_events(root=root):
        if event.get("decision") == "existing-missed":
            note_id = event.get("note_id", "?")
            missed[note_id] = missed.get(note_id, 0) + 1
    section(
        "Repair candidates",
        [
            f"- {note_id}: {count} missed retrieval(s) (strengthen aliases/Situation)"
            for note_id, count in sorted(missed.items(), key=lambda item: -item[1])
        ],
    )

    by_id = {note.note_id: note for note in notes}
    section(
        "Promotion candidates",
        [
            f"- {note_id} (recurred {count}x): {by_id[note_id].situation if note_id in by_id else '(note not in current files)'} -> review for tattoo"
            for note_id, count in sorted(recurrence_counts(root=root).items(), key=lambda item: -item[1])
            if count >= promote_threshold
        ],
    )
    section("Tattoo merge suggestions", [])
    return "\n".join(lines)
