"""Regressions for the publication gauntlet's persistence failures."""
import json

import pytest

from memento_tattoo import registry, retention, write_through
from memento_tattoo.save_commit import save_commit
from test_save_recovery import minimal, run


@pytest.mark.parametrize('target', ['retention_log_archive.jsonl', 'retention_log.jsonl', 'identity'])
def test_interrupted_retention_rotation_recovers_counts(tmp_path, monkeypatch, target):
    root = tmp_path / 'memory'
    root.mkdir()
    events = [dict(note_id=f'sess_old.note.{i:08}', decision='existing-missed',
                   decision_source='author', cover_note_id='original', pad='x' * 50000)
              for i in range(4)]
    (root / 'retention_log.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in events))
    real = retention._atomic_write

    hot_writes = 0

    def fail(path, lines):
        nonlocal hot_writes
        if path.name == 'retention_log.jsonl':
            hot_writes += 1
        if ((target == 'identity' and hot_writes == 1)
                or (path.name == target and (target != 'retention_log.jsonl' or hot_writes == 2))):
            raise OSError('injected rotation interruption')
        return real(path, lines)

    body = 'Situation: publishing a synthetic package\nNote: inspect the built artifact.'
    spec = minimal('sess_new')
    spec.pop('registry_delta')
    spec['note'] = body
    spec['retention'] = {'decision': 'new'}
    with monkeypatch.context() as patch:
        patch.setattr(retention, '_atomic_write', fail)
        assert run(root, spec) == 1
    assert len(retention.read_retention_events(root=root)) == 5
    assert retention.recurrence_counts(root=root, observed_only=True) == {'original': 4}
    assert run(root, spec) == 0
    assert len(retention.read_retention_events(root=root)) == 5
    assert retention.recurrence_counts(root=root, observed_only=True) == {'original': 4}
    stored = [json.loads(line) for name in ('retention_log_archive.jsonl', 'retention_log.jsonl')
              for line in (root / name).read_text().splitlines()]
    assert len(stored) == 5
    assert [{k: v for k, v in e.items() if k != "event_id"} for e in stored[:4]] == events
    assert (root / 'retention_log.jsonl').stat().st_size <= retention.RETENTION_LOG_ROTATE_BYTES


def test_ambiguous_legacy_boundary_events_are_preserved(tmp_path):
    line = json.dumps(dict(note_id='same', decision='existing-missed', decision_source='author'))
    for name in ('retention_log_archive.jsonl', 'retention_log.jsonl'):
        (tmp_path / name).write_text(line + '\n')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.warns(RuntimeWarning, match='preserved'):
        assert retention.recurrence_counts(root=tmp_path, observed_only=True) == {'same': 2}
    with pytest.warns(RuntimeWarning, match='preserved'):
        retention.rotate_retention_log(root=tmp_path)
    assert all((tmp_path / name).read_bytes() == body for name, body in before.items())


def test_distinct_identical_observations_survive_rotation(tmp_path):
    event = {'decision': 'existing-missed', 'note_id': 'same', 'decision_source': 'author'}
    retention.append_retention_event(event, root=tmp_path)
    retention.append_retention_event(event, root=tmp_path)
    retention.rotate_retention_log(root=tmp_path, rotate_bytes=1, keep=1)
    retention.append_retention_event(event, root=tmp_path)
    assert retention.recurrence_counts(root=tmp_path, observed_only=True) == {'same': 3}
    assert len({e['event_id'] for e in retention.read_retention_events(root=tmp_path)}) == 3
    assert 'event_id' not in event


@pytest.mark.parametrize('action', ['update', 'archive'])
@pytest.mark.parametrize('same_line', [False, True])
def test_losing_registry_operation_cannot_report_success(tmp_path, action, same_line):
    root = tmp_path / 'memory'
    spec = minimal('sess_loser')
    spec['registry_delta']['action'] = action
    line = spec['registry_delta']['line'] if same_line else '- Demo - newer-location/ - active'
    registry.registry_queue('sess_winner', action, spec['registry_delta']['slug'], line,
                            root, agent='codex', ts='2099-01-01T00:00:00Z')
    assert run(root, spec) == 1
    entry = registry._parse_registry(root / 'registry.md')[spec['registry_delta']['slug']]
    assert entry.sess == 'sess_winner'
    assert entry.line == (registry._archive_line(line) if action == 'archive' else line)
    assert list((root / '_queue/conflicts').glob('*.sess_loser.*'))
    before = (root / 'registry.md').read_bytes()
    assert run(root, spec) == 1
    assert (root / 'registry.md').read_bytes() == before


@pytest.mark.parametrize('malformed', [
    '<!-- registry-entry slug=precious status=active\n- Precious - precious/ - active\n',
    '<!-- registry-entry slug=demo status=active -->\n- Duplicate - other/ - active\n',
    '<!-- registry-entry slug=precious status=invalid -->\n- Precious - precious/ - active\n',
    '- Unmarked - precious/ - active\n',
])
def test_registry_parse_failure_preserves_all_files(tmp_path, malformed):
    registry.registry_queue('sess_first', 'add', 'demo', '- Demo - demo/ - active', tmp_path)
    assert registry.drain(tmp_path).ok
    registry.registry_queue('sess_next', 'add', 'other', '- Other - other/ - active', tmp_path)
    path = tmp_path / 'registry.md'
    path.write_text(path.read_text() + '\n' + malformed)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    result = registry.drain(tmp_path)
    assert not result.ok
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_registry_line_rejects_embedded_metadata_before_queue_write(tmp_path):
    with pytest.raises(ValueError, match='metadata'):
        registry.registry_queue('sess_bad', 'add', 'demo', '<!-- registry-entry slug=bad -->', tmp_path)
    assert not list(tmp_path.iterdir())


def test_archived_note_replay_verifies_actual_store(tmp_path, monkeypatch):
    root = tmp_path / 'memory'
    first, fill = minimal('sess_first'), minimal('sess_fill')
    for spec in (first, fill):
        spec.pop('registry_delta')
        spec['note_kind'] = 'seed'
    first['note'] = 'Situation: synthetic inspection\nNote: unique-archived-proof'
    first['verify'] = ['unique-archived-proof']
    fill['note'] = 'Situation: filling storage\nNote: ' + 'x' * 600
    monkeypatch.setattr(write_through, 'HOT_NOTES_ROTATE_BYTES', 500)
    monkeypatch.setattr(write_through, 'HOT_NOTES_TARGET_BYTES', 400)
    assert run(root, first) == 0
    assert run(root, fill) == 0
    assert 'unique-archived-proof' not in (root / 'notes.md').read_text()
    assert run(root, first) == 0
    result = save_commit(first, root=root)
    assert result.ok
    assert root / 'notes_archive.md' in result.touched


@pytest.mark.parametrize('judgment', [{'decision': 'applied'}, {'covered_note_id': 'old'}])
def test_pattern_judgment_rejected_before_any_memory_write(tmp_path, judgment):
    spec = minimal('sess_pattern')
    spec['note'] = 'Situation: repeated observations\nNote: preserve attribution.'
    spec['note_kind'] = 'pattern'
    spec['retention'] = judgment
    root = tmp_path / 'memory'
    assert run(root, spec) == 1
    assert not root.exists()
    from memento_tattoo.cli import main
    args = ['--root', str(root), 'note-add', '--sess', spec['sess'], '--kind', 'pattern', spec['note']]
    for key, value in judgment.items():
        args.extend(['--' + key.replace('_', '-'), value])
    assert main(args) == 2
    assert not root.exists()
    with pytest.raises(ValueError, match='correction or reflection'):
        write_through.note_add(spec['note'], sess=spec['sess'], root=root, kind='pattern', **judgment)
    assert not root.exists()


def test_retention_reader_retries_rotation_without_writing(tmp_path, monkeypatch):
    for i in range(3):
        retention.append_retention_event({'note_id': str(i), 'decision': 'new'}, root=tmp_path)
    real = retention._lines
    rotated = False

    def during_read(path):
        nonlocal rotated
        if path.name == 'retention_log_archive.jsonl' and not rotated:
            rotated = True
            retention.rotate_retention_log(root=tmp_path, rotate_bytes=1)
        return real(path)

    monkeypatch.setattr(retention, '_lines', during_read)
    assert [e['note_id'] for e in retention.read_retention_events(root=tmp_path)] == ['0', '1', '2']
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    retention.read_retention_events(root=tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}


def test_retention_read_creates_no_lock_for_plain_files(tmp_path):
    (tmp_path / 'retention_log.jsonl').write_text('{"decision":"new"}\n')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert retention.read_retention_events(root=tmp_path) == [{'decision': 'new'}]
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_registry_minimal_legacy_entry_round_trips(tmp_path):
    registry.registry_queue('sess_new', 'add', 'other', '- Other - other/ - active', tmp_path)
    path = tmp_path / 'registry.md'
    path.write_text('# Registry\n\n<!-- registry-entry slug=legacy -->\n- Legacy - legacy/ - active\n')
    before = registry._parse_registry(path)['legacy']
    assert registry.drain(tmp_path).ok
    assert registry._parse_registry(path)['legacy'] == before
    registry.registry_queue('sess_next', 'update', 'other', '- Other - other/ - maintained', tmp_path)
    assert registry.drain(tmp_path).ok
    assert registry._parse_registry(path)['legacy'] == before


def test_save_recovers_interruption_before_receipt_move(tmp_path, monkeypatch):
    root = tmp_path / 'memory'
    spec = minimal('sess_receipt')
    spec['registry_delta']['action'] = 'archive'
    spec['registry_delta']['expected_line'] = ''
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise OSError('injected receipt move failure')
        patch.setattr(registry, '_move_delta', fail)
        assert run(root, spec) == 1
    assert registry._parse_registry(root / 'registry.md')['memento-oss'].sess == 'sess_receipt'
    assert list((root / '_queue').glob('*.registry.md'))
    assert run(root, spec) == 0
    assert not list((root / '_queue').glob('*.registry.md'))
    assert len(list((root / '_queue/applied').glob('*.registry.md'))) == 1
