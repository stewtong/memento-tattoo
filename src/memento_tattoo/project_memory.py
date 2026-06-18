from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .agent import parse_delta_marker
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


def append_section(text: str, section: str, body: str, marker: str) -> str:
    normalized_section = section.strip()
    if not normalized_section.startswith("## "):
        raise ValueError("section must be a markdown h2 such as '## State'")

    match = re.search(rf"(?m)^{re.escape(normalized_section)}\s*$", text)
    new_body = f"{marker}\n{body.rstrip()}"
    if not match:
        replacement = f"{normalized_section}\n\n{new_body}\n"
        prefix = text.rstrip()
        return f"{prefix}\n\n{replacement}" if prefix else replacement

    next_match = SECTION_RE.search(text, match.end())
    start = match.start()
    end = next_match.start() if next_match else len(text)
    existing_section = text[match.end() : end].strip()
    section_body = f"{existing_section}\n\n{new_body}" if existing_section else new_body
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


def extract_section_body(text: str, section: str) -> str:
    normalized_section = section.strip()
    match = re.search(rf"(?m)^{re.escape(normalized_section)}\s*$", text)
    if not match:
        return ""
    next_match = SECTION_RE.search(text, match.end())
    end = next_match.start() if next_match else len(text)
    return text[match.end() : end].strip()


def delta_note_ids(text: str) -> set[str]:
    ids: set[str] = set()
    for line in text.splitlines():
        marker = parse_delta_marker(line)
        if marker is not None:
            ids.add(marker.note_id)
    return ids


def section_changed_since(section_text: str, flow_start: str | None) -> bool:
    if not flow_start:
        return False
    try:
        flow_dt = datetime.fromisoformat(flow_start.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("flow_start must be ISO timestamp") from exc
    for line in section_text.splitlines():
        marker = parse_delta_marker(line)
        if marker is None:
            continue
        if not marker.ts:
            return True
        try:
            marker_dt = datetime.fromisoformat(marker.ts.replace("Z", "+00:00"))
        except ValueError:
            return True
        if marker_dt >= flow_dt:
            return True
    return False
