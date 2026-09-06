from memento_tattoo.registry import registry_queue, drain
from memento_tattoo.recall import render_ranked_notes
import pytest


def test_registry_rechecks_guard_when_another_writer_has_applied(tmp_path):
    original = '- Demo - original/ - active'
    registry_queue('sess_a','add','demo',original,tmp_path,agent='codex', expected_line='')
    assert drain(tmp_path).ok
    q = registry_queue('sess_b','update','demo','- Demo - proposed/ - active',tmp_path,agent='codex',expected_line=original)
    # Preserve the pending operation while another caller applies an update.
    parked = tmp_path/'pending.saved';q.replace(parked)
    registry_queue('sess_c','update','demo','- Demo - owner-current/ - active',tmp_path,agent='codex')
    assert drain(tmp_path).ok
    parked.replace(q)
    before=(tmp_path/'registry.md').read_bytes()
    result=drain(tmp_path)
    assert not result.ok
    assert 'stale registry' in str(result.errors)
    assert q.exists()
    assert (tmp_path/'registry.md').read_bytes()==before


def test_current_project_snapshot_visible_without_lexical_match(tmp_path):
    (tmp_path/'project.md').write_text('## State\nHistorical: four charts.\n\n## Current state\nOwner chose two charts.\n')
    rendered=render_ranked_notes('archive recovery',root=tmp_path)
    assert 'Owner chose two charts' in rendered
    assert 'Historical: four charts' not in rendered
    assert 'current_project_state:' in rendered
