"""Deterministic cover-detection evaluation for the retention classifier."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memento_tattoo.retention import classify


@dataclass(frozen=True)
class EvalCase:
    label: str
    query: str
    expected_cover: bool


@dataclass(frozen=True)
class EvalResult:
    label: str
    query: str
    expected_cover: bool
    has_cover: bool
    suggested_decision: str


@dataclass(frozen=True)
class EvalReport:
    results: tuple[EvalResult, ...]

    @property
    def cover_queries(self) -> int:
        return sum(result.expected_cover for result in self.results)

    @property
    def cover_hits(self) -> int:
        return sum(result.expected_cover and _is_cover_detection(result) for result in self.results)

    @property
    def negative_queries(self) -> int:
        return sum(not result.expected_cover for result in self.results)

    @property
    def false_positives(self) -> int:
        return sum(not result.expected_cover and _is_cover_detection(result) for result in self.results)

    @property
    def cover_detection_coverage(self) -> float:
        return self.cover_hits / self.cover_queries if self.cover_queries else 0.0

    @property
    def false_positive_rate(self) -> float:
        return self.false_positives / self.negative_queries if self.negative_queries else 0.0


def _is_cover_detection(result: EvalResult) -> bool:
    return result.has_cover and result.suggested_decision == "related"


CASES = (
    EvalCase(
        label="completion-proof",
        query="reporting a completed change before checking its proof tests",
        expected_cover=True,
    ),
    EvalCase(
        label="public-docs-release",
        query="preparing public documentation for release while leaving internal paths",
        expected_cover=True,
    ),
    EvalCase(
        label="shared-state-edit",
        query="updating shared project state after a concurrent agent edit",
        expected_cover=True,
    ),
    EvalCase(
        label="landing-page-design",
        query="choosing a color palette for a landing page",
        expected_cover=False,
    ),
    EvalCase(
        label="database-timeout",
        query="debugging an intermittent database timeout",
        expected_cover=False,
    ),
    EvalCase(
        label="image-processing",
        query="resizing an image asset for a mobile thumbnail",
        expected_cover=False,
    ),
)


def _seed_corpus(root: Path) -> None:
    (root / "notes.md").write_text(
        "\n".join(
            (
                "<!-- delta:seed.note.11111111 -->",
                "Situation: claiming a code change is complete without running the proof command",
                "Note: run the relevant test before saying done.",
                "aliases: verification, tests, complete, done, proof",
                "",
                "<!-- delta:seed.note.22222222 -->",
                "Situation: publishing documentation with unsanitized examples",
                "Note: remove internal paths and credentials before release.",
                "aliases: docs, release, public, sanitize",
                "",
                "<!-- delta:seed.note.33333333 -->",
                "Situation: editing project memory after another agent changed the same section",
                "Note: preserve newer deltas before replacing shared state.",
                "aliases: multi-agent, conflict, project memory",
                "",
            )
        ),
        encoding="utf-8",
    )


def evaluate_retention_loop(root: Path) -> EvalReport:
    """Seed a fixed corpus and evaluate cover detection on independent queries."""
    _seed_corpus(root)
    results = tuple(
        EvalResult(
            label=case.label,
            query=case.query,
            expected_cover=case.expected_cover,
            has_cover=(classified := classify(case.query, root=root))["has_cover"],
            suggested_decision=classified["suggested_decision"],
        )
        for case in CASES
    )
    return EvalReport(results=results)


def main() -> None:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="memento-retention-eval-") as directory:
        report = evaluate_retention_loop(Path(directory))
    print(
        f"cover-detection coverage: {report.cover_hits}/{report.cover_queries} "
        f"({report.cover_detection_coverage:.2f})"
    )
    print(
        f"false-positive rate: {report.false_positives}/{report.negative_queries} "
        f"({report.false_positive_rate:.2f})"
    )
    print("These figures measure deterministic cover detection, not behavioral repeat reduction.")


if __name__ == "__main__":
    main()
