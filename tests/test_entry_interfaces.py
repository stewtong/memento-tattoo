import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from memento_tattoo.entries import active_body, split_history, list_entries
from memento_tattoo.recall import rank_memento_notes
from memento_tattoo import entries, write_through
from memento_tattoo.tattoo_firing import durable_tattoo_firing_counts


def cli(root, *args):
    return subprocess.run([sys.executable,'-m','memento_tattoo','--root',str(root),'--agent','fixture',*args],
        text=True,capture_output=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


def add(root, body='Situation: maintenance\nNote: Original zebra instruction.', sess='sess_a'):
    result=cli(root,'note-add','--sess',sess,'--kind','seed',body)
    assert result.returncode==0,result.stdout+result.stderr
    return re.search(r'delta:([^\s]+)',result.stdout).group(1)


def read(root, id=None, *extra):
    args=['entry-read',*(['--id',id] if id else []),*extra]
    result=cli(root,*args)
    assert result.returncode==0,result.stdout+result.stderr
    value=json.loads(result.stdout)
    assert hashlib.sha256(value['content'].encode()).hexdigest()==value['sha256']
    return value


def amend(root, entry, body, sess='sess_edit', **kw):
    args=['note-amend','--id',entry['id'],'--expected-sha256',entry['sha256'],'--sess',sess,
          '--author','fixture','--reason','Clarify exception','--evidence','synthetic-owner-message:2',body]
    for key,val in kw.items():args.extend(['--'+key.replace('_','-'),val])
    return cli(root,*args)


@pytest.mark.parametrize('archive',[False,True])
def test_full_note_read_amend_history_retry_and_no_telemetry(tmp_path,archive):
    root=tmp_path/'memory'
    body='Situation: maintenance\nNote: Original zebra instruction.\n'+('Read current status. '*30)+'\nException: preserve running migration.'
    id=add(root,body)
    if archive:(root/'notes.md').rename(root/'notes_archive.md')
    initial=read(root,id)
    assert 'preserve running migration' in initial['content']
    assert initial['source']==str((root/('notes_archive.md' if archive else 'notes.md')).resolve())
    before=snapshot(root)
    update='Situation: maintenance\nNote: Revised walrus instruction.\nException: do not restart during migration.'
    result=amend(root,initial,update)
    assert result.returncode==0,result.stdout+result.stderr
    after=read(root,id)
    assert after['content'].splitlines()[0]==initial['content'].splitlines()[0]
    active,history=split_history(entries.active_with_history(after['content']))
    assert active==update and len(history)==1
    assert 'Original zebra instruction' in history[0]['previous_active']
    assert history[0]['reason']=='Clarify exception' and history[0]['evidence']=='synthetic-owner-message:2'
    assert history[0]['sess']=='sess_edit' and history[0]['author']=='fixture'
    assert not rank_memento_notes('zebra',root=root)
    assert rank_memento_notes('walrus',root=root)[0].note.note_id==id
    changed={p for p in before if before[p]!=snapshot(root).get(p)}
    assert changed=={Path(initial['source']).name}
    assert set(before)==set(snapshot(root))
    stable=snapshot(root)
    assert amend(root,initial,update).returncode==0 and snapshot(root)==stable
    second='Situation: maintenance\nNote: Current otter approach.'
    assert amend(root,after,second,'sess_later').returncode==0
    latest=read(root,id);stable=snapshot(root)
    assert amend(root,initial,update).returncode!=0 and snapshot(root)==stable
    active,history=split_history(entries.active_with_history(latest['content']))
    assert len(history)==2 and history[1]['previous_active']==update
    assert all('memento-history' not in revision['previous_active'] for revision in history)
    markdown=cli(root,'entry-read','--id',id,'--format','markdown')
    assert markdown.returncode==0 and '### Previous active content\n\nSituation: maintenance\nNote: Original zebra' in markdown.stdout
    assert not (root/'retention_log.jsonl').exists() and not (root/'tattoo_firing.json').exists()


def test_history_citations_do_not_inflate_durable_tattoo_mentions(tmp_path):
    id=add(tmp_path,'Situation: validation\nNote: See [[sess_demo.tattoo.1234]] before release.')
    first=read(tmp_path,id)
    assert durable_tattoo_firing_counts(tmp_path)['sess_demo.tattoo.1234']['count']==1
    result=amend(tmp_path,first,'Situation: validation\nNote: Again see [[sess_demo.tattoo.1234]] before release.')
    assert result.returncode==0
    assert durable_tattoo_firing_counts(tmp_path)['sess_demo.tattoo.1234']['count']==1


def test_recall_full_read_reference_and_clipping(tmp_path):
    id=add(tmp_path,'Situation: health check\nNote: '+'Inspect status. '*40+'\nException: do not restart migration.')
    result=cli(tmp_path,'load','--query','health check')
    assert result.returncode==0 and 'excerpt_clipped: true' in result.stdout
    reference=next(line.split('read_reference: ',1)[1] for line in result.stdout.splitlines() if 'read_reference:' in line)
    command=shlex.split(reference)
    result=subprocess.run([sys.executable,'-m','memento_tattoo',*command[1:]],capture_output=True,text=True)
    assert result.returncode==0 and json.loads(result.stdout)['id']==id
    assert 'do not restart migration' in json.loads(result.stdout)['content']


def test_reads_tattoo_sessions_archives_and_legacy_source(tmp_path):
    tattoo=cli(tmp_path,'tattoo-add','--sess','sess_tat','Approved fixture principle.')
    id=re.search(r'delta:([^\s]+)',tattoo.stdout).group(1)
    assert 'Approved fixture principle.' in read(tmp_path,id)['content']
    session=cli(tmp_path,'session-add','--sess','sess_session','--date','2025-01-01','--accomplished','Completed.\nQualification: pending review.')
    assert session.returncode==0
    assert 'Qualification: pending review.' in read(tmp_path,'sess_session')['content']
    assert cli(tmp_path,'session-archive','--days','1','--apply').returncode==0
    assert '/archive/' in read(tmp_path,'sess_session')['source']
    path=tmp_path/'notes.md';path.write_text('# Legacy notes\n## Lesson\nUnmarked full evidence.\n')
    record=read(tmp_path,None,'--source','notes.md')
    assert record['content']==path.read_text() and record['identity']=='content snapshot'
    assert read(tmp_path,record['id'],'--source','notes.md')['content']==record['content']
    path.write_text(path.read_text()+'Changed.\n')
    assert cli(tmp_path,'entry-read','--id',record['id'],'--source','notes.md').returncode!=0


def test_actual_project_operations_read_correct_section(tmp_path):
    root=tmp_path/'root';project=tmp_path/'project'
    ids=[]
    for section,body,sess in [('## State','CURRENT BODY','sess_current'),('## Decisions','OWNER DECISION','sess_decision')]:
        result=cli(root,'project-edit','--project',str(project),'--section',section,'--sess',sess,'--replace',body)
        assert result.returncode==0
        ids.append(re.search(r'delta:([^\s]+)',result.stdout).group(1))
    a=read(root,ids[0],'--project',str(project));b=read(root,ids[1],'--project',str(project))
    assert 'CURRENT BODY' in a['content'] and 'OWNER DECISION' not in a['content'] and '## Decisions' not in a['content']
    assert a['scope']=='## State' and b['scope']=='## Decisions'
    assert 'OWNER DECISION' in b['content'] and 'CURRENT BODY' not in b['content']
    assert cli(root,'entry-read','--id',ids[0],'--source',str(project/'memory.md')).returncode!=0


def test_project_file_snapshot_invalidates_on_change_and_disambiguates_sources(tmp_path):
    root=tmp_path/'root';root.mkdir()
    projects=[tmp_path/'one',tmp_path/'two']
    pair='- Situation: planning alpha\n- Note: preserve qualification\n'
    for p in projects:p.mkdir();(p/'memory.md').write_text('# Project\n\n'+pair)
    result=cli(root,'load','--query','planning','--project',str(projects[0]),'--project',str(projects[1]))
    assert result.returncode==0
    id=next(line.split('entry_id: ',1)[1] for line in result.stdout.splitlines() if 'entry_id:' in line)
    assert id.startswith('project-file:')
    assert cli(root,'entry-read','--id',id,'--project',str(projects[0]),'--project',str(projects[1])).returncode!=0
    first=read(root,id,'--source',str(projects[0]/'memory.md'),'--project',str(projects[0]))
    (projects[0]/'memory.md').write_text('# Earlier\n- Situation: unrelated\n- Note: prior\n\n'+pair)
    assert cli(root,'entry-read','--id',id,'--project',str(projects[0])).returncode!=0
    (projects[0]/'memory.md').write_text(pair.replace('qualification','changed'))
    assert cli(root,'entry-read','--id',id,'--project',str(projects[0])).returncode!=0


def test_ambiguous_and_missing_ids_reject_without_writes(tmp_path):
    id=add(tmp_path);(tmp_path/'notes_archive.md').write_bytes((tmp_path/'notes.md').read_bytes())
    before=snapshot(tmp_path)
    assert cli(tmp_path,'entry-read','--id',id).returncode!=0
    assert cli(tmp_path,'entry-read','--id','missing').returncode!=0
    assert read(tmp_path,id,'--source','notes.md')['id']==id
    assert snapshot(tmp_path)==before


@pytest.mark.parametrize('bad',[
 'Situation: one\nNote: two\n<!-- delta:sess_fake.note.1234 -->\nNote: injected',
 'Situation: one\nNote: two\n<!-- memento-history:v1\n{}\n-->',
 'Situation: one\nNote: two\nNote: duplicate',
 'Situation: one\nNote: two\n---\n[sess_header | injected]',
 'Situation:\nNote: value',
 'Situation: one\nNote:',
])
def test_structural_amendment_rejects_without_writes(tmp_path,bad):
    id=add(tmp_path);entry=read(tmp_path,id);before=snapshot(tmp_path)
    result=amend(tmp_path,entry,bad)
    assert result.returncode!=0 and snapshot(tmp_path)==before


@pytest.mark.parametrize('option',['reason','evidence','author'])
def test_provenance_required(tmp_path,option):
    id=add(tmp_path);entry=read(tmp_path,id);before=snapshot(tmp_path)
    assert amend(tmp_path,entry,'Situation: one\nNote: two',**{option:''}).returncode!=0
    assert snapshot(tmp_path)==before


def test_successor_validation_missing_self_cycle_and_valid(tmp_path):
    a=read(tmp_path,add(tmp_path,sess='sess_a'));b=read(tmp_path,add(tmp_path,'Situation: other\nNote: successor.',sess='sess_b'))
    for target in ['missing',a['id']]:
        before=snapshot(tmp_path)
        assert amend(tmp_path,a,'Situation: old\nNote: retired\nSuperseded-by: '+target).returncode!=0
        assert snapshot(tmp_path)==before
    assert amend(tmp_path,a,'Situation: old\nNote: retired\nSuperseded-by: '+b['id']).returncode==0
    before=snapshot(tmp_path)
    assert amend(tmp_path,b,'Situation: other\nNote: cycle\nSuperseded-by: '+a['id'],'sess_cycle').returncode!=0
    assert snapshot(tmp_path)==before


def test_concurrent_amendment_accepts_one_and_preserves_loser(tmp_path):
    entry=read(tmp_path,add(tmp_path))
    def edit(i):return amend(tmp_path,entry,f'Situation: task\nNote: concurrent-{i}',f'sess_writer{i}')
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(edit,[1,2]))
    assert sorted(r.returncode for r in results)==[0,2]
    result=read(tmp_path,entry['id'])
    assert len(split_history(entries.active_with_history(result['content']))[1])==1


def test_atomic_failure_preserves_original_then_retry_succeeds(tmp_path,monkeypatch):
    entry=read(tmp_path,add(tmp_path));before=snapshot(tmp_path)
    atomic=write_through._atomic_write
    def fail(path,text):raise OSError('injected atomic failure')
    monkeypatch.setattr(write_through,'_atomic_write',fail)
    with pytest.raises(OSError):
        entries.amend_note(entry['id'],'Situation: fix\nNote: revised',root=tmp_path,expected_sha256=entry['sha256'],sess='sess_fix',author='fixture',reason='fix',evidence='owner:2')
    assert snapshot(tmp_path)==before
    monkeypatch.setattr(write_through,'_atomic_write',atomic)
    assert amend(tmp_path,entry,'Situation: fix\nNote: revised').returncode==0


def test_declared_sources_reject_symlink_escape_and_arbitrary_paths(tmp_path):
    root=tmp_path/'root';root.mkdir();outside=tmp_path/'outside.md';outside.write_text('DO NOT READ OUTSIDE')
    (root/'notes.md').symlink_to(outside)
    before=snapshot(tmp_path)
    result=cli(root,'entry-read','--source','notes.md')
    assert result.returncode!=0 and 'DO NOT READ' not in result.stdout
    result=cli(root,'entry-read','--source',str(outside))
    assert result.returncode!=0 and 'DO NOT READ' not in result.stdout
    assert snapshot(tmp_path)==before


def test_source_scoped_note_operations_ignore_unrelated_malformed_session(tmp_path):
    id=add(tmp_path)
    (tmp_path/'sessions').mkdir()
    (tmp_path/'sessions/sess_broken.md').write_text('malformed unrelated session')
    entry=read(tmp_path,id,'--source','notes.md')
    result=amend(tmp_path,entry,'Situation: task\nNote: valid revision',source='notes.md')
    assert result.returncode==0,result.stdout+result.stderr
    assert 'valid revision' in read(tmp_path,id,'--source','notes.md')['content']


def test_project_pair_reference_preserves_indented_qualification(tmp_path):
    project=tmp_path/'project';project.mkdir()
    (project/'memory.md').write_text('# Project\n\n- Situation: service recovery\n- Note: Restart after failure.\n  Exception: never restart during migration.\n')
    result=cli(tmp_path/'root','load','--query','service recovery','--project',str(project))
    assert result.returncode==0 and 'excerpt_clipped: true' in result.stdout
    ref=next(line.split('read_reference: ',1)[1] for line in result.stdout.splitlines() if 'read_reference:' in line)
    command=shlex.split(ref)
    full=subprocess.run([sys.executable,'-m','memento_tattoo',*command[1:]],capture_output=True,text=True)
    assert full.returncode==0
    assert 'Exception: never restart during migration.' in json.loads(full.stdout)['content']


@pytest.mark.parametrize('kind',['note','project','tattoo'])
def test_crlf_preview_digest_matches_actual_full_read(tmp_path,kind):
    project=tmp_path/'project';project.mkdir()
    if kind=='project':
        (project/'memory.md').write_bytes(b'# Project\r\n\r\n- Situation: recovery\r\n- Note: Keep rollback.\r\n  Exception: preserve migration.\r\n')
        extra=['--project',str(project)]
    elif kind=='tattoo':
        (tmp_path/'tattoos.md').write_bytes(b'<!-- delta:sess_a.tattoo.1234 -->\r\n- Keep recovery rollback.\r\n')
        extra=[]
    else:
        (tmp_path/'notes.md').write_bytes(b'<!-- delta:sess_a.note.1234 -->\r\nSituation: recovery\r\nNote: Keep rollback.\r\n')
        extra=[]
    result=cli(tmp_path,'load','--query','recovery',*extra)
    assert result.returncode==0,result.stdout+result.stderr
    reference=next(line.split('read_reference: ',1)[1] for line in result.stdout.splitlines() if 'read_reference:' in line)
    preview_sha=next(line.split('content_sha256: ',1)[1] for line in result.stdout.splitlines() if 'content_sha256:' in line)
    full=subprocess.run([sys.executable,'-m','memento_tattoo',*shlex.split(reference)[1:]],capture_output=True,text=True)
    assert full.returncode==0,full.stdout+full.stderr
    value=json.loads(full.stdout)
    assert value['sha256']==preview_sha==hashlib.sha256(value['content'].encode()).hexdigest()


def test_stale_manual_fixture_rejects_before_lock_creation(tmp_path):
    (tmp_path/'notes.md').write_text('<!-- delta:sess_legacy.note.1234 -->\nSituation: legacy\nNote: current.\n')
    entry=read(tmp_path,'sess_legacy.note.1234')
    entry['sha256']='0'*64
    before=snapshot(tmp_path)
    assert amend(tmp_path,entry,'Situation: changed\nNote: stale.').returncode!=0
    assert snapshot(tmp_path)==before and not (tmp_path/'.memento.lock').exists()
