from memento_tattoo.agent import format_delta_marker, normalize_agent, parse_delta_marker, resolve_agent


def test_normalize_agent_id():
    assert normalize_agent("Codex CLI") == "codex-cli"
    assert normalize_agent("claude_code") == "claude_code"
    assert normalize_agent("  GPT-5 Agent!! ") == "gpt-5-agent"
    assert normalize_agent("") == "unknown"
    assert normalize_agent(None) == "unknown"


def test_resolve_agent_prefers_explicit_value(monkeypatch):
    monkeypatch.setenv("MEMENTO_AGENT", "claude-code")
    assert resolve_agent("Codex") == "codex"


def test_resolve_agent_uses_environment(monkeypatch):
    monkeypatch.setenv("MEMENTO_AGENT", "Claude Code")
    assert resolve_agent() == "claude-code"


def test_resolve_agent_fallback(monkeypatch):
    monkeypatch.delenv("MEMENTO_AGENT", raising=False)
    assert resolve_agent() == "unknown"


def test_parse_old_delta_marker_without_attrs():
    marker = parse_delta_marker("<!-- delta:sess_abcd.note.11111111 -->")

    assert marker is not None
    assert marker.note_id == "sess_abcd.note.11111111"
    assert marker.sess == "sess_abcd"
    assert marker.kind == "note"
    assert marker.hash == "11111111"
    assert marker.agent == "unknown"


def test_parse_new_delta_marker_with_agent_and_ts():
    marker = parse_delta_marker("<!-- delta:sess_abcd.note.11111111 agent=codex ts=2026-06-17T00:00:00Z -->")

    assert marker is not None
    assert marker.note_id == "sess_abcd.note.11111111"
    assert marker.agent == "codex"
    assert marker.ts == "2026-06-17T00:00:00Z"


def test_format_delta_marker_writes_agent_metadata():
    assert format_delta_marker("sess_abcd.note.11111111", agent="Codex", ts="2026-06-17T00:00:00Z") == (
        "<!-- delta:sess_abcd.note.11111111 agent=codex ts=2026-06-17T00:00:00Z -->"
    )
