import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent  # noqa: E402
import arms  # noqa: E402


def _lesson(lid, pr, created, text, path="pkg/a/a_test.go", edits=None, situation=""):
    return {"id": lid, "pr": pr, "created_at": created, "path": path, "paths_glob": str(Path(path).parent) + "/**",
            "text": text, "situation": situation, "edits": edits or []}


LESSONS = [
    _lesson("9901001", 1, "2026-01-01T00:00:00Z", "Use t.Helper() in test helpers so failures point at the caller."),
    _lesson("9901002", 2, "2026-02-01T00:00:00Z", "Mark this helper with t.Helper(); failure lines should point at the caller."),
    _lesson("9901003", 3, "2026-03-01T00:00:00Z", "Call t.Helper() in helper functions."),
    _lesson("9901004", 1, "2026-01-05T00:00:00Z", "Wrap errors with fmt.Errorf and %w so callers can use errors.Is.", path="pkg/b/b.go"),
    _lesson("9901005", 2, "2026-02-05T00:00:00Z", "Use %w when wrapping errors.", path="pkg/b/b.go"),
    _lesson("9901006", 3, "2026-03-05T00:00:00Z", "Rename this variable to something descriptive.", path="pkg/c/c.go"),
    _lesson("9901007", 4, "2026-04-01T00:00:00Z", "Add a changelog entry for user-facing changes.", path="CHANGELOG.md",
            edits=[{"edited_at": "2026-05-01T00:00:00Z", "previous_text": "Add a changelog line."}]),
    _lesson("9901008", 4, "2026-04-02T00:00:00Z", "Counter metric names need a _total suffix.", path="pkg/m/m.go",
            edits=[{"edited_at": "2026-05-10T00:00:00Z", "previous_text": None}]),
]
CLUSTERS = {
    "clusters": {"A": ["9901001", "9901002", "9901003"], "B": ["9901004", "9901005"]},
    "member_pr": {l["id"]: l["pr"] for l in LESSONS},
    "member_created": {l["id"]: l["created_at"] for l in LESSONS},
}
Q1 = {"id": "9902001", "pr": 5, "pr_opened_at": "2026-04-15T00:00:00Z", "path": "pkg/a/b_test.go",
      "diff_hunk": "+func assertOK(t *testing.T, err error) {\n+\tif err != nil { t.Fatal(err) }  // test helper, caller line lost\n+}",
      "reference_text": "Add t.Helper() here so the failure points at the caller.",
      "relevant": ["9901001", "9901002", "9901003"], "post_cutoff": False}
Q2 = {"id": "9902002", "pr": 6, "pr_opened_at": "2026-06-01T00:00:00Z", "path": "pkg/b/c.go",
      "diff_hunk": "+return fmt.Errorf(\"open: %v\", err)  // wrapping errors",
      "reference_text": "Use %w so callers can match the error; %v loses it.",
      "relevant": ["9901004", "9901005"], "post_cutoff": False}


def _ids(lessons):
    return {l["id"] for l in lessons}


def test_visible_lessons_point_in_time_and_edits():
    visible, unknown = arms.visible_lessons_counted(Q1, LESSONS)
    by_id = {l["id"]: l for l in visible}
    assert "9901008" not in by_id and unknown == 1  # edited after Q1 opened, earlier text unknown
    assert by_id["9901007"]["text"] == "Add a changelog line."  # edited after Q1 opened: earlier text
    visible2, unknown2 = arms.visible_lessons_counted(Q2, LESSONS)
    by_id2 = {l["id"]: l for l in visible2}
    assert unknown2 == 0 and by_id2["9901008"]["text"] == "Counter metric names need a _total suffix."
    assert by_id2["9901007"]["text"] == "Add a changelog entry for user-facing changes."


def test_visible_lessons_exclude_same_pr_and_later_lessons():
    extra = LESSONS + [_lesson("9901009", 5, "2026-01-10T00:00:00Z", "same PR as Q1"),
                       _lesson("9901010", 2, "2026-04-15T00:00:00Z", "created at the moment Q1 opened")]
    ids = _ids(arms.visible_lessons(Q1, extra))
    assert "9901009" not in ids and "9901010" not in ids
    assert {"9901001", "9901006", "9901007"} <= ids


def test_recurrence_counts_distinct_earlier_prs_excluding_the_query_pr():
    assert arms.recurrence("9901001", Q2, CLUSTERS) == 3
    assert arms.recurrence("9901004", Q2, CLUSTERS) == 2
    assert arms.recurrence("9901006", Q2, CLUSTERS) == 1  # unclustered: minimum 1
    q_in_pr3 = {**Q2, "pr": 3}
    assert arms.recurrence("9901001", q_in_pr3, CLUSTERS) == 2
    early = {**Q2, "pr_opened_at": "2026-01-20T00:00:00Z"}
    assert arms.recurrence("9901001", early, CLUSTERS) == 1  # only PR 1 existed then


def test_curated_orders_by_recurrence_then_recency_and_cuts_at_budget():
    visible = arms.visible_lessons(Q2, LESSONS)
    full = arms.curated_context(Q2, visible, CLUSTERS)
    assert full.lesson_ids[:3] == ["9901003", "9901002", "9901001"]
    assert full.lesson_ids[3:5] == ["9901005", "9901004"]
    small = arms.curated_context(Q2, visible, CLUSTERS, budget=60)
    assert 0 < len(small.lesson_ids) < len(full.lesson_ids)
    assert small.lesson_ids == full.lesson_ids[: len(small.lesson_ids)]
    assert small.tokens <= 60


def test_whole_set_reports_size_and_refuses_over_cap():
    visible = arms.visible_lessons(Q2, LESSONS)
    ctx = arms.whole_set_context(Q2, visible)
    assert len(ctx.lesson_ids) == len(visible) and ctx.tokens == arms.estimate_tokens(ctx.text)
    with pytest.raises(arms.ArmUnavailable, match="over the cap"):
        arms.whole_set_context(Q2, visible, cap=10)


def test_retrieval_arms_rank_the_obvious_lessons_first():
    visible = arms.visible_lessons(Q1, LESSONS)
    for arm in (arms.memento_lexical, arms.bm25):
        assert arm(Q1, visible)[0] in Q1["relevant"], arm.__name__
    visible2 = arms.visible_lessons(Q2, LESSONS)
    for arm in (arms.memento_lexical, arms.bm25):
        assert arm(Q2, visible2)[0] in Q2["relevant"], arm.__name__


def test_paths_arm_is_unavailable_and_embeddings_needs_fastembed():
    with pytest.raises(arms.ArmUnavailable, match="Phase 3"):
        arms.memento_paths(Q1, LESSONS)
    try:
        import fastembed  # noqa: F401
    except ImportError:
        with pytest.raises(arms.ArmUnavailable, match="fastembed"):
            arms.embeddings(Q1, LESSONS)


def test_rendering_carries_no_ids_or_pr_numbers():
    visible = arms.visible_lessons(Q2, LESSONS)
    text = arms.render_lessons(visible)
    for lesson in LESSONS:
        assert lesson["id"] not in text
    assert "PR" not in text and "#" not in text
    assert "Applies to: pkg/a/**" in text


def test_review_prompt_never_contains_reference_or_arm_name():
    ctx = arms.curated_context(Q1, arms.visible_lessons(Q1, LESSONS), CLUSTERS)
    prompt = agent.review_prompt(Q1, ctx)
    assert Q1["reference_text"] not in prompt
    assert "curated" not in prompt.lower() and "memento" not in prompt.lower()
    assert "Lessons from earlier reviews" in prompt
    empty = agent.review_prompt(Q1, arms.no_memory_context(Q1, []))
    assert "Lessons from earlier reviews" not in empty


@pytest.mark.parametrize("raw", [
    '{"raised_point": true, "reference_states_reason": true, "reason_compatible": false}',
    'Here you go:\n```json\n{"raised_point": false, "reference_states_reason": false, "reason_compatible": null}\n```',
])
def test_parse_grade_accepts_plain_and_fenced_json(raw):
    g = agent.parse_grade(raw)
    assert set(g) == {"raised_point", "reason_compatible", "reference_states_reason"}


@pytest.mark.parametrize("raw", ["no json here", '{"raised_point": "yes", "reference_states_reason": true}',
                                 '{"raised_point": true, "reference_states_reason": true, "reason_compatible": "maybe"}',
                                 "{not json}"])
def test_parse_grade_rejects_malformed(raw):
    with pytest.raises(ValueError):
        agent.parse_grade(raw)


def _write_dataset(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "lessons.jsonl").write_text("".join(json.dumps(l) + "\n" for l in LESSONS), encoding="utf-8")
    (cache / "queries.jsonl").write_text("".join(json.dumps(q) + "\n" for q in (Q1, Q2)), encoding="utf-8")
    (cache / "clusters.json").write_text(json.dumps(CLUSTERS), encoding="utf-8")


def test_plumbing_reports_completion_only_never_a_rate(tmp_path):
    cache = tmp_path / "cache"
    _write_dataset(cache)
    calls = []

    def fake_runner(prompt, system, cwd):
        calls.append(system)
        if system == agent.GRADE_SYSTEM:
            return '{"raised_point": true, "reference_states_reason": true, "reason_compatible": true}'
        return "Consider adding t.Helper()."

    report = agent.plumbing(cache, n=5, runner=fake_runner, max_workers=1)
    assert report["queries"] == 2
    def keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from keys(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from keys(v)

    found = set(keys(report))
    assert not found & {"raised_point", "reason_compatible", "reference_states_reason"}
    assert not [k for k in found if "rate" in k.split("_") or k.endswith("rate") or "score" in k]
    assert report["arms"]["memento_paths"]["unavailable"]
    for arm in ("memento_lexical", "bm25", "curated_file", "long_file", "no_memory"):
        entry = report["arms"][arm]
        assert entry["reviews_ok"] == entry["grades_ok"] == entry["contexts"] == 2, arm
        assert entry["excluded_unknown_text"] == 1, arm  # lesson 9901008 before its unknown edit
    assert report["arms"]["no_memory"]["context_tokens"] == [0, 0]
    # a rerun is served from the cache
    before = len(calls)
    agent.plumbing(cache, n=5, runner=fake_runner, max_workers=1)
    assert len(calls) == before


def test_curated_file_never_exceeds_budget_on_real_rendering():
    import arms as A
    lessons = [{"id": f"l{i}", "pr": i, "created_at": f"2026-01-{i % 28 + 1:02d}T00:00:00Z", "path": "a/b.go",
                "paths_glob": "a/**", "text": "x" * (37 + i % 11), "situation": "s" * (5 + i % 3), "edits": []}
               for i in range(300)]
    query = {"id": "q", "pr": 999, "pr_opened_at": "2026-12-01T00:00:00Z", "path": "a/b.go", "diff_hunk": ""}
    ctx = A.curated_context(query, lessons, {"clusters": {}, "member_pr": {}, "member_created": {}}, budget=2000)
    assert ctx.tokens <= 2000


def test_long_file_keeps_newest_lessons_within_32_kib():
    import arms as A
    lessons = [{"id": f"l{i:03d}", "pr": i, "created_at": f"2026-0{1 + i % 9}-{1 + i % 27:02d}T00:00:00Z", "path": "a/b.go",
                "paths_glob": "a/**", "text": "y" * 400, "situation": "when editing b", "edits": []} for i in range(400)]
    query = {"id": "q", "pr": 999, "pr_opened_at": "2026-12-01T00:00:00Z", "path": "a/b.go", "diff_hunk": ""}
    ctx = A.long_file_context(query, lessons)
    assert len(ctx.text.encode("utf-8")) <= A.LONG_FILE_BYTES
    newest = max(lessons, key=lambda l: (l["created_at"], l["id"]))
    oldest = min(lessons, key=lambda l: (l["created_at"], l["id"]))
    assert newest["id"] in ctx.lesson_ids and oldest["id"] not in ctx.lesson_ids
