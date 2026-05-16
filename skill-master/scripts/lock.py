"""
lock.py — File-based mutual exclusion for /master insights invocations.

Usage:
    from scripts.lock import acquire

    with acquire():
        # only one invocation runs this block at a time
        ...
"""

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path

LOCK_PATH = Path("~/.claude/skill-master-insights.lock").expanduser()


@contextmanager
def acquire(lock_path: Path = LOCK_PATH):
    """
    Context manager that acquires an exclusive file lock on `lock_path`.
    A second invocation that finds the lock held exits with a RuntimeError.
    The OS releases the lock automatically when the process exits or the fd is closed.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY)
    try:
        # Non-blocking: raises BlockingIOError if already locked
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RuntimeError(
            "Another /master insights invocation is already running. "
            "Wait for it to finish or remove the lock file: "
            f"{lock_path}"
        )
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
