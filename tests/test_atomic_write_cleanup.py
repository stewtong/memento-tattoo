"""A failed temp-then-replace write must not leave a .tmp file behind."""
from __future__ import annotations

import pathlib

import pytest

from memento_tattoo import registry, rebuild, retention, session_store, write_through


def _text_call(module):
    return lambda path: module._atomic_write(path, "new content\n")


def _lines_call(path):
    retention._atomic_write(path, ["new content"])


HELPERS = [
    pytest.param(_text_call(write_through), id="write_through"),
    pytest.param(_text_call(registry), id="registry"),
    pytest.param(_text_call(session_store), id="session_store"),
    pytest.param(_text_call(rebuild), id="rebuild"),
    pytest.param(_lines_call, id="retention"),
]


def _tmp_files(directory):
    return [p.name for p in directory.iterdir() if p.name.endswith(".tmp")]


def _break_write(monkeypatch):
    real = pathlib.Path.write_text

    def partial(self, data, *args, **kwargs):
        if self.name.endswith(".tmp"):
            real(self, data[: max(1, len(data) // 2)], *args, **kwargs)
            raise OSError("simulated full disk")
        return real(self, data, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "write_text", partial)


def _break_replace(monkeypatch):
    real = pathlib.Path.replace

    def failing(self, target):
        if self.name.endswith(".tmp"):
            raise OSError("simulated replace failure")
        return real(self, target)

    monkeypatch.setattr(pathlib.Path, "replace", failing)


@pytest.mark.parametrize("call", HELPERS)
@pytest.mark.parametrize("existing", [True, False], ids=["target_exists", "target_absent"])
@pytest.mark.parametrize("breaker", [_break_write, _break_replace], ids=["write_fails", "replace_fails"])
def test_failed_write_leaves_no_tmp_and_target_unchanged(tmp_path, monkeypatch, call, existing, breaker):
    target = tmp_path / "data.md"
    if existing:
        target.write_text("original\n", encoding="utf-8")
    breaker(monkeypatch)
    with pytest.raises(OSError):
        call(target)
    monkeypatch.undo()
    assert _tmp_files(tmp_path) == []
    if existing:
        assert target.read_text(encoding="utf-8") == "original\n"
    else:
        assert not target.exists()
