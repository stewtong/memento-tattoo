"""Failure-boundary regressions for public export and checked saves."""
import pytest
from scripts.export_public import export_public, PUBLIC_ENTRIES
from memento_tattoo import retention, write_through
from memento_tattoo.save_commit import save_commit
from test_save_recovery import minimal, run


def test_export_preserves_existing_destination(tmp_path):
    target = tmp_path / 'existing'
    target.mkdir()
    sentinel = target / 'keep.txt'
    sentinel.write_text('preserve')
    with pytest.raises(FileExistsError):
        export_public(target)
    assert sentinel.read_text() == 'preserve'


def test_export_rejects_nested_destination(tmp_path):
    with pytest.raises(ValueError, match='separate'):
        export_public(tmp_path / 'export', source_root=tmp_path)
    assert not list(tmp_path.iterdir())


def test_export_rejects_symlink_without_reading_target(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    outside = tmp_path / 'private.txt'
    outside.write_text('synthetic private content')
    for name in PUBLIC_ENTRIES:
        (source / name).write_text('public')
    (source / 'docs').unlink()
    (source / 'docs').mkdir()
    (source / 'docs' / 'linked.md').symlink_to(outside)
    with pytest.raises(ValueError, match='symlink'):
        export_public(tmp_path / 'public', source_root=source)
    assert not (tmp_path / 'public').exists()


@pytest.mark.parametrize('same_registry_line', [False, True])
def test_superseded_save_does_not_restore_project_snapshot(tmp_path, same_registry_line):
    root = tmp_path / 'memory'
    first, latest = minimal('sess_first'), minimal('sess_latest')
    for spec, state in ((first, 'old snapshot'), (latest, 'accepted snapshot')):
        spec['project_edit'] = {'project': 'demo', 'body': state, 'mode': 'replace'}
    if not same_registry_line:
        latest['registry_delta']['line'] = '- Memento OSS - demo/ - latest'
    assert run(root, first) == 0
    assert run(root, latest) == 0
    before = (root / 'demo/memory.md').read_bytes()
    assert run(root, first) == 1
    assert (root / 'demo/memory.md').read_bytes() == before


@pytest.mark.parametrize('field', ['significance', 'note_kind', 'mode'])
def test_unhashable_options_return_failed_save_without_writes(tmp_path, field):
    spec = minimal('sess_invalid')
    if field == 'significance':
        spec['session'][field] = []
    elif field == 'mode':
        spec['project_edit'] = {'project': 'demo', 'body': 'state', 'mode': []}
    else:
        spec[field] = []
    result = save_commit(spec, root=tmp_path / 'memory')
    assert not result.ok
    assert not (tmp_path / 'memory').exists()


def test_note_retry_recovers_missing_event_without_self_cover(tmp_path, monkeypatch):
    body = 'Situation: publishing a sanitized public package\nNote: inspect export contents.'
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise OSError('injected retention failure')
        patch.setattr(retention, 'append_retention_event', fail)
        with pytest.raises(OSError):
            write_through.note_add(body, sess='sess_note', root=tmp_path)
    write_through.note_add(body, sess='sess_note', root=tmp_path)
    write_through.note_add(body, sess='sess_note', root=tmp_path)
    events = retention.read_retention_events(root=tmp_path)
    assert len(events) == 1
    assert events[0]['decision'] == 'new'
    assert not events[0]['cover_note_id']
    assert (tmp_path / 'notes.md').read_text().count('<!-- delta:') == 1


def test_drain_reads_sessions_after_acquiring_lock(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from memento_tattoo import registry
    from memento_tattoo.session_store import render_session_block
    from memento_tattoo.rebuild import rebuild
    registry.registry_queue('sess_update', 'add', 'demo', '- Demo - demo/ - active', tmp_path)
    real_lock = registry.memory_lock

    @contextmanager
    def concurrent_session(root, **kwargs):
        with real_lock(root, **kwargs):
            sessions = tmp_path / 'sessions'
            sessions.mkdir()
            (sessions / 'sess_other.md').write_text(render_session_block(
                'sess_other', date='2026-09-05', agent='test', topics=['concurrent'],
                significance='low', accomplished='saved before drain lock',
                started='none', pending='none', insights='none', files=[]))
            yield

    monkeypatch.setattr(registry, 'memory_lock', concurrent_session)
    assert registry.drain(tmp_path).ok
    assert rebuild(tmp_path, check=True)[0]
