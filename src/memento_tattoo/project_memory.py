from __future__ import annotations

import re
from pathlib import Path

from .config import project_memory_path


SECTION_RE = re.compile(r"(?m)^## .+$")


def ensure_project_memory(project: Path) -> Path:
    path = project_memory_path(project)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Project Memory\n\n## Key Decisions\n\n## State\n", encoding="utf-8")
    return path


def replace_section(text: str, section: str, body: str, marker: str, *, preserve_existing: bool = False) -> str:
    normalized_section = section.strip()
    if not normalized_section.startswith("## "):
        raise ValueError("section must be a markdown h2 such as '## State'")

    match = re.search(rf"(?m)^{re.escape(normalized_section)}\s*$", text)
    if not match:
        replacement = f"{normalized_section}\n\n{marker}\n{body.rstrip()}\n"
        prefix = text.rstrip()
        return f"{prefix}\n\n{replacement}" if prefix else replacement

    next_match = SECTION_RE.search(text, match.end())
    start = match.start()
    end = next_match.start() if next_match else len(text)
    existing_section = text[match.end() : end].strip()
    new_body = f"{marker}\n{body.rstrip()}"
    if preserve_existing and existing_section:
        section_body = (
            "<!-- concurrent-edit reconcile -->\n"
            "### Existing section\n\n"
            f"{existing_section}\n\n"
            "### Incoming section\n\n"
            f"{new_body}"
        )
    else:
        section_body = new_body

    replacement = f"{normalized_section}\n\n{section_body}\n"
    prefix = text[:start].rstrip()
    suffix = text[end:].lstrip("\n")

    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(replacement.rstrip())
    if suffix:
        parts.append(suffix.rstrip())
    return "\n\n".join(parts).rstrip() + "\n"
