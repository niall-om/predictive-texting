from __future__ import annotations

import fcntl
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO


@contextmanager
def acquire_exclusive_lock_with_timeout(
    path: Path,
    timeout: float = 5.0,
    poll_interval: float = 0.5,
) -> Iterator[TextIO]:
    """
    Acquire an exclusive file lock with a timeout.

    Attempts to obtain a non-blocking exclusive lock on the given file. If the
    lock is not immediately available, it retries until the timeout is reached.

    This is used to coordinate access between multiple processes, ensuring that
    only one process performs critical operations (e.g. database bootstrapping)
    at a time.

    Args:
        path: Path to the lock file.
        timeout: Maximum time to wait for the lock (in seconds).
        poll_interval: Time to wait between retry attempts.

    Yields:
        An open file object with the lock held.

    Raises:
        TimeoutError: If the lock cannot be acquired within the timeout.
    """
    deadline = time.monotonic() + timeout

    # file open before locking: lock is on file descriptor
    with open(path, 'a+') as f:
        while True:
            try:
                # attempt non-blocking acquistion: outer loop handles waiting
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f'Could not acquire lock on {path!r} within {timeout} seconds') from None
                time.sleep(poll_interval)

        # Yield control to caller while holding the lock.
        # Cleanup (unlock + close) happens in the finally block when context exits.
        try:
            yield f
        finally:
            # ensure cleanup if calling context exits with an exception
            # critical - prevents deadlocks
            fcntl.flock(f, fcntl.LOCK_UN)
