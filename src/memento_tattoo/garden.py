from __future__ import annotations

from pathlib import Path

from .recall import load_memento_notes
from .retention import recurrence_counts, read_retention_events, retention_health_rate


DEFAULT_DIGEST_LIMIT = 8


def build_digest(*, root: Path, today: str, promote_threshold: int = 2, limit: int = DEFAULT_DIGEST_LIMIT) -> str:
    today = today[:10]
    notes = load_memento_notes(root)
    lines = [
        "# Memento gardening digest",
        "",
        f"Retention health: {retention_health_rate(root=root):.2f} "
        "(existing-missed / (new + existing-missed); note-write signal, not prevention/application)",
        "",
    ]

    def section(title: str, items: list[str]) -> None:
        if limit > 0 and len(items) > limit:
            lines.append(f"## {title} ({len(items)} total, showing {limit})")
            lines.extend(items[:limit])
            lines.append(f"- ...{len(items) - limit} more; use --limit 0 for the full list.")
        else:
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
        if event.get("decision") == "existing-missed" and event.get("decision_source") == "author":
            note_id = event.get("cover_note_id") or event.get("covered_note_id") or event.get("note_id", "?")
            missed[note_id] = missed.get(note_id, 0) + 1
    section(
        "Repair candidates",
        [
            f"- {note_id}: {count} author-recorded miss(es) (review cause before changing retrieval)"
            for note_id, count in sorted(missed.items(), key=lambda item: -item[1])
        ],
    )

    by_id = {note.note_id: note for note in notes}
    section(
        "Promotion candidates",
        [
            f"- {note_id} (recurred {count}x): {by_id[note_id].situation if note_id in by_id else '(note not in current files)'} -> review for tattoo"
            for note_id, count in sorted(recurrence_counts(root=root, observed_only=True).items(), key=lambda item: -item[1])
            if count >= promote_threshold
        ],
    )
    legacy = [event for event in read_retention_events(root=root) if event.get("decision") in ("existing-missed", "existing-repaired") and event.get("decision_source") != "author"]
    section("Unverified historical classifications", [f"- {len(legacy)} event(s); retained as history, excluded from observed-miss promotion counts."] if legacy else [])
    section("Tattoo merge suggestions", [])
    return "\n".join(lines)


def digest_counts(*, root: Path, today: str, promote_threshold: int = 2) -> dict[str, int]:
    notes = load_memento_notes(root)
    events = read_retention_events(root=root)
    missed = {
        event.get("cover_note_id") or event.get("covered_note_id") or event.get("note_id")
        for event in events if event.get("decision") == "existing-missed" and event.get("decision_source") == "author"
    }
    return {
        "stale": sum(bool(note.review_after and note.review_after <= today[:10]) for note in notes),
        "repair": len(missed - {None}),
        "promote": sum(count >= promote_threshold for count in recurrence_counts(root=root, observed_only=True).values()),
    }
