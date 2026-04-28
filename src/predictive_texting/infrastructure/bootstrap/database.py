from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

from ...exceptions.infrastructure import BootstrapError
from ..utils.acquire_lock import acquire_exclusive_lock_with_timeout
from .db.schema_loader import load_schema_sql


def bootstrap_sqlite_database(db_path: Path) -> Path:
    # validate path
    if not isinstance(db_path, Path):
        raise BootstrapError(f'Invalid db_path {db_path!r}; expected a Path object, got {type(db_path)!r}')

    # validate db_path and its parent directory
    _dir = db_path.parent
    if not _dir.exists():
        raise BootstrapError(f'Invalid db_path {db_path!r}; directory {_dir!r} does not exist')
    if not _dir.is_dir():
        raise BootstrapError(f'Invalid db_path {db_path!r}; directory {_dir!r} is not a directory')

    # load schema_sql 
    try:
        schema_sql = load_schema_sql()
    except (ValueError, OSError) as e:
        raise BootstrapError('Failed to load database schema') from e

    lock_file = _dir / 'db_bootstrap.lock'
    try:
        # Acquire exclusive bootstrap lock: delegate to context manager for lock acquisition/release
        with acquire_exclusive_lock_with_timeout(lock_file, timeout=5.0, poll_interval=0.5):
            creating: bool = bool(not db_path.exists())

            conn: sqlite3.Connection | None = None
            try:
                conn = sqlite3.connect(db_path)
                conn.executescript(schema_sql)
                return db_path

            except sqlite3.Error as e:
                # clean up: ensure no partial db file remains on failure
                if creating and db_path.exists():
                    with contextlib.suppress(OSError):
                        db_path.unlink(missing_ok=True)
                raise BootstrapError(f'Failed to bootstrap Sqlite database at {db_path!r}') from e

            finally:
                if conn is not None:
                    conn.close()

    except (BlockingIOError, TimeoutError) as e:
        raise BootstrapError(f'Failed to acquire db bootstrap lock {lock_file!r}') from e
