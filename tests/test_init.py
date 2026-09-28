import json
import os
import re
from pathlib import Path

import pytest

from memento_tattoo.cli import main
from memento_tattoo.doctor import run_doctor
from memento_tattoo.init import (
    CLAUDE_IMPORT_LINE,
    SKILL_NAME,
    protocol_text,
    run_init,
    skill_markdown,
    stub_text,
)

REPO = Path(__file__).resolve().parents[1]
CORE_ROOT_FILES = ("notes.md", "tattoos.md", "retention_log.jsonl", "PROTOCOL.md")


def _files(base: Path) -> dict[str, bytes]:
    return {path.relative_to(base).as_posix(): path.read_bytes() for path in base.rglob("*") if path.is_file()}


def test_packaged_templates_are_the_readable_templates():
    assert protocol_text() == (REPO / "templates/PROTOCOL.md").read_text(encoding="utf-8")
    assert stub_text() == (REPO / "templates/memento-stub.md").read_text(encoding="utf-8")


def test_init_creates_root_files_project_memory_and_prints_stub(tmp_path: Path, capsys):
    assert main(["init", "--root", str(tmp_path / "memento")]) == 0
    out = capsys.readouterr().out

    for name in CORE_ROOT_FILES:
        assert (tmp_path / "memento" / name).is_file()
    assert (tmp_path / "memento/PROTOCOL.md").read_text(encoding="utf-8") == protocol_text()
    memory = (tmp_path / "memory.md").read_text(encoding="utf-8")
    assert "## Key Decisions" in memory and "## Current state" in memory
    assert out.startswith("MEMENTO_TATTOO_INIT\n")
    assert out.count("created ") == 5
    assert stub_text().rstrip("\n") in out

    ok, doctor_output = run_doctor(tmp_path / "memento", projects=[tmp_path])
    assert ok is True, doctor_output


def test_global_root_flag_also_selects_the_init_root(tmp_path: Path):
    assert main(["--root", str(tmp_path / "mem"), "init"]) == 0

    assert (tmp_path / "mem/PROTOCOL.md").is_file()
    assert (tmp_path / "memory.md").is_file()


def test_init_is_idempotent_and_never_overwrites(tmp_path: Path, capsys):
    root = tmp_path / "memento"
    root.mkdir()
    (root / "notes.md").write_text("existing notes\n", encoding="utf-8")
    (tmp_path / "memory.md").write_text("my project\n", encoding="utf-8")

    assert main(["init", "--root", str(root)]) == 0
    first = capsys.readouterr().out
    assert f"skipped (exists) {root / 'notes.md'}" in first
    assert f"skipped (exists) {tmp_path / 'memory.md'}" in first
    assert (root / "notes.md").read_text(encoding="utf-8") == "existing notes\n"
    assert (tmp_path / "memory.md").read_text(encoding="utf-8") == "my project\n"

    before = _files(tmp_path)
    assert main(["init", "--root", str(root)]) == 0
    second = capsys.readouterr().out
    assert "created " not in second
    assert _files(tmp_path) == before


def test_init_keeps_an_edited_protocol(tmp_path: Path):
    root = tmp_path / "memento"
    run_init(root)
    (root / "PROTOCOL.md").write_text("locally adapted\n", encoding="utf-8")

    result = run_init(root)

    assert root / "PROTOCOL.md" in result.skipped
    assert (root / "PROTOCOL.md").read_text(encoding="utf-8") == "locally adapted\n"


def test_init_points_instructions_at_a_nondefault_root(tmp_path: Path):
    result = run_init(tmp_path / "tools" / "mem", project=tmp_path)
    output = "\n".join(result.lines)

    assert "read tools/mem/PROTOCOL.md" in output
    assert "memento/" not in output.split("Paste this", 1)[1]


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(": ")
        # A double-quoted YAML scalar written with JSON escapes decodes as JSON.
        fields[key] = json.loads(value) if value.startswith('"') else value
    return fields


def test_skill_adapter_writes_spec_conformant_skill_in_default_location(tmp_path: Path):
    assert main(["init", "--root", str(tmp_path / "memento"), "--adapter", "skill"]) == 0

    skill = tmp_path / ".agents/skills/memento-tattoo/SKILL.md"
    text = skill.read_text(encoding="utf-8")
    fields = _frontmatter(text)
    assert set(fields) == {"name", "description"}
    assert fields["name"] == skill.parent.name == SKILL_NAME
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", fields["name"]) and len(fields["name"]) <= 64
    assert 0 < len(fields["description"]) < 1024
    assert "corrects you" in fields["description"]
    assert "past lesson" in fields["description"]
    assert '"save work"' in fields["description"]
    body = text.split("\n---\n", 1)[1]
    assert "`memento/PROTOCOL.md` from the repository root" in body


def test_skill_description_survives_yaml_special_characters(tmp_path: Path):
    root = tmp_path / "mem: archive #1"
    assert main(["init", "--root", str(root), "--adapter", "skill", "--dir", str(tmp_path / "skills")]) == 0
    line = next(l for l in (tmp_path / "skills/memento-tattoo/SKILL.md").read_text().splitlines()
                if l.startswith("description: "))
    value = line[len("description: "):]
    assert value.startswith('"') and value.endswith('"')
    decoded = json.loads(value)
    assert '"save work"' in decoded and "PROTOCOL.md" in decoded


def test_nested_root_is_addressed_from_the_repository_root(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--root", "tools/mem", "--adapter", "skill"]) == 0
    text = (tmp_path / ".agents/skills/memento-tattoo/SKILL.md").read_text(encoding="utf-8")
    assert "`tools/mem/PROTOCOL.md` from the repository root" in text
    assert (tmp_path / "memory.md").is_file()


def test_skill_adapter_honors_dir(tmp_path: Path):
    target = tmp_path / "client-skills"
    assert main(["init", "--root", str(tmp_path / "memento"), "--adapter", "skill", "--dir", str(target)]) == 0

    assert (target / SKILL_NAME / "SKILL.md").is_file()
    assert not (tmp_path / ".agents").exists()


def test_claude_md_import_prints_line_without_writing(tmp_path: Path, capsys):
    assert main(["init", "--root", str(tmp_path / "memento"), "--adapter", "claude-md-import"]) == 0

    assert CLAUDE_IMPORT_LINE in capsys.readouterr().out.splitlines()
    assert not (tmp_path / "CLAUDE.md").exists()


def test_claude_md_import_write_creates_but_never_edits(tmp_path: Path, capsys):
    root = str(tmp_path / "memento")
    assert main(["init", "--root", root, "--adapter", "claude-md-import", "--write"]) == 0
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == CLAUDE_IMPORT_LINE + "\n"
    capsys.readouterr()

    (tmp_path / "CLAUDE.md").write_text("# House rules\n", encoding="utf-8")
    assert main(["init", "--root", root, "--adapter", "claude-md-import", "--write"]) == 0
    out = capsys.readouterr().out
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "# House rules\n"
    assert "CLAUDE.md exists; add this line to it:" in out


def test_generic_adapter_is_the_stub_only(tmp_path: Path, capsys):
    assert main(["init", "--root", str(tmp_path / "memento"), "--adapter", "generic"]) == 0
    out = capsys.readouterr().out

    assert stub_text().rstrip("\n") in out
    assert not (tmp_path / ".agents").exists()
    assert not (tmp_path / "CLAUDE.md").exists()


@pytest.mark.parametrize("argv", [["--dir", "x"], ["--write"]])
def test_adapter_options_require_their_adapter(tmp_path: Path, argv: list[str], capsys):
    assert main(["init", "--root", str(tmp_path / "memento"), *argv]) == 2
    assert "applies only to" in capsys.readouterr().out
    assert not (tmp_path / "memento").exists()


def _protocol_fragments() -> list[str]:
    fragments = []
    for line in protocol_text().splitlines():
        stripped = line.strip().lstrip("-0123456789. ").strip()
        if stripped.startswith(("<!--", "```")) or len(stripped) < 30:
            continue
        fragments.append(stripped)
        fragments.extend(part.strip() for part in re.split(r"(?<=[.:;])\s+", stripped) if len(part.strip()) >= 30)
    return fragments


def test_no_adapter_output_contains_protocol_body_text(tmp_path: Path):
    outputs = [skill_markdown(tmp_path / "memento", tmp_path), CLAUDE_IMPORT_LINE, stub_text()]
    fragments = _protocol_fragments()

    assert len(fragments) > 50
    for output in outputs:
        leaked = [fragment for fragment in fragments if fragment in output]
        assert leaked == []


def test_project_edit_after_init_updates_the_section_recall_reads(tmp_path: Path):
    from memento_tattoo.recall import _current_state

    root = tmp_path / "memento"
    assert main(["init", "--root", str(root)]) == 0
    assert main(["--root", str(root), "project-edit", "--project", str(tmp_path), "--sess", "sess_test",
                 "--replace", "Release branch is frozen until Friday."]) == 0
    text = (tmp_path / "memory.md").read_text(encoding="utf-8")
    assert text.count("## Current state") == 1 and "## State" not in text
    assert "Release branch is frozen" in _current_state(tmp_path / "memory.md")
