from pathlib import Path

from scripts.retention_eval import EvalReport, EvalResult, evaluate_retention_loop


def test_retention_eval_reports_cover_detection_and_false_positive_rates(tmp_path: Path):
    report = evaluate_retention_loop(tmp_path)

    assert report.cover_queries == 3
    assert report.cover_hits == 3
    assert report.negative_queries == 3
    assert report.false_positives == 0
    assert report.cover_detection_coverage == 1.0
    assert report.false_positive_rate == 0.0


def test_retention_eval_uses_classification_properties_not_note_ids(tmp_path: Path):
    report = evaluate_retention_loop(tmp_path)

    assert all(result.suggested_decision in {"new", "related"} for result in report.results)
    assert all(result.expected_cover == result.has_cover for result in report.results)


def test_retention_eval_counts_only_the_related_classification_as_a_cover():
    report = EvalReport(
        results=(
            EvalResult("mismatched-positive", "query", True, True, "new"),
            EvalResult("mismatched-negative", "query", False, True, "related"),
        )
    )

    assert report.cover_hits == 0
    assert report.false_positives == 1
