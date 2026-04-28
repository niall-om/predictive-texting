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
    deadline = time.monotonic() + timeout
    with open(path, 'a+') as f:
        while True:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f'Could not acquire lock on {path!r} within {timeout} seconds') from None
                time.sleep(poll_interval)

        try:
            yield f
        finally:
            # ensure cleanup if calling context exits with an exception
            fcntl.flock(f, fcntl.LOCK_UN)
