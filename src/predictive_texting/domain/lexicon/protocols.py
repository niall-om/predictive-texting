from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ..encoding.types import EncodedIndexKeySequence
from .types import Word, WordId, WordRecord, WordSource


class WordStoreProtocol(Protocol):
    def __contains__(self, word_id: object) -> bool:
        """Convenience membership check by word ID."""
        ...

    def add_record(self, record: WordRecord) -> None:
        """
        Insert a persisted record into the runtime store.

        Raise WordStoreError if record.word_id already exists in the store.
        """
        ...

    def remove_record(self, word_id: WordId) -> None:
        """
        Remove the record associated with a WordId from the runtime store.

        Raises:
        - WordStoreError: If word_id is not stored.
        """
        ...

    def update_frequency(self, word_id: WordId, frequency: int) -> None:
        """
        Overwrite the current frequency for a word_id.

        Raises:
        - WordStoreError if word_id is not stored.
        - TypeError/Value error if frequency is invalid.

        """
        ...

    def clear(self) -> None:
        """Clear current runtime state."""
        ...

    def get_word(self, word_id: WordId) -> Word:
        """
        Return the word text for a word_id.

        Raise WordStoreError if word_id is not stored.
        """
        ...

    def get_frequency(self, word_id: WordId) -> int:
        """
        Return the current frequency for a word_id.

        Raise WordStoreError if word_id is not stored.
        """
        ...

    def get_source(self, word_id: WordId) -> WordSource:
        """
        Return the WordSource for a WordId.

        Raise WordStoreError if word_id is not stored.
        """
        ...

    def get_record(self, word_id: WordId) -> WordRecord:
        """
        Return a WordRecord snapshot for a WordId.

        Raise WordStoreError if word_id is not stored.
        """
        ...

    @property
    def word_count(self) -> int:
        """Return the number of words stored."""
        ...


class RankedCompletionIndexProtocol(Protocol):
    def insert(self, word_id: WordId, sequence: EncodedIndexKeySequence) -> None:
        """
        Insert a word into the completion index.

        Raises CompletionIndexError if:
        - sequence is not valid (not consistent with keyspace of the index).
        - word_id is already stored in the index.

        Note:
        This associates the given word_id with the provided encoded key sequence
        and updates all relevant index structures (e.g. trie nodes and ranking summaries)
        along the path defined by the sequence.

        This method is used during:
        - initial index construction (bootstrapping)
        - insertion of newly learned words
        """
        ...

    def delete(self, word_id: WordId, sequence: EncodedIndexKeySequence) -> bool:
        """
        Delete a word ID from the completion index.

        Returns True if the word ID is present in the index and is deleted.
        Returns False if the word ID is not present in the index.

        Raises CompletionIndexError if:
        - sequence is not valid (not consistent with keyspace of the index).
        - sequence is not stored in the index.
        """
        ...

    def get_ranked_candidates(self, sequence: EncodedIndexKeySequence) -> Sequence[WordId]:
        """
        Return the top-K ranked candidate word IDs for the given encoded key sequence;
        where K is defined by the index at construction time.

        If the sequence does not exist in the index, an empty list is returned.

        Raises CompletionIndexError if:
        - sequence is not valid (not consistent with keyspace of the index).

        Note:
        The sequence defines a position in the index (e.g. a node in a trie).
        The method returns up to k word IDs corresponding to words whose encoded
        sequences share the same prefix, ordered according to the index's ranking policy.
        """
        ...

    def refresh_index(self, sequence: EncodedIndexKeySequence) -> None:
        """
        Recompute cached ranking summaries along the path defined by the given encoded key sequence.

        Raises CompletionIndexError if:
        - sequence is not valid (not consistent with keyspace of the index).
        - sequence is not stored in the index.

        Note:
        This should be called when ranking-relevant metadata for one or more words associated
        with the sequence has changed (for example, word frequency in the WordStore).
        """
        ...

    def clear(self) -> None:
        """Clear current runtime state."""
        ...

    @property
    def word_count(self) -> int:
        """Return the number of indexed words."""
        ...

    @property
    def k(self) -> int:
        """Return k, the number of candidates included in get_ranked_candidates."""
        ...
