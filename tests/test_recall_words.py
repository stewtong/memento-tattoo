from pathlib import Path

import pytest

from memento_tattoo.recall import _fold_plural, _terms, _words, rank_memento_notes


def _notes(tmp_path: Path, *blocks: tuple[str, str, str]) -> Path:
    body = "".join(
        f"<!-- delta:sess_w.note.{suffix} -->\nSituation: {situation}\nNote: {note}\n\n"
        for suffix, situation, note in blocks
    )
    (tmp_path / "notes.md").write_text(body, encoding="utf-8")
    return tmp_path


def _ranked_ids(query: str, root: Path) -> list[str]:
    return [item.note.note_id for item in rank_memento_notes(query, root=root)]


def test_query_word_does_not_match_inside_a_longer_word(tmp_path: Path):
    root = _notes(
        tmp_path,
        ("aaaa0001", "starting the server after a restart", "check the port first"),
        ("aaaa0002", "choosing the art direction", "use the brand kit colors"),
    )
    assert _ranked_ids("art", root) == ["sess_w.note.aaaa0002"]


def test_log_does_not_match_login_catalog_or_blog(tmp_path: Path):
    root = _notes(
        tmp_path,
        ("bbbb0001", "fixing the login page", "clear the session cookie"),
        ("bbbb0002", "updating the product catalog and blog", "rebuild the index"),
        ("bbbb0003", "reading service logs", "query the log index by trace ID"),
    )
    assert _ranked_ids("log", root) == ["sess_w.note.bbbb0003"]


@pytest.mark.parametrize(
    "query, note_text",
    [("rollbacks", "planning a rollback"), ("rollback", "planning rollbacks"), ("policy", "editing retry policies")],
)
def test_plural_and_singular_match_each_other(tmp_path: Path, query: str, note_text: str):
    root = _notes(tmp_path, ("cccc0001", note_text, "follow the runbook"))
    assert _ranked_ids(query, root) == ["sess_w.note.cccc0001"]


def test_compound_words_match_their_parts(tmp_path: Path):
    root = _notes(tmp_path, ("dddd0001", "running save-commit on a spec", "draft the JSON first"))
    assert _ranked_ids("commit", root) == ["sess_w.note.dddd0001"]


def test_plural_folding_follows_harman():
    assert _fold_plural("policies") == "policy"
    assert _fold_plural("rollbacks") == "rollback"
    # Rule 2 keeps the "e", so "index" does not match "indexes": a known limit of plural-only folding.
    assert _fold_plural("indexes") == "indexe"
    assert _fold_plural("status") == "status"
    assert _fold_plural("class") == "class"
    assert _fold_plural("toes") == "toe"
    assert _fold_plural("gas") == "gas"


def test_words_drop_short_words_and_stoplist_but_keep_digit_tokens():
    assert _words("Fix the CI job on k8s and s3 for v2") == ["fix", "job", "k8s", "s3", "v2"]
    assert _terms("docs docs Docs change") == ["doc", "change"]


def test_fast_field_match_equals_whole_word_comparison():
    import random

    from memento_tattoo.recall import _field_hits

    stems = ["policy", "log", "index", "toe", "class", "status", "gas", "s3", "the", "memory", "art", "rollback", "key"]
    forms = [w for s in stems for w in (s, s + "s", s + "es", s[:-1] + "ies" if s.endswith("y") else s)]
    rng = random.Random(3)
    for _ in range(500):
        text = " ".join(rng.choice(forms + ["start", "login", "catalog", "x"]) for _ in range(rng.randint(0, 8)))
        terms = _terms(" ".join(rng.choice(forms) for _ in range(rng.randint(1, 4))))
        words = set(_words(text))
        assert _field_hits(text, terms) == [t for t in terms if t in words], (text, terms)
