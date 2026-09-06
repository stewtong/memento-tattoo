"""Persistence regressions exercised through the save CLI."""
import json
from pathlib import Path
import pytest
from memento_tattoo.cli import main
from memento_tattoo import registry, write_through
from test_save_commit import _spec


def minimal(sess):
    spec = _spec(sess)
    for key in ('tattoo', 'project_edit', 'note', 'verify'):
        spec.pop(key, None)
    return spec


def run(root, spec):
    path = root.parent / (spec['sess'] + '.json')
    path.write_text(json.dumps(spec))
    return main(['--root', str(root), 'save-commit', '--spec', str(path)])


def test_old_replay_after_receipt_rotation_preserves_newer_state(tmp_path):
    root = tmp_path / 'memento'
    a, b = minimal('sess_old1'), minimal('sess_new1')
    assert run(root, a) == 0
    b['registry_delta']['line'] = '- Memento OSS - demo/ - latest'
    assert run(root, b) == 0
    registry.prune_applied(root / '_queue/applied', keep=0)
    before = (root / 'registry.md').read_bytes()
    assert run(root, a) == 1
    assert (root / 'registry.md').read_bytes() == before
    assert not list((root / '_queue').glob('*.registry.md'))


def test_archive_same_line_is_applied_by_action(tmp_path):
    root = tmp_path / 'memento'
    a, b = minimal('sess_old1'), minimal('sess_arch')
    assert run(root, a) == 0
    b['registry_delta']['action'] = 'archive'
    assert run(root, b) == 0
    assert 'status=archived' in (root / 'registry.md').read_text()
    assert run(root, b) == 0


def test_missing_legacy_receipt_fails_without_overwrite(tmp_path):
    root = tmp_path / 'memento'
    spec = minimal('sess_old1')
    assert run(root, spec) == 0
    # Simulate historical pruning, using only this synthetic receipt.
    for p in (root / '_queue/applied').glob('*.registry.md'):
        p.unlink()
    before = (root / 'registry.md').read_bytes()
    assert run(root, spec) == 1
    assert (root / 'registry.md').read_bytes() == before


@pytest.mark.parametrize('target', ['archive', 'hot'])
def test_failed_rotation_retry_preserves_note_and_replay_is_noop(tmp_path, monkeypatch, target):
    root = tmp_path / 'memento'
    a, b = minimal('sess_note'), minimal('sess_fill')
    for spec in (a, b):
        spec.pop('registry_delta')
        spec['note_kind'] = 'seed'
    a['note'] = 'Situation: comparing synthetic distributions\nNote: inspect tails.'
    b['note'] = 'Situation: large synthetic seed\nNote: ' + 'x' * 600
    monkeypatch.setattr(write_through, 'HOT_NOTES_ROTATE_BYTES', 500)
    monkeypatch.setattr(write_through, 'HOT_NOTES_TARGET_BYTES', 400)
    assert run(root, a) == 0
    real = write_through._atomic_write
    count = 0
    def fail(path, body):
        nonlocal count
        if path.name == 'notes.md':
            count += 1
        if (target == 'archive' and path.name == 'notes_archive.md') or (target == 'hot' and path.name == 'notes.md' and count == 2):
            raise OSError('injected rotation failure')
        return real(path, body)
    with monkeypatch.context() as m:
        m.setattr(write_through, '_atomic_write', fail)
        assert run(root, b) == 1
    assert 'sess_note.note.' in (root / 'notes.md').read_text()
    assert run(root, b) == 0
    assert run(root, a) == 0
    assert sum((root / p).read_text().count('sess_note.note.') for p in ('notes.md', 'notes_archive.md')) == 1


@pytest.mark.parametrize('field,value', [('sess', 'sess_bad/../../escape'), ('registry_delta', []), ('retention', {'decision':''}), ('retention', {'covered_note_id':['bad']})])
def test_invalid_nested_input_fails_before_writing(tmp_path, field, value):
    spec = minimal('sess_valid')
    spec['note'] = 'Situation: synthetic check\nNote: validate input.'
    spec[field] = value
    from memento_tattoo.save_commit import save_commit
    root = tmp_path / 'memento'
    assert not save_commit(spec, root=root).ok
    assert not root.exists()
