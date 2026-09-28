from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_readme_opening_leads_with_category_and_displays_the_hero():
    readme = _read("README.md")

    assert "Persistent memory for coding agents" in readme
    assert "designed to be harness- and model-agnostic" in readme
    assert "or any agent that follows instructions" not in readme
    assert "research, writing, and other knowledge work" in readme
    assert "The CLI never verifies a lesson's truth by itself" in readme
    assert "![Evidence board in the style of Memento" in readme
    assert "](docs/memento-memory-hero-v2.png)" in readme
    assert (ROOT / "docs/memento-memory-hero-v2.png").is_file()
    assert "**Notes**" in readme and "**Polaroids**" in readme and "**Tattoos**" in readme


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


def test_portable_interfaces_preserve_revision_and_approval_contract():
    concepts = _read("docs/concepts.md")
    protocol = _read("templates/PROTOCOL.md")
    template = _read("templates/AGENTS.md")
    pattern = _read("MEMENTO-PATTERN.md")
    for text in (concepts, protocol, pattern):
        assert "entry-read" in text and "note-amend" in text
        assert "owner" in text.lower() and "approval" in text.lower()
    assert "CLI has no in-place editor" not in template
    assert "content snapshots, not durable logical IDs" in concepts
    assert "An editorial change is not evidence that a lesson was applied or missed" in pattern


PUBLIC_DOCS = ("README.md", "MEMENTO-PATTERN.md", "CONTRIBUTING.md", "CHANGELOG.md")


def _public_doc_paths() -> list[Path]:
    paths = [ROOT / name for name in PUBLIC_DOCS]
    paths += sorted((ROOT / "templates").glob("*.md"))
    paths += sorted((ROOT / "docs").glob("*.md"))
    paths += sorted((ROOT / "examples").rglob("*.md"))
    return paths


def _stub_block(text: str) -> str:
    start = text.index("\n## Memory (memento)\n") + 1
    lines = text[start:].splitlines()
    block = [lines[0]]
    for line in lines[1:]:
        if not line.startswith("- "):
            break
        block.append(line)
    return "\n".join(block) + "\n"


def test_stub_is_small_and_has_five_rules_including_scoped_line():
    stub = _read("templates/memento-stub.md")

    assert len(stub.encode("utf-8")) < 1200
    assert stub.startswith("## Memory (memento)\n")
    bullets = [line for line in stub.splitlines() if line.startswith("- ")]
    assert len(bullets) == 5
    assert any("## Scoped" in line and "paths:" in line for line in bullets)
    assert any("memento/PROTOCOL.md" in line and "save work" in line for line in bullets)
    assert any("approves its exact wording" in line for line in bullets)


def test_every_quoted_stub_matches_the_canonical_stub():
    stub = _read("templates/memento-stub.md")

    assert _stub_block(_read("MEMENTO-PATTERN.md")) == stub
    assert _stub_block(_read("templates/AGENTS.md")) == stub


def test_worked_example_points_at_protocol_and_keeps_repo_rules():
    template = _read("templates/AGENTS.md")

    assert "memento/PROTOCOL.md" in template
    assert "## Repository" in template
    assert len(template.encode("utf-8")) < 3000


def test_protocol_covers_both_modes_triggers_formats_and_gates():
    protocol = _read("templates/PROTOCOL.md")

    for heading in (
        "## Modes",
        "## When the user corrects you",
        "## When you recognize a past situation",
        '## When the user says "save work"',
        "## Proposing a tattoo",
        "## Revising a note",
        "## Note format",
        "## Tattoo format",
    ):
        assert heading in protocol
    assert "Plain-file mode" in protocol and "CLI mode" in protocol
    assert "Why:" in protocol
    assert "<action with its trigger>; <reason clause>." in protocol
    assert "Silence is never approval." in protocol
    for decision in ("`new`", "`related`", "`existing-missed`", "`applied`", "`overapplied`"):
        assert decision in protocol
    assert "docs/concepts.md" in protocol


def test_protocol_links_to_tool_semantics_instead_of_restating_them():
    protocol = _read("templates/PROTOCOL.md")
    concepts = _read("docs/concepts.md")

    for restated in ("existing-missed / (new + existing-missed)", "memento-history:v1", "_project_receipts", "excludes them from observed-miss"):
        assert restated not in protocol
        assert restated in concepts


def test_reason_fields_are_documented_in_contract_standards_and_templates():
    shape = "<action with its trigger>; <reason clause>."
    for relative_path in ("MEMENTO-PATTERN.md", "docs/authoring-standards.md", "templates/PROTOCOL.md", "docs/concepts.md"):
        text = _read(relative_path)
        assert "Why:" in text, relative_path
        assert shape in text, relative_path
    assert "A rule without a reason cannot be reviewed for fit later" in _read("docs/authoring-standards.md")


def test_interpret_evidence_heading_has_one_public_copy_in_concepts():
    heading = "## Interpret evidence within its scope"
    counts = {path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8").count(heading) for path in _public_doc_paths()}

    assert sum(counts.values()) == 1
    assert counts["docs/concepts.md"] == 1
    assert "docs/concepts.md#interpret-evidence-within-its-scope" in _read("MEMENTO-PATTERN.md")


def test_flagship_example_replaces_the_verification_tattoo():
    old = "run the command that proves it"
    new = "Before changing a package's public API, search the other packages for callers; CI runs only the changed package's tests."
    hits = {path.relative_to(ROOT).as_posix() for path in _public_doc_paths() if old in path.read_text(encoding="utf-8")}

    assert hits == {"CHANGELOG.md", "examples/basic/memento/notes.md"}
    assert old in _read("examples/basic/memento/notes.md")
    assert old not in _read("examples/basic/memento/tattoos.md")
    for relative_path in ("README.md", "examples/basic/memento/tattoos.md", "examples/basic/README.md", "templates/PROTOCOL.md"):
        assert new in _read(relative_path), relative_path


def test_public_docs_make_no_universal_compatibility_claim():
    import re

    pattern = re.compile(r"any (agent|model|harness)", re.IGNORECASE)
    hits = [path.relative_to(ROOT).as_posix() for path in _public_doc_paths() if pattern.search(path.read_text(encoding="utf-8"))]

    assert hits == []


def test_readme_quickstart_produces_the_output_it_shows(tmp_path: Path):
    import os
    import re
    import stat
    import subprocess
    import sys

    readme = _read("README.md")
    quickstart = readme.split("## Quickstart", 1)[1].split("\n## ", 1)[0]
    bash_blocks = re.findall(r"```bash\n(.*?)```", quickstart, re.DOTALL)
    text_blocks = re.findall(r"```text\n(.*?)```", quickstart, re.DOTALL)
    assert len(bash_blocks) == 2 and len(text_blocks) == 2

    shim = tmp_path / ".venv/bin/memento-tattoo"
    shim.parent.mkdir(parents=True)
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m memento_tattoo "$@"\n', encoding="utf-8")
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(["bash", "-e", "-c", bash_blocks[1]], cwd=tmp_path, env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    doctor_part, load_part = result.stdout.split("MEMENTO_TATTOO_DOCTOR", 1)[1].split("MEMENTO_TATTOO_LOAD", 1)
    for line in text_blocks[0].strip("\n").splitlines():
        assert line in doctor_part.splitlines(), line
    first_match = load_part.split("\n- note_id:", 2)[1]
    for line in text_blocks[1].strip("\n").splitlines():
        assert line in first_match.splitlines(), line
    assert "situation: tattoo" in load_part.split("\n- note_id:", 3)[2]
