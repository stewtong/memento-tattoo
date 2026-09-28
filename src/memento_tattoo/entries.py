"""Complete source-scoped entries and editorial revisions in their Markdown blocks."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from .agent import parse_delta_marker, normalize_agent
from .config import paths_for, project_memory_path
from .lock import memory_lock

MARKER = re.compile(r'(?m)^<!--\s*delta:[^\n]*?-->[ \t]*')
PAIR = re.compile(r'(?mi)^[ \t]*-[ \t]*Situation:[ \t]*(.+?)[ \t]*$\n^[ \t]*-[ \t]*Note:[ \t]*(.+?)[ \t]*$')
HISTORY = '<!-- memento-history:v1\n'
FIELDS = 'Situation|Note|Why|How to apply|tags|aliases|Superseded-by|review_after'


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical_block(text: str) -> str:
    return text.rstrip() + '\n'


@dataclass(frozen=True)
class Entry:
    entry_id: str
    source: Path
    kind: str
    content: str
    start: int = 0
    end: int = 0
    scope: str = ''

    @property
    def sha256(self) -> str:
        return digest(self.content)

    def record(self) -> dict:
        return {'id': self.entry_id, 'source': str(self.source), 'kind': self.kind,
                'sha256': self.sha256, 'content': self.content, 'scope': self.scope,
                'identity': 'content snapshot' if self.entry_id.startswith(('project-snapshot:', 'project-file:', 'store-file:')) else 'stored id'}


def split_history(body: str) -> tuple[str, list[dict]]:
    if HISTORY not in body:
        if '<!-- memento-history:' in body:
            raise ValueError('unsupported or malformed note history')
        return body.strip(), []
    active, tail = body.split(HISTORY, 1)
    if HISTORY in tail or not tail.rstrip().endswith('-->'):
        raise ValueError('malformed note history')
    value = json.loads(tail.rstrip()[:-3])
    if not isinstance(value, dict) or set(value) != {'revisions'} or not isinstance(value['revisions'], list):
        raise ValueError('malformed note history')
    required = {'operation_id', 'expected_sha256', 'body_sha256', 'previous_active', 'reason', 'evidence', 'author', 'sess', 'timestamp'}
    for revision in value['revisions']:
        if (not isinstance(revision, dict) or set(revision) != required
                or not all(isinstance(v, str) for v in revision.values())
                or '<!-- memento-history:' in revision['previous_active']):
            raise ValueError('malformed note revision')
    return active.strip(), value['revisions']


def active_body(block: str) -> str:
    marker = MARKER.match(block)
    return split_history(block[marker.end():] if marker else block)[0]


def field(body: str, name: str) -> str:
    match = re.search(rf'^{re.escape(name)}:[ \t]*(.*?)(?=\n(?:{FIELDS}):|\Z)', body, re.I | re.M | re.S)
    return match.group(1).strip() if match else ''


def marked_entries(path: Path, kind: str) -> list[Entry]:
    if not path.is_file():
        return []
    text = path.read_bytes().decode('utf-8')
    matches = list(MARKER.finditer(text))
    entries = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        marker = parse_delta_marker(match.group())
        if marker is None:
            raise ValueError(f'{path.name}: malformed record marker at offset {match.start()}')
        entries.append(Entry(marker.note_id, path.resolve(), kind, canonical_block(text[match.start():end]), match.start(), end))
    return entries


def project_entries(path: Path) -> list[Entry]:
    if not path.is_file():
        return []
    text = path.read_bytes().decode('utf-8')
    entries = []
    markers = list(MARKER.finditer(text))
    headings = list(re.finditer(r'(?m)^## .+$', text))
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        end = min([end, *[h.start() for h in headings if h.start() > marker.start()]])
        previous = [h.group() for h in headings if h.start() < marker.start()]
        scope = previous[-1] if previous else ''
        parsed = parse_delta_marker(marker.group())
        if parsed is None:
            raise ValueError(f'{path.name}: malformed record marker at offset {marker.start()}')
        entries.append(Entry(parsed.note_id, path.resolve(), 'project',
                             canonical_block(text[marker.start():end]), marker.start(), end, scope))
    entries.append(Entry('project-file:' + digest(text), path.resolve(), 'project', text))
    return entries


def allowed_sources(root: Path, projects: list[Path] | None = None) -> list[tuple[Path, str]]:
    paths = paths_for(root)
    items = [(paths.notes, 'note'), (paths.notes_archive, 'note'), (paths.tattoos, 'tattoo'), (paths.project, 'project')]
    for directory in (paths.sessions, paths.sessions / 'archive'):
        if directory.exists() and not directory.resolve().is_relative_to(paths.root):
            raise ValueError('session source escapes memory root')
        items.extend((p, 'session') for p in sorted(directory.glob('sess_*.md')))
    for path, _ in items:
        if not path.resolve().is_relative_to(paths.root):
            raise ValueError('entry source escapes memory root')
    for project in projects or []:
        directory = project.expanduser().resolve()
        path = project_memory_path(directory)
        if not path.resolve().is_relative_to(directory):
            raise ValueError('project memory source escapes declared project')
        items.append((path, 'project'))
    # The same explicit project or root file may be supplied more than once.
    return list(dict.fromkeys((path.resolve(), kind) for path, kind in items))


def list_entries(root: Path, projects: list[Path] | None = None, *, source: Path | None = None, kinds: set[str] | None = None) -> list[Entry]:
    entries = []
    for path, kind in allowed_sources(root, projects):
        if (source is not None and path != source) or (kinds is not None and kind not in kinds):
            continue
        if not path.is_file():
            continue
        if kind == 'project':
            entries.extend(project_entries(path))
        elif kind == 'session':
            from .session_store import parse_session_file
            record = parse_session_file(path)
            entries.append(Entry(record.sess, path, kind, path.read_bytes().decode('utf-8')))
        else:
            entries.extend(marked_entries(path, kind))
    return entries


def resolve_entry(entry_id: str | None, *, root: Path, source: str | None = None, projects: list[Path] | None = None, kinds: set[str] | None = None) -> Entry:
    allowed = {path for path, _ in allowed_sources(root, projects)}
    selected = None
    if source is not None:
        candidate = Path(source).expanduser()
        selected = (candidate if candidate.is_absolute() else paths_for(root).root / candidate).resolve()
        if selected not in allowed:
            raise ValueError('source is not a declared memory store or project memory file')
    if entry_id is None:
        if selected is None or not selected.is_file():
            raise ValueError('supply an entry id or an existing declared source')
        content = selected.read_bytes().decode('utf-8')
        return Entry('store-file:' + digest(content), selected, 'file', content)
    if entry_id.startswith('store-file:') and selected is not None:
        content = selected.read_bytes().decode('utf-8')
        if entry_id != 'store-file:' + digest(content):
            raise ValueError('source snapshot changed; refresh the source read')
        return Entry(entry_id, selected, 'file', content)
    matches = [e for e in list_entries(root, projects, source=selected, kinds=kinds) if e.entry_id == entry_id and (selected is None or e.source == selected)]
    if not matches:
        raise ValueError('entry not found; refresh recall or check declared source')
    if len(matches) != 1:
        raise ValueError('ambiguous entry id; specify an exact source or reconcile duplicate records')
    return matches[0]


def validate_note(body: str) -> None:
    if not body.strip() or '<!--' in body or '-->' in body or '\r' in body or '\x00' in body:
        raise ValueError('note body contains an empty value or reserved structural marker')
    if re.search(r'(?m)^\s*---\s*$|^\[.*\]\s*$', body):
        raise ValueError('note body contains a reserved record header')
    labels = re.findall(rf'^({FIELDS}):', body, re.I | re.M)
    if len({label.lower() for label in labels}) != len(labels):
        raise ValueError('note body contains duplicate field headers')
    if not body.startswith('Situation:') or not field(body, 'Situation') or not field(body, 'Note'):
        raise ValueError('note body requires nonempty Situation and Note fields')


def _validate_successor(entry: Entry, body: str, notes: list[Entry]) -> None:
    current = field(body, 'Superseded-by')
    visited = {entry.entry_id}
    while current:
        if current in visited:
            raise ValueError('note supersession would create a cycle')
        visited.add(current)
        matches = [note for note in notes if note.entry_id == current]
        if len(matches) != 1:
            raise ValueError('superseding note must resolve to one existing ordinary note')
        current = field(active_body(matches[0].content), 'Superseded-by')


def amend_note(entry_id: str, text: str, *, root: Path, expected_sha256: str, sess: str,
               author: str, reason: str, evidence: str, source: str | None = None) -> tuple[bool, Entry]:
    validate_note(text)
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('expected_sha256 must be a full lowercase SHA-256')
    if not re.fullmatch(r'sess_[A-Za-z0-9_]+', sess):
        raise ValueError('amendment sess must match sess_[A-Za-z0-9_]+')
    for name, value in [('author', author), ('reason', reason), ('evidence', evidence)]:
        if not value.strip() or re.search(r'[\x00-\x1f\x7f]', value):
            raise ValueError(f'{name} must be nonempty and contain no control characters')
    # Preflight is read-only; repeat resolution under the root lock for writers.
    entry = resolve_entry(entry_id, root=root, source=source, kinds={'note'})
    if entry.kind != 'note':
        raise ValueError('note-amend edits ordinary notes only; durable rules require owner approval')
    new_body = text.strip()
    identity = {'id': entry_id, 'expected_sha256': expected_sha256, 'body': new_body,
                'sess': sess, 'author': normalize_agent(author), 'reason': reason, 'evidence': evidence}
    operation_id = digest(json.dumps(identity, sort_keys=True))
    # Reject stale/invalid drafts before even creating a missing lock file; repeat
    # every state-dependent check inside the lock before committing.
    old_body, revisions = split_history(active_with_history(entry.content))
    retry = bool(revisions and revisions[-1]['operation_id'] == operation_id)
    if retry:
        if old_body != new_body or digest(old_body) != revisions[-1]['body_sha256']:
            raise ValueError('amendment changed after its receipt; refresh the current entry')
    elif entry.sha256 != expected_sha256:
        raise ValueError('stale amendment: current block digest differs; read and reconcile the entry')
    else:
        _validate_successor(entry, new_body, list_entries(root, kinds={'note'}))
    with memory_lock(paths_for(root).root):
        entry = resolve_entry(entry_id, root=root, source=source, kinds={'note'})
        old_body, revisions = split_history(active_with_history(entry.content))
        if revisions and revisions[-1]['operation_id'] == operation_id:
            if old_body != new_body or digest(old_body) != revisions[-1]['body_sha256']:
                raise ValueError('amendment changed after its receipt; refresh the current entry')
            return False, entry
        if entry.sha256 != expected_sha256:
            raise ValueError('stale amendment: current block digest differs; read and reconcile the entry')
        notes = list_entries(root, kinds={'note'})
        _validate_successor(entry, new_body, notes)
        from ._time import now_iso
        revision = {'operation_id': operation_id, 'expected_sha256': expected_sha256,
                    'body_sha256': digest(new_body), 'previous_active': old_body,
                    'reason': reason, 'evidence': evidence, 'author': normalize_agent(author),
                    'sess': sess, 'timestamp': now_iso()}
        history = json.dumps({'revisions': [*revisions, revision]}, indent=2, ensure_ascii=True)
        history = history.replace('<', '\\u003c').replace('>', '\\u003e').replace('[[', '\\u005b\\u005b').replace(']]', '\\u005d\\u005d')
        marker = MARKER.match(entry.content).group()
        content = f'{marker}\n{new_body}\n\n{HISTORY}{history}\n-->\n'
        original = entry.source.read_bytes().decode('utf-8')
        updated = original[:entry.start] + content + ('\n' if entry.end < len(original) else '') + original[entry.end:]
        from .write_through import _atomic_write
        _atomic_write(entry.source, updated)
        result = resolve_entry(entry_id, root=root, source=str(entry.source), kinds={'note'})
        if result.content != content:
            raise RuntimeError('amended entry verification failed')
        return True, result


def active_with_history(block: str) -> str:
    marker = MARKER.match(block)
    if marker is None:
        raise ValueError('ordinary note lacks a creation marker')
    return block[marker.end():].strip()


def render_markdown(entry: Entry) -> str:
    lines = [f"# {entry.entry_id}", f"Source: {entry.source}", f"SHA-256: {entry.sha256}"]
    if entry.kind != 'note':
        return "\n\n".join([*lines, entry.content])
    active, revisions = split_history(active_with_history(entry.content))
    lines.extend(["## Active content", MARKER.match(entry.content).group() + "\n" + active])
    for index, revision in enumerate(revisions, start=1):
        lines.append(f"## Revision {index}")
        lines.extend(f"{key}: {value}" for key, value in revision.items() if key != 'previous_active')
        lines.extend(["### Previous active content", revision['previous_active']])
    return "\n\n".join(lines) + "\n"
