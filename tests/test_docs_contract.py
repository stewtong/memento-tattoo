from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_canonical_pattern_names_both_adoption_modes_and_coordination_boundary():
    text = _read("MEMENTO-PATTERN.md")

    assert "Adapt this protocol with plain files and repo-local instructions." in text
    assert "Install the reference CLI for deterministic writes and diagnostics." in text
    for guarantee in ("locking", "collision-safe IDs", "idempotent writes", "atomic moves", "complete-batch validation", "deterministic doctor checks"):
        assert guarantee in text


def test_canonical_pattern_separates_similarity_from_author_outcomes():
    text = _read("MEMENTO-PATTERN.md")
    section = text.split("## Retrieval checks", 1)[1].split("## Guardrails", 1)[0]

    assert "- `new`:" in section
    assert "- `related`:" in section
    assert "- `existing-missed`:" in section
    assert "- `applied`:" in section
    assert "- `overapplied`:" in section
    assert "existing-repaired" not in section
    assert "false-positive" in section
    assert "not another required retention outcome" in section


def test_canonical_pattern_preserves_archive_and_recommendation_semantics():
    text = _read("MEMENTO-PATTERN.md")

    assert "search hot and archived notes together" in text
    assert "60 percent archived coverage is a starting review recommendation" in text
    assert "never authorizes automatic removal" in text
    assert "Keep the count and byte measurements visible even when a local warning is disabled." in text
    assert "The operator chooses the age policy." in text
    assert "Plain-file adaptations should not archive sessions while another writer may be active" in text


def test_canonical_pattern_requires_explicit_approval_and_parking_on_silence():
    text = _read("MEMENTO-PATTERN.md")

    assert "explicitly approves the proposed wording" in text
    assert "If the user takes no action, park the candidate" in text
    assert "Silence is never approval." in text
    assert "retrievable evidence, not always-loaded instruction" in text


def test_public_docs_keep_candidate_proposal_and_parking_manual():
    for relative_path in ("README.md", "docs/concepts.md"):
        text = _read(relative_path)

        assert "agent manually proposes the strongest candidate" in text
        assert "The CLI neither proposes nor parks candidates." in text
        assert "session marker or tagged note" in text
        assert "Silence is never approval." in text


def test_public_docs_describe_integrated_cli_behavior_in_present_tense():
    changelog = _read("CHANGELOG.md")
    readme = _read("README.md")
    concepts = _read("docs/concepts.md")

    assert "Adds session inspection and caller-controlled, dry-run-first archival." in changelog
    assert "Adds doctor recommendations for separate hot and archived alias coverage" in changelog
    assert "planned" not in changelog.split("## 0.3.1", 1)[0]
    assert "ships when" not in changelog.split("## 0.3.1", 1)[0]
    for text in (readme, concepts):
        assert "session-archive" in text
        assert "session-list" in text
        assert "never remove" in text
