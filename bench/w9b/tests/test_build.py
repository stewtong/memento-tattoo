import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build  # noqa: E402

BY_ID = {i: {"id": i, "path": "a.go", "diff_hunk": "@@ x", "body": f"comment {i}"} for i in "abcd"}
PAIRS = [{"id": "a:b", "earlier": "a", "later": "b"}, {"id": "c:d", "earlier": "c", "later": "d"}]


def test_failed_call_stops_the_run_instead_of_splitting(tmp_path, monkeypatch):
    calls = []

    def boom(cache, model, prompt, stage):
        calls.append(prompt)
        raise RuntimeError("workspace is out of credits")

    monkeypatch.setattr(build, "_tf_call", boom)
    with pytest.raises(RuntimeError, match="out of credits"):
        build._decide(tmp_path, "zai-org/GLM-5.3-Flash", PAIRS, BY_ID, "label")
    assert len(calls) == 1  # no split into smaller batches


def test_empty_reply_splits_the_batch(tmp_path, monkeypatch):
    def reply(cache, model, prompt, stage):
        if prompt.count("### Pair") > 1:
            raise build.EmptyReply("burned")
        return '{"decisions": [{"id": "p1", "instruction": "", "same": false}]}'

    monkeypatch.setattr(build, "_tf_call", reply)
    assert build._decide(tmp_path, "zai-org/GLM-5.3-Flash", PAIRS, BY_ID, "label") == {"a:b": False, "c:d": False}


def test_label_refuses_to_write_with_undecided_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "_jsonl", lambda path: PAIRS)
    monkeypatch.setattr(build, "_lesson_rows", lambda cache: list(BY_ID.values()))
    monkeypatch.setattr(build, "_decide_all", lambda cache, who, pairs, by_id, stage:
                        {"a:b": True, "c:d": False} if who != build.CONFIRMER else {})
    with pytest.raises(SystemExit, match="undecided"):
        build.label(tmp_path, "zai-org/GLM-5.3-Flash")
    assert not (tmp_path / "labels.json").exists()
