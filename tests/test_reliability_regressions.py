"""Shared writer and public CLI regression probes for the reliability repair."""
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import pytest
from memento_tattoo.recall import _extract_field, load_memento_notes
from memento_tattoo.save_commit import save_commit
from memento_tattoo.session_store import load_sessions, render_session_block, write_session_block
from memento_tattoo import write_through


def spec(sess='sess_a', body='OLD', mode='replace', registry=False):
    value = {'sess': sess, 'agent': 'codex', 'session': {
        'date': '2026-01-01', 'topics': ['probe'], 'significance': 'low',
        'accomplished': 'Checked.\nException: keep rollback available.',
        'started': '', 'pending': '', 'insights': '', 'files': []},
        'project_edit': {'project': 'project', 'mode': mode, 'body': body}}
    if registry:
        value['registry_delta'] = {'action': 'update', 'slug': 'probe', 'line': f'- Probe - project/ - {body}'}
    return value


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def cli(root, *args):
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'src')}
    return subprocess.run([sys.executable, '-m', 'memento_tattoo', '--root', str(root),
                           '--agent', 'codex', *args], env=env, text=True, capture_output=True)


def save_cli(root, value, tmp_path):
    source = tmp_path / f'{value["sess"]}.json'
    source.write_text(json.dumps(value))
    return cli(root, 'save-commit', '--spec', str(source))


@pytest.mark.parametrize('mode', ['replace', 'append', 'auto'])
@pytest.mark.parametrize('registry', [False, True])
def test_cli_replay_preserves_every_file(tmp_path, mode, registry):
    root = tmp_path / 'root'
    a = spec(mode=mode, registry=registry)
    assert save_cli(root, a, tmp_path).returncode == 0
    before = snapshot(root)
    assert save_cli(root, a, tmp_path).returncode == 0
    assert snapshot(root) == before
    assert save_cli(root, spec('sess_b', 'NEW', registry=registry), tmp_path).returncode == 0
    before = snapshot(root)
    rejected = save_cli(root, a, tmp_path)
    assert rejected.returncode != 0 and 'superseded' in rejected.stdout
    assert snapshot(root) == before


@pytest.mark.parametrize('stage', ['reserve', 'project', 'acknowledge'])
def test_interrupted_order_recovers_at_cli(tmp_path, monkeypatch, stage):
    root = tmp_path / 'root'
    atomic = write_through._atomic_write
    def fail(path, text):
        receipt = path.parent.name == '_project_receipts'
        if ((stage == 'reserve' and receipt and '"pending"' in text)
            or (stage == 'project' and path.name == 'memory.md')
            or (stage == 'acknowledge' and receipt and '"applied"' in text)):
            raise OSError('injected interruption at ' + stage)
        atomic(path, text)
    monkeypatch.setattr(write_through, '_atomic_write', fail)
    result = save_commit(spec(), root=root)
    assert not result.ok and 'injected interruption' in result.error
    if stage == 'reserve':
        assert not (root / 'sessions').exists()
    elif stage == 'project':
        assert not (root / 'project/memory.md').exists()
    else:
        assert 'OLD' in (root / 'project/memory.md').read_text()
    monkeypatch.setattr(write_through, '_atomic_write', atomic)
    assert save_cli(root, spec(), tmp_path).returncode == 0
    receipt = json.loads(next((root / '_project_receipts').glob('*.json')).read_text())
    assert receipt['status'] == 'applied'
    before = snapshot(root)
    assert save_cli(root, spec(), tmp_path).returncode == 0
    assert snapshot(root) == before


def test_pending_receipt_cannot_overwrite_intervening_edit(tmp_path):
    root = tmp_path / 'root'
    write_through.project_edit('OLD', sess='sess_a', root=root, project=root/'project', mode='replace', prepare_only=True)
    assert cli(root, 'project-edit', '--project', str(root/'project'), '--sess', 'sess_b', '--replace', 'NEW').returncode == 0
    before = snapshot(root)
    assert save_cli(root, spec(), tmp_path).returncode != 0
    assert snapshot(root) == before


def test_archived_session_replay_and_missing_receipt(tmp_path):
    root = tmp_path / 'root'
    assert save_cli(root, spec(), tmp_path).returncode == 0
    assert cli(root, 'session-archive', '--days', '1', '--apply').returncode == 0
    before = snapshot(root)
    assert save_cli(root, spec(), tmp_path).returncode == 0
    assert snapshot(root) == before
    assert save_cli(root, spec('sess_b', 'NEW'), tmp_path).returncode == 0
    receipt = next(p for p in (root/'_project_receipts').glob('*.json') if json.loads(p.read_text())['identity']['sess'] == 'sess_a')
    receipt.unlink()  # Synthetic legacy save predating receipts, marker replaced.
    before = snapshot(root)
    result = save_cli(root, spec(), tmp_path)
    assert result.returncode != 0 and 'no project receipt' in result.stdout
    assert snapshot(root) == before


def test_legacy_marker_can_bootstrap_receipt_without_rewriting_project(tmp_path):
    root=tmp_path/'root'
    assert save_cli(root, spec(), tmp_path).returncode == 0
    receipt=next((root/'_project_receipts').glob('*.json'))
    receipt.unlink()
    before=(root/'project/memory.md').read_bytes()
    assert save_cli(root,spec(),tmp_path).returncode == 0
    assert (root/'project/memory.md').read_bytes() == before and receipt.exists()


def test_direct_project_edit_rejects_obsolete_replay(tmp_path):
    args=('project-edit','--project',str(tmp_path/'project'),'--replace')
    assert cli(tmp_path,*args,'--sess','sess_a','OLD').returncode == 0
    assert cli(tmp_path,*args,'--sess','sess_b','NEW').returncode == 0
    before=snapshot(tmp_path)
    assert cli(tmp_path,*args,'--sess','sess_a','OLD').returncode != 0
    assert snapshot(tmp_path)==before


def test_concurrent_project_append_writers_and_replay(tmp_path):
    def run(index):
        return cli(tmp_path,'project-edit','--project',str(tmp_path/'project'),'--sess',f'sess_{index}','--append',f'BODY{index}')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(run,range(8)))
    assert all(p.returncode==0 for p in results),[(p.stdout,p.stderr) for p in results]
    text=(tmp_path/'project/memory.md').read_text()
    assert all(text.count(f'BODY{i}')==1 for i in range(8))
    before=snapshot(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(run,range(8)))
    assert all(p.returncode==0 for p in results)
    assert snapshot(tmp_path)==before


@pytest.mark.parametrize('extra', [
    ['--sess','../../escape'],['--sess','ABSOLUTE_ESCAPE'],['--sess','sess_foo\\bar'],
    ['--sess','sess_bad','--topics','foo | other'],['--sess','sess_bad','--topics','foo [other]'],
    ['--sess','sess_bad','--topics','foo\n[other]'],
    ['--sess','sess_bad','--accomplished','Done.\nPending: injected'],
])
def test_invalid_cli_session_does_not_create_or_poison_store(tmp_path,extra):
    root=tmp_path/'root'
    extra=[str(tmp_path/'absolute_escape') if item=='ABSOLUTE_ESCAPE' else item for item in extra]
    result=cli(root,'session-add','--date','2026-09-07','--accomplished','done',*extra)
    assert result.returncode != 0 and not root.exists()
    assert cli(root,'session-add','--date','2026-09-07','--accomplished','done','--sess','sess_valid').returncode==0
    assert cli(root,'session-list').returncode==0
    assert cli(root,'rebuild').returncode==0


def test_shared_writer_validates_before_root(tmp_path):
    block=render_session_block('sess_good',agent='codex',**spec()['session'])
    for sess,bad in [('sess_other',block),('../../escape',block),('sess_good',block.replace('probe | low','probe | injected | low')),
                     ('sess_good',block.replace('Pending:','Pending: extra\nPending:'))]:
        with pytest.raises(ValueError):
            write_session_block(tmp_path/'absent',bad,sess)
        assert not (tmp_path/'absent').exists()


@pytest.mark.parametrize('surface',['directory','file'])
def test_session_symlink_escape_rejected_by_shared_writer_and_driver(tmp_path,surface):
    root=tmp_path/'root';root.mkdir()
    outside=tmp_path/'outside';outside.mkdir()
    if surface=='directory':
        (root/'sessions').symlink_to(outside,target_is_directory=True)
    else:
        (root/'sessions').mkdir()
        (root/'sessions/sess_a.md').symlink_to(outside/'target.md')
    before=snapshot(tmp_path)
    block=render_session_block('sess_a',agent='codex',**spec()['session'])
    with pytest.raises(ValueError,match='escapes'):
        write_session_block(root,block,'sess_a')
    result=save_commit(spec(),root=root)
    assert not result.ok and 'escapes' in result.error
    assert cli(root,'session-add','--sess','sess_a','--date','2026-01-01','--accomplished','done').returncode!=0
    assert snapshot(tmp_path)==before


@pytest.mark.parametrize('destination',['notes.md','notes_archive.md'])
def test_cli_continuation_only_note_retrieval(tmp_path,destination):
    body='Situation: restarting service\nNote: Check health.\nNever proceed when rollback is unavailable.\nWhy: preserve recovery.\n'
    assert cli(tmp_path,'note-add','--sess','sess_note','--kind','seed',body).returncode==0
    if destination != 'notes.md':
        (tmp_path/'notes.md').rename(tmp_path/destination)
    result=cli(tmp_path,'load','--query','rollback unavailable','--limit','1')
    assert result.returncode==0 and 'Never proceed when rollback is unavailable.' in result.stdout
    assert f'source: {destination}' in result.stdout and len(result.stdout)<2000
    assert load_memento_notes(tmp_path)[0].note=='Check health.\nNever proceed when rollback is unavailable.'


def test_note_fields_empty_mixed_case_and_final_continuations():
    body='Note:\nnOtEignored: keep this\nWhy: reason\nhOw To ApPlY:\nCheck status.\nUnless migration is active.\ntags: service\nrollback\n'
    assert _extract_field(body,'Note')=='nOtEignored: keep this'
    assert _extract_field('Note:\nWhy: reason\n','Note')==''
    assert _extract_field(body,'How to apply')=='Check status.\nUnless migration is active.'
    assert _extract_field(body,'tags')=='service\nrollback'


def test_session_narrative_round_trip_archive_rebuild_and_legacy_read(tmp_path):
    value=spec()['session']
    value.update(accomplished='Checked.\nException: preserve rollback.',started='',pending='First.\nSecond.',
                 insights='Learned.\nApplied.',files=['one.md','two.md'])
    block=render_session_block('sess_current',agent='codex',**value)
    write_session_block(tmp_path,block,'sess_current')
    record=load_sessions(tmp_path)[0]
    for key in ['accomplished','started','pending','insights','files']:
        assert getattr(record,key)==value[key]
    assert cli(tmp_path,'session-archive','--days','1','--apply').returncode==0
    assert cli(tmp_path,'rebuild').returncode==0
    assert load_sessions(tmp_path)[0].pending=='First.\nSecond.'
    legacy=tmp_path/'sessions/sess_legacy.md'
    legacy.write_text('---\n[sess_legacy | 2025-01-01 | history]\nAccomplished: old\ncontinued\nFiles: legacy.md\n---\n')
    records=load_sessions(tmp_path)
    assert records[0].agent=='grandfathered' and records[0].accomplished=='old\ncontinued'
    assert cli(tmp_path,'session-list').returncode==0


def test_session_add_without_agent_keeps_unknown_default(tmp_path):
    result=subprocess.run([sys.executable,'-m','memento_tattoo','--root',str(tmp_path),
                           'session-add','--sess','sess_default','--date','2026-09-07',
                           '--accomplished','done'],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert load_sessions(tmp_path)[0].agent=='unknown'


def test_pending_receipt_detects_line_ending_changes(tmp_path):
    project=tmp_path/'project';project.mkdir()
    path=project/'memory.md';path.write_bytes(b'# Project\r\n\r\n## State\r\nBefore\r\n')
    write_through.project_edit('After',sess='sess_change',root=tmp_path,project=project,mode='replace',prepare_only=True)
    path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n'))
    before=snapshot(tmp_path)
    with pytest.raises(ValueError,match='superseded or edited'):
        write_through.project_edit('After',sess='sess_change',root=tmp_path,project=project,mode='replace')
    assert snapshot(tmp_path)==before
