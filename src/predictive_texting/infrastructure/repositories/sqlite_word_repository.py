from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from ...application.word_prediction.interfaces import WordRepositoryProtocol
from ...domain.lexicon.types import (
    NewWord,
    Word,
    WordId,
    WordRecord,
    WordSource,
    normalise_word,
    validate_frequency,
    validate_word,
)
from ...exceptions.infrastructure import RepositoryError
from ..utils.time_utils import now_utc_str


class SqliteWordRepository(WordRepositoryProtocol):
    """
    SQLite-backed implementation of the WordRepositoryProtocol.

    This repository persists lexicon word data in a SQLite database and translates
    between SQLite rows and validated domain objects (`NewWord`, `WordRecord`, `WordId`).

    Design Notes:
    - Raw persisted data is converted back into domain objects at the repository
      boundary.
    - Public repository methods raise `RepositoryError` on persistence failures
      or invalid persisted data.
    - Word creation accepts a validated `NewWord` domain object, while some query
      and update operations still accept primitive-like values (e.g. raw word text,
      frequency) and validate them at the repository boundary.
    """

    __slots__ = (
        '_db_path',
        '_conn',
    )
    _db_path: str
    _conn: sqlite3.Connection | None

    def __init__(self, db_path: Path | str) -> None:
        """
        Initialize the repository and open a SQLite connection.

        Raises:
        - RepositoryError: If the database connection cannot be established.
        """
        self._db_path = str(db_path)
        self._conn = None
        self._connect()

    def close(self) -> None:
        """
        Close the underlying SQLite connection.

        Safe to call multiple times.
        """
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def add_word(self, new_word: NewWord) -> WordRecord:
        """
        Persist a new word and return the created record.

        Args:
        - new_word: Validated domain object representing the word to persist.

        Returns:
        - WordRecord: Persisted record including generated WordId.

        Raises:
        - RepositoryError: If the word already exists, the insert fails.
        """

        sql = """
            INSERT INTO WORDS (WORD, FREQUENCY, SOURCE, CREATED_TS)
            VALUES (:WORD, :FREQUENCY, :SOURCE, :CREATED_TS)
        """

        params = {
            'WORD': new_word.word,
            'FREQUENCY': new_word.frequency,
            'SOURCE': new_word.source,
            'CREATED_TS': now_utc_str(),
        }

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                word_id = cursor.lastrowid
                if not isinstance(word_id, int):
                    raise RepositoryError(f'Error adding word {new_word.word!r}')

            except sqlite3.IntegrityError as e:
                raise RepositoryError(f'Word already exists: {new_word.word!r}') from e
            except sqlite3.Error as e:
                raise RepositoryError(f'Error adding word {new_word.word!r}') from e
            finally:
                cursor.close()

        return WordRecord(
            WordId(word_id),
            new_word.word,
            new_word.frequency,
            new_word.source,
        )

    def remove_word(self, word_id: WordId) -> None:
        """
        Soft-delete a persisted word by setting its deletion timestamp.

        Args:
        - word_id: Identifier of the word to remove.

        Raises:
        - RepositoryError: If the delete operation fails, or if the word does not
        exist or is already deleted.
        """

        sql = """
            UPDATE WORDS
            SET DELETED_TS = :DELETED_TS
            WHERE WORD_ID = :WORD_ID
            AND DELETED_TS IS NULL
        """

        params = {'WORD_ID': word_id.value, 'DELETED_TS': now_utc_str()}

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                rowcount = cursor.rowcount

            except sqlite3.Error as e:
                raise RepositoryError(f'Error removing word; word_id {word_id.value!r}') from e
            finally:
                cursor.close()

        if rowcount == 0:
            raise RepositoryError(f'Word does not exist or is already deleted; word_id {word_id.value!r}')

    def update_frequency(self, word_id: WordId, frequency: int) -> None:
        """
        Persist a new frequency value for an existing word.

        Args:
        - word_id: Identifier of the word to update.
        - frequency: New frequency value.

        Raises:
        - RepositoryError: If frequency is invalid, if the update fails, or if the
        target word does not exist or is deleted.
        """

        # delegate to domain helper for frequency validation
        try:
            validate_frequency(frequency)
        except (TypeError, ValueError) as e:
            raise RepositoryError('Error updating frequency; invalid value') from e

        sql = """
            UPDATE WORDS 
            SET FREQUENCY = :FREQUENCY, UPDATED_TS = :UPDATED_TS
            WHERE WORD_ID = :WORD_ID 
            AND DELETED_TS IS NULL
        """
        params = {'WORD_ID': word_id.value, 'FREQUENCY': frequency, 'UPDATED_TS': now_utc_str()}

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                rowcount = cursor.rowcount

            except sqlite3.Error as e:
                raise RepositoryError(f'Error updating frequency of word_id {word_id.value!r}') from e
            finally:
                cursor.close()

        if rowcount == 0:
            raise RepositoryError(f'Word does not exist or is deleted; word_id {word_id.value!r}')

    def load_all(self) -> list[WordRecord]:
        """
        Load all non-deleted persisted word records.

        Returns:
        - list[WordRecord]: All active persisted records.

        Raises:
        - RepositoryError: If the query fails or persisted rows cannot be converted
        into valid domain records.
        """

        sql = """
            SELECT WORD_ID, WORD, FREQUENCY, SOURCE 
            FROM WORDS 
            WHERE DELETED_TS IS NULL
        """

        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            return self._records_from_rows(cursor.fetchall())

        except sqlite3.Error as e:
            raise RepositoryError('Error loading words from repository') from e

        finally:
            cursor.close()

    def get_by_word(self, word: Word) -> WordRecord | None:
        """
        Return the persisted record for a word, if present.

        The input word is normalized and validated before querying.

        Args:
        - word: Word text to look up.

        Returns:
        - WordRecord | None: Matching persisted record, or None if not found.

        Raises:
        - RepositoryError: If the input word is invalid, the query fails, or
        persisted data cannot be converted into a valid domain record.
        """

        # delegate word normalisation and validation to domain helpers
        # see domain for normalisation/validation rules
        try:
            normalised_word = normalise_word(word)
            validate_word(normalised_word)
        except (TypeError, ValueError) as e:
            raise RepositoryError('Error retrieving word; invalid word') from e

        sql = """
            SELECT WORD_ID, WORD, FREQUENCY, SOURCE
            FROM WORDS
            WHERE WORD = :WORD
            AND DELETED_TS IS NULL
        """
        params = {'WORD': normalised_word}

        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            return self._record_from_row(cursor.fetchone())

        except sqlite3.Error as e:
            raise RepositoryError(f'Error retrieving word {word!r}') from e
        finally:
            cursor.close()

    def get_by_id(self, word_id: WordId) -> WordRecord | None:
        """
        Return the persisted record for a WordId, if present.

        Args:
        - word_id: Identifier of the word to retrieve.

        Returns:
        - WordRecord | None: Matching persisted record, or None if not found.

        Raises:
        - RepositoryError: If the query fails or persisted data cannot be converted
        into a valid domain record.
        """

        sql = """
            SELECT WORD_ID, WORD, FREQUENCY, SOURCE
            FROM WORDS
            WHERE WORD_ID = :WORD_ID
            AND DELETED_TS IS NULL
        """
        params = {'WORD_ID': word_id.value}

        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            return self._record_from_row(cursor.fetchone())

        except sqlite3.Error as e:
            raise RepositoryError(f'Error retrieving word_id {word_id.value!r}') from e
        finally:
            cursor.close()

    def is_empty(self) -> bool:
        """
        Return True if the repository contains no active persisted words.

        Returns:
        - bool: True if no non-deleted records exist, otherwise False.

        Raises:
        - RepositoryError: If the repository count cannot be retrieved.
        """
        return self.word_count == 0

    @property
    def word_count(self) -> int:
        """
        Return the number of active persisted words.

        Returns:
        - int: Count of non-deleted persisted records.

        Raises:
        - RepositoryError: If the count query fails.
        """

        sql = """
            SELECT COUNT(*) AS WORD_COUNT
            FROM WORDS
            WHERE DELETED_TS IS NULL
        """

        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(sql)
            row = cursor.fetchone()
        except sqlite3.Error as e:
            raise RepositoryError('Error retrieving word count') from e
        finally:
            cursor.close()

        return int(row['WORD_COUNT'])

    # additional method for runtime construction/datat seeding (not defined in interface protocol)
    def seed(self, words: Iterable[NewWord]) -> None:
        """
        Seed the repository with validated NewWord domain objects.

        Existing words are ignored, making this operation idempotent for bootstrap use.

        Raises:
        - RepositoryError: If the seed operation fails.
        """

        sql = """
            INSERT OR IGNORE INTO WORDS (WORD, FREQUENCY, SOURCE, CREATED_TS)
            VALUES (:WORD, :FREQUENCY, :SOURCE, :CREATED_TS)
        """

        created_ts = now_utc_str()

        params = [
            {
                'WORD': word.word,
                'FREQUENCY': word.frequency,
                'SOURCE': word.source,
                'CREATED_TS': created_ts,
            }
            for word in words
        ]

        if not params:
            return

        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.executemany(sql, params)
            except sqlite3.Error as e:
                raise RepositoryError('Error seeding word repository') from e
            finally:
                cursor.close()

    # ---------- Internal Helpers --------------
    def _connect(self) -> None:
        """
        Establish the underlying SQLite connection if not already connected.

        Raises:
        - RepositoryError: If the database connection cannot be established.
        """
        if self._conn is None:
            db_path = self._db_path
            try:
                self._conn = sqlite3.connect(database=db_path)
                self._conn.row_factory = sqlite3.Row
            except sqlite3.Error as e:
                self._conn = None
                raise RepositoryError(f'Error connecting to Database at {db_path!r}') from e

    def _get_db_connection(self) -> sqlite3.Connection:
        """
        Return the active SQLite connection, reconnecting if needed.

        Returns:
        - sqlite3.Connection: Active database connection.

        Raises:
        - RepositoryError: If a connection cannot be established.
        """
        if self._conn is None:
            self._connect()

        assert self._conn is not None
        return self._conn

    @staticmethod
    def _record_from_row(row: sqlite3.Row | None) -> WordRecord | None:
        """
        Convert a SQLite row into a WordRecord.

        Args:
        - row: Database row or None.

        Returns:
        - WordRecord | None: Converted domain record, or None if row is None.

        Raises:
        - RepositoryError: If row data cannot be converted into a valid
        WordRecord.
        """
        if row is None:
            return None

        try:
            return WordRecord(
                WordId(row['WORD_ID']),
                row['WORD'],
                row['FREQUENCY'],
                WordSource(row['SOURCE']),
            )
        except (TypeError, ValueError) as e:
            raise RepositoryError('Persisted word data is invalid') from e

    def _records_from_rows(self, rows: list[sqlite3.Row]) -> list[WordRecord]:
        """
        Convert SQLite rows into WordRecord objects.

        Args:
        - rows: Database rows to convert.

        Returns:
        - list[WordRecord]: Converted domain records.

        Raises:
        - RepositoryError: If any row cannot be converted into a valid
        WordRecord.
        """
        return [record for row in rows if (record := self._record_from_row(row)) is not None]
