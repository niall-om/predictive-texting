from __future__ import annotations

from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent
_SCHEMA_FILE = _BASE_DIR / 'schema.sql'


# public accessor
def load_schema_sql() -> str:
    if not _SCHEMA_FILE.exists():
        raise ValueError(f'Schema file {_SCHEMA_FILE!r} does not exist')

    if not _SCHEMA_FILE.is_file():
        raise ValueError(f'Invalid schema file: {_SCHEMA_FILE!r} is not a file')

    try:
        return _SCHEMA_FILE.read_text(encoding='utf-8')
    except OSError as e:
        raise ValueError(f'Failed to load schema file {_SCHEMA_FILE!r}') from e
