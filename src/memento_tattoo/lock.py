from __future__ import annotations

import errno
import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import paths_for


DEFAULT_TIMEOUT = 10.0
_BACKOFF = 0.1
_held: set[str] = set()


class LockTimeout(RuntimeError):
    """Raised when the root lock cannot be acquired within the timeout."""


@contextmanager
def memory_lock(root: Path, *, timeout: float = DEFAULT_TIMEOUT) -> Iterator[None]:
    path = paths_for(root).lock
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path.parent.resolve() / path.name)
    if key in _held:
        raise RuntimeError("memory_lock is not re-entrant")

    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                    raise
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"could not acquire lock within {timeout}s: {path}") from exc
                time.sleep(_BACKOFF)
        _held.add(key)
        try:
            yield
        finally:
            _held.discard(key)
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
