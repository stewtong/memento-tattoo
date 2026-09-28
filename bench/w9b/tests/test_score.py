"""Sampler, scored run and scoring, on synthetic data only (no model calls)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent  # noqa: E402
import sample  # noqa: E402
import score  # noqa: E402


# ----- synthetic cache ------------------------------------------------------

def _write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _repo(root: Path, name: str, n_post: int, n_pre: int = 3, passes: bool = True, with_check: bool = True) -> Path:
    d = root / name.replace("/", "__")
    d.mkdir(parents=True)
    lessons = [{"id": f"{name}-L{i}", "pr": 1000 + i, "created_at": f"2026-01-{i % 28 + 1:02d}T00:00:00Z",
                "path": "pkg/a.go", "paths_glob": "pkg/**", "text": f"use helper number {i} in pkg tests",
                "situation": "writing pkg tests", "edits": []} for i in range(6)]
    queries = []
    for i in range(n_post + n_pre):
        post = i < n_post
        queries.append({"id": f"{name}-Q{i:03d}", "pr": 5000 + i,
                        "pr_opened_at": ("2026-08-01T00:00:00Z" if post else "2026-03-01T00:00:00Z"),
                        "path": "pkg/a.go", "diff_hunk": f"+ helper number {i % 6} in pkg tests",
                        "reference_text": "use the helper", "relevant": [f"{name}-L{i % 6}"], "post_cutoff": post})
    _write_jsonl(d / "lessons.jsonl", lessons)
    _write_jsonl(d / "queries.jsonl", queries)
    (d / "clusters.json").write_text(json.dumps({"clusters": {}, "member_pr": {}, "member_created": {}}))
    if with_check:
        (d / "label_check_round1.json").write_text(json.dumps({"round": 1, "passes": passes, "precision_same": 0.9 if passes else 0.5}))
    return d


# ----- sampler --------------------------------------------------------------

def test_draw_takes_42_each_and_redistributes_shortfall():
    pools = {"a/a": [f"a{i}" for i in range(100)], "b/b": [f"b{i}" for i in range(10)],
             "c/c": [f"c{i}" for i in range(100)], "d/d": [f"d{i}" for i in range(100)]}
    chosen, short = sample.draw(pools, per_repo=42)
    assert short == {"b/b": 32}
    assert len(chosen["b/b"]) == 10
    assert sum(map(len, chosen.values())) == 42 * 4
    extra = {r: len(chosen[r]) - 42 for r in ("a/a", "c/c", "d/d")}
    assert sorted(extra.values()) == [10, 11, 11]  # 32 redrawn evenly, remainder round-robin
    assert all(len(set(v)) == len(v) for v in chosen.values())


def test_draw_caps_a_donor_at_what_it_has():
    pools = {"a/a": [f"a{i}" for i in range(100)], "b/b": [f"b{i}" for i in range(10)],
             "c/c": [f"c{i}" for i in range(100)], "d/d": [f"d{i}" for i in range(50)]}
    chosen, short = sample.draw(pools, per_repo=42)
    assert {r: len(v) for r, v in chosen.items()} == {"a/a": 54, "b/b": 10, "c/c": 54, "d/d": 50}


def test_draw_is_deterministic():
    pools = {"a/a": [f"a{i}" for i in range(80)], "b/b": [f"b{i}" for i in range(80)]}
    assert sample.draw(pools) == sample.draw(pools)


def test_build_sample_filters_repos_and_refuses_overwrite(tmp_path):
    _repo(tmp_path, "x/ok", n_post=50)
    _repo(tmp_path, "y/fail", n_post=50, passes=False)
    _repo(tmp_path, "z/nocheck", n_post=50, with_check=False)
    assert sample.main(["--cache", str(tmp_path)]) == 0
    out = json.loads((tmp_path / "sample.json").read_text())
    assert out["counts"] == {"x/ok": 50} and out["per_repo_target"] == 50
    assert set(out["excluded"]) == {"y/fail", "z/nocheck"}
    assert all(e["query_id"].startswith("x/ok-Q") for e in out["sample"])
    assert sample.main(["--cache", str(tmp_path)]) == 2  # drawn once
    assert sample.main(["--cache", str(tmp_path), "--force"]) == 0


def test_only_post_cutoff_queries_with_relevant_lessons_are_eligible():
    qs = [{"id": "1", "post_cutoff": True, "relevant": ["a"]}, {"id": "2", "post_cutoff": False, "relevant": ["a"]},
          {"id": "3", "post_cutoff": True, "relevant": []}]
    assert [q["id"] for q in sample.eligible(qs)] == ["1"]


# ----- statistics and decision ----------------------------------------------

def test_stratified_bootstrap_clear_difference_excludes_zero():
    pairs = {"r1": [(1.0, 0.0)] * 30 + [(0.0, 0.0)] * 12, "r2": [(1.0, 0.0)] * 25 + [(1.0, 1.0)] * 17}
    diff, lo, hi, n = score.stratified_bootstrap_diff(pairs, rounds=2000)
    assert n == 84 and diff == pytest.approx(55 / 84)
    assert lo > 0 and score.decide(diff, lo, hi) == "advantage"


def test_stratified_bootstrap_null_difference_includes_zero():
    pairs = {"r1": [(1.0, 0.0), (0.0, 1.0)] * 21, "r2": [(1.0, 1.0), (0.0, 0.0)] * 21}
    diff, lo, hi, _ = score.stratified_bootstrap_diff(pairs, rounds=2000)
    assert diff == pytest.approx(0.0)
    assert lo < 0 < hi and score.decide(diff, lo, hi) == "no advantage"


def test_decision_rule():
    assert score.decide(0.05, 0.01, 0.09) == "advantage"
    assert score.decide(0.05, -0.01, 0.11) == "no advantage"
    assert score.decide(-0.05, -0.09, -0.01).startswith("no advantage (baseline higher")


def test_stratified_resampling_stays_within_repository():
    # One repository all ones, one all zeros: every resample keeps each repository's size, so the mean is fixed.
    pairs = {"r1": [(1.0, 0.0)] * 10, "r2": [(0.0, 0.0)] * 30}
    diff, lo, hi, _ = score.stratified_bootstrap_diff(pairs, rounds=500)
    assert diff == lo == hi == pytest.approx(0.25)


# ----- end to end on synthetic data -----------------------------------------

class FakeRunner:
    """Reviews echo whether lessons were supplied; grades say the point was raised only when they were."""

    def __init__(self):
        self.calls = 0

    def __call__(self, prompt, system, cwd):
        self.calls += 1
        if system == agent.GRADE_SYSTEM:
            raised = "LESSONS-SEEN" in prompt
            return json.dumps({"raised_point": raised, "reference_states_reason": True,
                               "reason_compatible": raised})
        return "LESSONS-SEEN use the helper" if "Lessons from earlier reviews" in prompt else "looks fine"


def test_run_and_score_end_to_end(tmp_path, capsys):
    for name in ("x/one", "y/two"):
        _repo(tmp_path, name, n_post=45)
    assert sample.main(["--cache", str(tmp_path), "--per-repo", "42"]) == 0
    runner = FakeRunner()
    arms_to_run = ("memento_lexical", "bm25", "curated_file", "long_file", "no_memory")
    counts = agent.run(tmp_path, runner=runner, arm_names=arms_to_run, check_embeddings=False, progress_every=50)
    assert counts["completed"] == 84 * len(arms_to_run) and counts["failed"] == 0
    err = capsys.readouterr().err
    assert "progress:" in err and "rate" not in err.lower() and "%" not in err
    again = agent.run(tmp_path, runner=runner, arm_names=arms_to_run, check_embeddings=False)
    assert again["jobs"] == 0  # resumable: nothing left to do

    # Retrieval runs for the lexical arms; embeddings stubbed to the bm25 ranking (no fastembed in tests).
    for d in sample.repo_dirs(tmp_path):
        score.retrieve_repo(d, workers=1, arm_names=score.LEXICAL_ARMS)
        runs = json.loads((d / "retrieval_runs.json").read_text())
        runs["runs"]["embeddings"] = runs["runs"]["bm25"]
        (d / "retrieval_runs.json").write_text(json.dumps(runs))
    # Embeddings agent results stubbed as copies of bm25 rows, so the comparison can be computed.
    path = tmp_path / "agent_results.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    with path.open("a") as fh:
        for r in rows:
            if r["arm"] == "bm25":
                fh.write(json.dumps({**r, "arm": "embeddings"}) + "\n")

    results = score.score(tmp_path)
    md = (tmp_path / "results.md").read_text()
    assert md.startswith("memento against the short curated file: **")
    assert "Sample: 84 paired queries (x/one 42, y/two 42)" in md
    pw = results["agent_level"]["power"]
    assert pw["paired_queries"] == 84 and "80% power" in md
    assert "10-point" not in md and "336" not in md  # no claim carried over from the original 336-query design
    ag = results["agent_level"]
    assert ag["arms"]["no_memory"]["raised_point_rate"] == 0.0
    assert ag["arms"]["memento_lexical"]["raised_point_rate"] == 1.0
    assert ag["comparisons"]["no_memory"]["decision"] == "advantage"
    assert ag["comparisons"]["curated_file"]["decision"] == "no advantage"  # both supply lessons in this toy
    assert results["not_run"] == {"memento_paths": score.NOT_RUN["memento_paths"]}
    assert "x/one" in results["label_checks"] and results["label_checks"]["x/one"][0]["passes"] is True
    rl = results["retrieval_level"]["arms"]["bm25"]
    assert rl["all"]["pooled"]["n"] > 0 and "before_2026-07-01" in rl and "after_2026-07-01" in rl


def test_retrieval_metrics_toy_case(tmp_path):
    from memento_bench import metrics as m
    ranked = ["x", "rel", "y"]
    assert m.recall_at(ranked, {"rel"}, 5) == 1.0
    assert m.hit_at(ranked, {"rel"}, 1) == 0.0
    assert m.reciprocal_rank(ranked, {"rel"}) == 0.5


def test_stale_retrieval_runs_are_rejected(tmp_path):
    d = _repo(tmp_path, "x/one", n_post=5)
    score.retrieve_repo(d, workers=1, arm_names=score.LEXICAL_ARMS)
    with (d / "queries.jsonl").open("a") as fh:
        fh.write(json.dumps({"id": "extra", "pr": 1, "pr_opened_at": "2026-08-01T00:00:00Z", "path": "p",
                             "diff_hunk": "", "reference_text": "", "relevant": [], "post_cutoff": True}) + "\n")
    with pytest.raises(SystemExit, match="stale"):
        score._retrieval_level({"x/one": d})


def test_identical_prompts_in_flight_share_one_call(tmp_path):
    import threading
    import time
    calls = []

    def slow(prompt, system, cwd):
        calls.append(1)
        time.sleep(0.2)
        return "same answer"

    out = []
    threads = [threading.Thread(target=lambda: out.append(agent.cached_call(tmp_path, "t1", "p", "s", slow))) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert out == ["same answer"] * 4 and len(calls) == 1
    assert not list((tmp_path / "agent-cache" / "t1").glob("*.tmp*"))


def test_per_repo_parameter_and_shortfall(tmp_path):
    _repo(tmp_path, "x/big", n_post=80)
    _repo(tmp_path, "y/small", n_post=30)
    assert sample.main(["--cache", str(tmp_path), "--per-repo", "50"]) == 0
    out = json.loads((tmp_path / "sample.json").read_text())
    assert out["counts"] == {"x/big": 70, "y/small": 30}  # the 20 missing from y/small redrawn from x/big
    assert out["shortfalls"] == {"y/small": 20} and out["unfilled"] == 0
    with pytest.raises(SystemExit):
        sample.main(["--cache", str(tmp_path), "--per-repo", "0", "--force"])


def test_minimum_detectable_difference_matches_power_py():
    import power
    for pd in power.DISCORDANT:
        n = power.connor_n(0.10, pd)
        assert score.minimum_detectable_difference(n, pd) == pytest.approx(0.10, abs=0.002)
    assert score.minimum_detectable_difference(100, 0.3) > 0.10  # smaller samples detect only larger differences
    assert score.minimum_detectable_difference(0, 0.3) is None


def test_power_statement_reports_actual_n():
    pairs = {"a/a": [(1.0, 0.0)] * 20 + [(1.0, 1.0)] * 30, "b/b": [(0.0, 1.0)] * 10 + [(0.0, 0.0)] * 40}
    pw = score.power_statement(pairs)
    assert pw["paired_queries"] == 100 and pw["per_repo"] == {"a/a": 50, "b/b": 50}
    assert pw["observed_discordance"] == 0.3
    assert pw["mdd_at_observed_discordance"] == pytest.approx(score.minimum_detectable_difference(100, 0.3), abs=1e-4)
