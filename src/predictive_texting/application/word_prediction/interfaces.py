from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from predictive_texting.domain.lexicon.types import NewWord, Word, WordId, WordRecord


class WordRepositoryProtocol(Protocol):
    def add_word(self, new_word: NewWord) -> WordRecord:
        """
        Persist a new word and return the created record.

        Args:
        - new_word: Validated domain object representing the word to persist.

        Returns:
        - WordRecord: Persisted record including generated WordId.

        Raises:
        - RepositoryError: If the word already exists, persistence fails, or
          the resulting data cannot be represented as a valid domain record.
        """
        ...

    def remove_word(self, word_id: WordId) -> None:
        """
        Remove a word from the repository.

        Implementations may use soft or hard deletion.

        Args:
        - word_id: Identifier of the word to remove.

        Raises:
        - RepositoryError: If the operation fails or the target word does not
          exist.
        """
        ...

    def update_frequency(self, word_id: WordId, frequency: int) -> None:
        """
        Persist a new frequency value for an existing word.

        Args:
        - word_id: Identifier of the word to update.
        - frequency: New frequency value.

        Raises:
        - RepositoryError: If the frequency is invalid, persistence fails, or
          the target word does not exist.
        """
        ...

    def load_all(self) -> Iterable[WordRecord]:
        """
        Load all non-deleted persisted word records.

        Returns:
        - Iterable[WordRecord]: All active persisted records.

        Raises:
        - RepositoryError: If the underlying data source cannot be read or
          persisted data cannot be converted into valid domain records.
        """
        ...

    def get_by_word(self, word: Word) -> WordRecord | None:
        """
        Return the persisted record for a word, if present.

        Args:
        - word: Word text to look up.

        Returns:
        - WordRecord | None: Matching persisted record, or None if not found.

        Raises:
        - RepositoryError: If the input is invalid, the query fails, or persisted
          data cannot be converted into a valid domain record.
        """
        ...

    def get_by_id(self, word_id: WordId) -> WordRecord | None:
        """
        Return the persisted record for a WordId, if present.

        Args:
        - word_id: Identifier of the word to retrieve.

        Returns:
        - WordRecord | None: Matching persisted record, or None if not found.

        Raises:
        - RepositoryError: If the query fails or persisted data cannot be
          converted into a valid domain record.
        """
        ...

    def is_empty(self) -> bool:
        """
        Return True if the repository contains no active persisted words.

        Returns:
        - bool: True if no records exist, otherwise False.

        Raises:
        - RepositoryError: If the repository state cannot be determined.
        """
        ...

    @property
    def word_count(self) -> int:
        """
        Return the number of active persisted words.

        Returns:
        - int: Count of stored non-deleted records.

        Raises:
        - RepositoryError: If the count cannot be retrieved.
        """
        ...
