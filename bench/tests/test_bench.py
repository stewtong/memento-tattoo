import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest

from memento_bench import metrics, rankers
from memento_bench.pit import NoteRecord, Revision, corpus_at, state_at, strictly_before
from memento_bench.text import s_stem, tokens


def _note(nid, situation, note="", **extra):
    fields = {"note_id": nid, "situation": situation, "note": note, "why": "", "aliases": [], "tags": [],
              "superseded_by": ""}
    fields.update(extra)
    return fields


# Point in time

def test_strictly_before_resolves_ties_toward_exclusion():
    assert strictly_before("2026-08-01T10:00", "2026-08-01T10:01")
    assert not strictly_before("2026-08-01T10:01", "2026-08-01T10:01")
    assert not strictly_before("2026-08-01", "2026-08-01T23:59")  # same day, date-only
    assert strictly_before("2026-07-31", "2026-08-01T00:00")
    assert not strictly_before("", "2026-08-01T00:00")


def test_amended_and_superseded_note_shows_its_original_state_at_event_time():
    original = _note("s1.note.aaaaaaaa", "deploying a service", "check the old port")
    amended = _note("s1.note.aaaaaaaa", "deploying a service", "check the new port",
                    superseded_by="s9.note.bbbbbbbb")
    record = NoteRecord(note_id="s1.note.aaaaaaaa", created="2026-07-01T09:00", created_source="retention_log",
                        current=amended, revisions=(Revision("2026-08-10T12:00", original),))
    successor = NoteRecord(note_id="s9.note.bbbbbbbb", created="2026-08-10T12:00", created_source="retention_log",
                           current=_note("s9.note.bbbbbbbb", "deploying a service on the new cluster"))
    event_ts = "2026-08-05T08:00"  # after creation, before the amendment and the successor

    visible, counts = corpus_at([record, successor], event_ts)

    assert [n["note_id"] for n in visible] == ["s1.note.aaaaaaaa"]
    assert visible[0]["note"] == "check the old port"
    assert visible[0]["superseded_by"] == ""
    assert counts["not_yet_created"] == 1
    assert counts["reconstructed_from_revision"] == 1


def test_revision_at_the_event_minute_counts_as_later():
    before = _note("n", "s", "old")
    record = NoteRecord(note_id="n", created="2026-07-01T09:00", created_source="x",
                        current=_note("n", "s", "new"), revisions=(Revision("2026-08-05T08:00", before),))
    assert state_at(record, "2026-08-05T08:00")["note"] == "old"
    assert state_at(record, "2026-08-05T08:01")["note"] == "new"


def test_supersession_without_history_is_dated_from_its_text():
    marked = _note("n", "s", "x", superseded_by="replaced by the routing plan (2026-07-09)")
    record = NoteRecord(note_id="n", created="2026-06-01T00:00", created_source="x", current=marked)
    early, _ = corpus_at([record], "2026-07-08T00:00")
    late, _ = corpus_at([record], "2026-07-10T00:00")
    assert early[0]["superseded_by"] == ""
    assert late[0]["superseded_by"]


def test_notes_without_creation_time_are_excluded_and_counted():
    record = NoteRecord(note_id="n", created="", created_source="none", current=_note("n", "s"))
    visible, counts = corpus_at([record], "2026-09-01T00:00")
    assert visible == [] and counts["no_creation_time"] == 1


# Tokenizing

@pytest.mark.parametrize("word,stem", [
    ("queries", "query"), ("policies", "policy"), ("taxes", "taxe"),
    ("files", "file"), ("toes", "toe"), ("trees", "tree"),
    ("tests", "test"), ("status", "status"), ("class", "class"),
    ("its", "its"), ("gas", "gas"),
])
def test_s_stemmer_rules(word, stem):
    assert s_stem(word) == stem


def test_tokens_match_whole_words_only():
    assert "art" not in tokens("start the service")
    assert tokens("Files and Tests") == ["file", "test"]


# Rankers

def test_bm25f_prefers_rare_terms_and_situation_field():
    corpus = [
        _note("common", "agent file run", "agent file run agent"),
        _note("rare", "migration rollback on billing", "keep the old column"),
        _note("body-only", "unrelated", "migration rollback noted in passing"),
    ]
    ranked = rankers.BM25FIndex(corpus).rank("billing migration rollback", rankers.BM25FConfig())
    assert ranked[0] == "rare"
    assert ranked.index("rare") < ranked.index("body-only")
    assert "common" not in ranked


def test_bm25f_demotes_superseded_notes():
    corpus = [_note("old", "rotate the api key", superseded_by="new"), _note("new", "rotate the api key")]
    ranked = rankers.BM25FIndex(corpus).rank("rotate api key", rankers.BM25FConfig())
    assert ranked == ["new", "old"]


def test_a0_substring_keeps_the_0_4_0_behavior():
    corpus = [_note("hit", "starting the server")]
    assert rankers.a0_substring("art", corpus) == ["hit"]  # the bug the tokenizer fixes


def test_a0_package_matches_whole_words():
    corpus = [_note("start", "starting the server"), _note("art", "the art direction")]
    assert rankers.a0_package("art", corpus) == ["art"]


def test_a0_package_weights_rare_words():
    corpus = [_note("rare", "agent changed the ledger rounding"), _note("c1", "agent run test"),
              _note("c2", "agent run test build"), _note("c3", "agent test run deploy")]
    assert rankers.a0_package("agent run test ledger", corpus)[0] == "rare"


def test_rrf_votes_then_breaks_ties_by_rank():
    fused = rankers.rrf([["a", "b", "c"], ["b", "a"], ["b"]])
    assert fused[0] == "b"
    assert fused[:3] == ["b", "a", "c"]


# Metrics

def test_ranked_metrics():
    ranked = ["x", "r1", "y", "r2"]
    relevant = {"r1", "r2", "r3"}
    assert metrics.recall_at(ranked, relevant, 2) == pytest.approx(1 / 3)
    assert metrics.hit_at(ranked, relevant, 1) == 0.0
    assert metrics.hit_at(ranked, relevant, 2) == 1.0
    assert metrics.reciprocal_rank(ranked, relevant) == 0.5
    assert metrics.precision_at(ranked, {"r1", "y"}, 4) == 0.5


def test_set_metrics_and_empty_choice():
    assert metrics.set_hit({"a"}, {"a", "b"}) == 1.0
    assert metrics.set_recall({"a"}, {"a", "b"}) == 0.5
    assert metrics.set_precision(set(), {"a"}) is None


def test_paired_bootstrap_excludes_zero_for_a_clear_difference():
    a = [1.0] * 40 + [0.0] * 10
    b = [0.0] * 40 + [1.0] * 10
    mean, lo, hi = metrics.paired_bootstrap_diff(a, b)
    assert mean == pytest.approx(0.6) and lo > 0


# Public synthetic fixture (plan section 5.2)

def _fixture_corpus():
    import json
    from memento_tattoo.recall import load_memento_notes
    root = Path(__file__).resolve().parents[1] / "fixtures" / "ranking-200"
    notes = load_memento_notes(root)
    corpus = [dict(note_id=n.note_id, situation=n.situation, note=n.note, why=getattr(n, "why", ""),
                   aliases=list(n.aliases), tags=list(n.tags or []), superseded_by=n.superseded_by,
                   tier="hot" if n.source_name == "notes.md" else "archive") for n in notes]
    cases = [c for c in json.loads((root / "expected.json").read_text()) if c["phase"] != "w7"]
    return corpus, cases


def _case_passes(case, ranked):
    top = ranked[: case.get("top", 5)]
    ok = all(x in top for x in case.get("must_include", []))
    if "must_exclude_any_other_than" in case:
        ok &= all(x in case["must_exclude_any_other_than"] for x in ranked)
    if "max_results" in case:
        ok &= len(ranked) <= case["max_results"]
    if "order" in case:
        ok &= top[: len(case["order"])] == case["order"]
    return ok


def test_fixture_has_200_notes_and_separates_the_rankers():
    corpus, cases = _fixture_corpus()
    assert len(corpus) == 200
    index, config = rankers.BM25FIndex(corpus), rankers.BM25FConfig()
    for case in cases:
        a0 = _case_passes(case, rankers.a0_substring(case["query"], corpus))
        a1 = _case_passes(case, index.rank(case["query"], config))
        assert a1, case["id"]
        assert a0 == (case["phase"] == "now"), case["id"]


def test_package_ranker_passes_every_now_and_w4_case():
    corpus, cases = _fixture_corpus()
    for case in cases:
        passes = _case_passes(case, rankers.a0_package(case["query"], corpus))
        assert passes, case["id"]  # BM25F shipped in 0.5.0, so every now and w4 case holds


def test_mixed_version_round_trip_on_current_code(tmp_path):
    import subprocess
    script = Path(__file__).resolve().parents[1] / "compat" / "roundtrip.py"
    proc = subprocess.run([sys.executable, str(script), "--python", sys.executable, "--keep", str(tmp_path / "m")],
                          capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2])
    assert proc.returncode == 0, proc.stdout + proc.stderr
