from datetime import date
from pathlib import Path

from memento_tattoo.tattoo_audit import audit_tattoos, tattoo_audit_report


def _seed_session(root: Path, sess: str, when: str) -> None:
    sessions = root / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    (sessions / f"{sess}.md").write_text(
        f"---\n[{sess} | {when} | codex | test | low]\n"
        "Accomplished: x\nStarted: none\nPending: none\nInsights: none\nFiles: none\n---\n",
        encoding="utf-8",
    )


def _seed_tattoos(root: Path, body: str) -> None:
    (root / "tattoos.md").write_text("# Tattoos\n\n" + body, encoding="utf-8")


def _by_text(candidates, needle):
    for c in candidates:
        if needle in c.text:
            return c
    raise AssertionError(f"no candidate matching {needle!r} in {[c.text for c in candidates]}")


# (a) ts older than window -> flagged, past-window reason
def test_ts_older_than_window_is_flagged(tmp_path: Path):
    _seed_session(tmp_path, "sess_anch", "2026-06-17 10:00")
    _seed_tattoos(
        tmp_path,
        "<!-- delta:sess_old.tattoo.aaaaaaaa agent=codex ts=2026-01-01T00:00:00Z -->\n"
        "- Old tattoo bullet.\n",
    )
    c = _by_text(audit_tattoos(tmp_path), "Old tattoo bullet")
    assert c.flagged is True
    assert c.age_days is not None and c.age_days > 30
    assert "past" in c.reason


# (b) within window -> not flagged
def test_within_window_not_flagged(tmp_path: Path):
    _seed_session(tmp_path, "sess_anch", "2026-06-17 10:00")
    _seed_tattoos(
        tmp_path,
        "<!-- delta:sess_new.tattoo.bbbbbbbb agent=codex ts=2026-06-10T00:00:00Z -->\n"
        "- Recent tattoo bullet.\n",
    )
    c = _by_text(audit_tattoos(tmp_path), "Recent tattoo bullet")
    assert c.flagged is False
    assert c.age_days == 7


# (c) attr-less marker resolved via origin session-date join
def test_attrless_marker_resolved_via_origin_session(tmp_path: Path):
    _seed_session(tmp_path, "sess_anch", "2026-06-17 10:00")
    _seed_session(tmp_path, "sess_orig", "2026-01-01 09:00")
    _seed_tattoos(
        tmp_path,
        "<!-- delta:sess_orig.tattoo.cccccccc -->\n- Attrless tattoo bullet.\n",
    )
    c = _by_text(audit_tattoos(tmp_path), "Attrless tattoo bullet")
    assert c.origin_sess == "sess_orig"
    assert c.age_days is not None and c.flagged is True


# (d) reviewed token newer than origin resets the clock
def test_reviewed_token_resets_clock(tmp_path: Path):
    _seed_session(tmp_path, "sess_anch", "2026-06-17 10:00")
    _seed_session(tmp_path, "sess_rev", "2026-06-15 09:00")
    _seed_tattoos(
        tmp_path,
        "<!-- delta:sess_old.tattoo.dddddddd agent=codex ts=2026-01-01T00:00:00Z -->\n"
        "- Reviewed tattoo bullet. reviewed:sess_rev\n",
    )
    c = _by_text(audit_tattoos(tmp_path), "Reviewed tattoo bullet")
    assert c.reviewed_sess == "sess_rev"
    assert c.flagged is False
    assert "last reviewed" in c.reason


# (e) bullet with no marker -> flagged, no-provenance reason
def test_markerless_bullet_flagged_unknown_provenance(tmp_path: Path):
    _seed_session(tmp_path, "sess_anch", "2026-06-17 10:00")
    _seed_tattoos(tmp_path, "- Orphan bullet without any marker.\n")
    c = _by_text(audit_tattoos(tmp_path), "Orphan bullet")
    assert c.origin_sess is None
    assert c.reviewed_sess is None
    assert c.age_days is None
    assert c.flagged is True
    assert "no resolvable provenance" in c.reason


# (f) empty/missing tattoos.md -> empty list, report says nothing due
def test_missing_tattoos_file(tmp_path: Path):
    _seed_session(tmp_path, "sess_anch", "2026-06-17 10:00")
    assert audit_tattoos(tmp_path) == []
    report = tattoo_audit_report(tmp_path)
    assert "Nothing due for review." in report
    assert "0 tattoos" in report


# (g) anchor defaults to latest session date when now not passed
def test_anchor_defaults_to_latest_session_date(tmp_path: Path):
    _seed_session(tmp_path, "sess_early", "2026-06-01 10:00")
    _seed_session(tmp_path, "sess_late", "2026-06-17 10:00")
    _seed_tattoos(
        tmp_path,
        "<!-- delta:sess_x.tattoo.eeeeeeee agent=codex ts=2026-06-10T00:00:00Z -->\n"
        "- Anchor probe bullet.\n",
    )
    # anchor = 2026-06-17 -> age 7; window 5 -> flagged.
    # If anchor were the earliest session (2026-06-01) age would be negative -> not flagged.
    c = _by_text(audit_tattoos(tmp_path, window_days=5), "Anchor probe bullet")
    assert c.age_days == 7
    assert c.flagged is True


# (h) no session files + multiple ts markers -> anchor is max marker ts date
def test_anchor_from_markers_when_no_sessions(tmp_path: Path):
    _seed_tattoos(
        tmp_path,
        "<!-- delta:sess_a.tattoo.11111111 agent=codex ts=2026-06-01T00:00:00Z -->\n"
        "- First marker bullet.\n\n"
        "<!-- delta:sess_b.tattoo.22222222 agent=codex ts=2026-06-20T00:00:00Z -->\n"
        "- Second marker bullet.\n",
    )
    candidates = audit_tattoos(tmp_path, window_days=10)
    # anchor = max marker ts = 2026-06-20
    first = _by_text(candidates, "First marker bullet")
    second = _by_text(candidates, "Second marker bullet")
    assert first.age_days == 19 and first.flagged is True
    assert second.age_days == 0 and second.flagged is False


# (i) reviewed token pointing at a missing session -> flagged distinctly
def test_dangling_reviewed_watermark(tmp_path: Path):
    _seed_session(tmp_path, "sess_anch", "2026-06-17 10:00")
    _seed_tattoos(
        tmp_path,
        "<!-- delta:sess_o.tattoo.33333333 agent=codex ts=2026-06-16T00:00:00Z -->\n"
        "- Dangling reviewed bullet. reviewed:sess_ghost\n",
    )
    c = _by_text(audit_tattoos(tmp_path), "Dangling reviewed bullet")
    assert c.reviewed_sess == "sess_ghost"
    assert c.flagged is True
    assert "sess_ghost" in c.reason
    # age still computed from the marker ts for context
    assert c.age_days is not None


# (j) report buckets are mutually exclusive and sum to the flagged count
def test_report_buckets_mutually_exclusive(tmp_path: Path):
    _seed_session(tmp_path, "sess_anch", "2026-06-17 10:00")
    _seed_tattoos(
        tmp_path,
        "<!-- delta:sess_old.tattoo.44444444 agent=codex ts=2026-01-01T00:00:00Z -->\n"
        "- Past window bullet.\n\n"
        "- Markerless bullet.\n\n"
        "<!-- delta:sess_new.tattoo.55555555 agent=codex ts=2026-06-16T00:00:00Z -->\n"
        "- Fresh bullet.\n",
    )
    report = tattoo_audit_report(tmp_path)
    assert "2 due for review (1 past 30d window, 1 unknown provenance)" in report
