from __future__ import annotations

from importlib import resources

from ...exceptions.infrastructure import BootstrapError
from ..bootstrap import db as db_pkg


def load_schema_sql(schema_file_name: str) -> str:
    """
    Loads, reads and returns the contents of a schema.sql file.

    Parameters:
    - schema_file_name: basename of the schema file (not a full path)
    - schema_file_name must refer to a file within the infrastructure.db package

    Returns: str

    Raises BootstrapError if:
    - schema_file_name cannot be resolved to a file under infrastructure.db
    - OSError exception is raised when attempting to open and read file

    Notes:
    - does not do any processing or validation, file contents are returned
    as a single str
    """

    schema = resources.files(db_pkg).joinpath(schema_file_name)
    if not schema.is_file():
        raise BootstrapError(f'Failed to load schema {schema_file_name!r}; expected a file')

    try:
        return schema.read_text(encoding='utf-8')
    except OSError as e:
        raise BootstrapError(f'Failed to read schema {schema_file_name!r}') from e


def load_seed_file(seed_file_name: str) -> list[str]:
    """
    Loads, reads and returns the contents of database seed words files.

    Parameters:
    - seed_file_name: basename of the seed word file (not a full path)
    - seed_file_name must refer to a file within the infrastructure.db.seed package

    Returns: list[str]
    - Returns lines in seed file as a list of strings.
    - Each line is stripped of new line characters; empty lines are skipped.
    """

    # DESIGN
    # Considered returning a file handle and letting caller handle reading.
    # Overkill for v0 of this appp, seed files are small.
    # Revisit if seed files grow too large.

    seed = resources.files(db_pkg).joinpath('seed', seed_file_name)
    if not seed.is_file():
        raise BootstrapError(f'Failed to load seed file {seed_file_name!r}; expected a file')

    try:
        with seed.open('r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]  # remove \n, skip empty lines
    except OSError as e:
        raise BootstrapError(f'Failed to open seed file {seed_file_name!r}') from e
