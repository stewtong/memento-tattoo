from pathlib import Path

from memento_tattoo.tattoo_firing import bump_tattoo_firing, tattoo_firing_counts, tattoo_firing_path
from memento_tattoo.write_through import note_add


TATTOO = "sess_t001.tattoo.03de28d2"


def test_note_citing_tattoo_bumps_counter_as_byproduct(tmp_path: Path):
    note_add(
        f"Situation: when reserving under a lock so a deferred commit cannot collide\n"
        f"Note: reserve at decision time. See [[{TATTOO}]].",
        sess="sess_x1",
        root=tmp_path,
        kind="reflection",
    )

    counts = tattoo_firing_counts(tmp_path)

    assert counts[TATTOO]["count"] == 1
    assert counts[TATTOO]["last_used"]


def test_repeated_citations_increment(tmp_path: Path):
    for index in range(3):
        note_add(
            f"Situation: distinct cited situation {index}\nNote: see [[{TATTOO}]].",
            sess=f"sess_c{index}",
            root=tmp_path,
            kind="reflection",
        )

    assert tattoo_firing_counts(tmp_path)[TATTOO]["count"] == 3


def test_note_without_citation_writes_no_counter(tmp_path: Path):
    note_add("Situation: a novel uncited topic\nNote: nothing linked.", sess="sess_n", root=tmp_path)

    assert not tattoo_firing_path(tmp_path).exists()


def test_seed_import_does_not_inflate(tmp_path: Path):
    note_add(f"Situation: bulk imported note citing [[{TATTOO}]]\nNote: x", sess="sess_seed", root=tmp_path, kind="seed")

    assert tattoo_firing_counts(tmp_path) == {}


def test_pattern_note_does_bump(tmp_path: Path):
    note_add(
        f"Situation: when you want a divergent cold read\nNote: reach for it, cf [[{TATTOO}]].",
        sess="sess_pat",
        root=tmp_path,
        kind="pattern",
    )

    assert tattoo_firing_counts(tmp_path)[TATTOO]["count"] == 1


def test_audit_report_annotates_firing(tmp_path: Path):
    from memento_tattoo.tattoo_audit import tattoo_audit_report

    (tmp_path / "tattoos.md").write_text(
        "# Tattoos\n\n"
        f"<!-- delta:{TATTOO} agent=codex ts=2026-01-01T00:00:00Z -->\n"
        "- Reserve under the same lock at decision time.\n",
        encoding="utf-8",
    )
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "sess_anchor.md").write_text(
        "---\n[sess_anchor | 2026-07-07 10:00 | codex | test | low]\nAccomplished: x\n---\n",
        encoding="utf-8",
    )

    assert "never cited" in tattoo_audit_report(root=tmp_path)
    bump_tattoo_firing(f"see [[{TATTOO}]]", root=tmp_path, now="2026-07-07T10:00:00Z")
    assert "cited 1x" in tattoo_audit_report(root=tmp_path)
