"""
Integration tests for the SqliteWordRepository.

These tests validate that the repository correctly persists and retrieves
domain objects using a real SQLite database.

Focus areas:
- Word insertion
- Frequency updates
- Correct mapping between database rows and domain objects

These are integration-style tests (not unit tests), as they exercise
the actual database layer.
"""

from __future__ import annotations

from pathlib import Path

from predictive_texting.domain.lexicon.types import NewWord, WordSource
from predictive_texting.infrastructure.bootstrap.database import bootstrap_sqlite_database
from predictive_texting.infrastructure.repositories.sqlite_word_repository import SqliteWordRepository


def test_sqlite_word_repository_adds_and_retrieves_word(db_path: Path) -> None:
    """
    Verify that a word can be inserted into the repository and retrieved by ID.

    This test ensures:
    - A WordRecord is correctly persisted
    - The generated WordId is valid
    - Retrieved data matches the inserted domain object
    """

    bootstrap_sqlite_database(db_path)
    repository = SqliteWordRepository(db_path)

    record = repository.add_word(
        NewWord(
            word='zzfoobar',
            frequency=0,
            source=WordSource.USER,
        )
    )

    retrieved = repository.get_by_id(record.word_id)

    assert retrieved is not None
    assert retrieved.word_id == record.word_id
    assert retrieved.word == 'zzfoobar'
    assert retrieved.frequency == 0
    assert retrieved.source == WordSource.USER


def test_sqlite_word_repository_updates_frequency(db_path: Path) -> None:
    """
    Verify that updating a word's frequency is persisted correctly.

    This test ensures:
    - Frequency updates are applied in the database
    - The updated value is returned on subsequent retrieval
    """

    bootstrap_sqlite_database(db_path)
    repository = SqliteWordRepository(db_path)

    record = repository.add_word(
        NewWord(
            word='zzfoobar',
            frequency=0,
            source=WordSource.USER,
        )
    )

    repository.update_frequency(record.word_id, 3)

    updated = repository.get_by_id(record.word_id)

    assert updated is not None
    assert updated.frequency == 3
