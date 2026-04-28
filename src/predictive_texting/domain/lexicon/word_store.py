from __future__ import annotations

from collections.abc import Iterable

from ...exceptions.domain import WordStoreError
from .protocols import WordStoreProtocol
from .types import Word, WordId, WordRecord, WordSource, validate_frequency


class InMemoryWordStore(WordStoreProtocol):
    """
    In-memory store for word data keyed by WordId.
    Implements the WordStoreProtocol.

    Design Note:
    This store uses `WordId` objects as dictionary keys for internal mappings.
    This keeps the implementation aligned with domain types and simplifies
    interaction with other components.

    However, storing `WordId` objects directly introduces additional memory
    overhead compared to using primitive identifiers (e.g. raw integers).
    If memory usage becomes a concern, this store could be optimized to
    internally use primitive values (e.g. `word_id.value`) while exposing
    `WordId` objects at the interface boundary.

    Such an optimization would remain an internal implementation detail and
    would not affect the public interface of the store.
    """

    __slots__ = (
        '_words_by_id',
        '_freqs_by_id',
        '_sources_by_id',
    )
    _words_by_id: dict[WordId, Word]  # uses WordId objects; see class-level design note
    _freqs_by_id: dict[WordId, int]
    _sources_by_id: dict[WordId, WordSource]

    def __init__(self) -> None:
        self._words_by_id = dict()
        self._freqs_by_id = dict()
        self._sources_by_id = dict()

    def __contains__(self, word_id: object) -> bool:
        """Convenience membership check by word ID."""
        return word_id in self._words_by_id

    def add_record(self, record: WordRecord) -> None:
        """
        Insert a persisted record into the runtime store.

        Raise WordStoreError if record.word_id already exists in the store.
        """
        # NOTE: Only uniqueness of word_ids is guaranteed.
        # Store does not guarantee that words themselves are unique within the store.
        # Later implementations may include this feature and also support reverse lookup.
        # Currently word uniqueness is handled by the Repository persistence layer.

        word_id = record.word_id
        self._word_id_must_not_exist(word_id)
        self._words_by_id[word_id] = record.word
        self._freqs_by_id[word_id] = record.frequency
        self._sources_by_id[word_id] = record.source

    def remove_record(self, word_id: WordId) -> None:
        """
        Remove the record associated with a WordId from the runtime store.

        Raises:
        - WordStoreError: If word_id is not stored.
        """
        self._word_id_exists_or_raise(word_id)
        del self._words_by_id[word_id]
        del self._freqs_by_id[word_id]
        del self._sources_by_id[word_id]

    def update_frequency(self, word_id: WordId, frequency: int) -> None:
        """
        Overwrite the current frequency for a word_id.

        Raises:
        - WordStoreError if word_id is not stored.
        - TypeError/Value error if frequency is invalid.
        """

        # Frequency validation delegated to domain helper.
        # See validate_frequency for domain rules

        validate_frequency(frequency)
        self._word_id_exists_or_raise(word_id)
        self._freqs_by_id[word_id] = frequency

    def clear(self) -> None:
        """Clear current runtime state."""
        self._words_by_id.clear()
        self._freqs_by_id.clear()
        self._sources_by_id.clear()

    def get_word(self, word_id: WordId) -> Word:
        """
        Return the word text for a word_id.

        Raise WordStoreError if word_id is not stored.
        """
        self._word_id_exists_or_raise(word_id)
        return self._words_by_id[word_id]

    def get_frequency(self, word_id: WordId) -> int:
        """
        Return the current frequency for a word_id.

        Raise WordStoreError if word_id is not stored.
        """
        self._word_id_exists_or_raise(word_id)
        return self._freqs_by_id[word_id]

    def get_source(self, word_id: WordId) -> WordSource:
        """
        Return the WordSource for a WordId.

        Raise WordStoreError if word_id is not stored.
        """
        self._word_id_exists_or_raise(word_id)
        return self._sources_by_id[word_id]

    def get_record(self, word_id: WordId) -> WordRecord:
        """
        Return a WordRecord snapshot for a WordId.

        Raise WordStoreError if word_id is not stored.
        """
        self._word_id_exists_or_raise(word_id)
        return WordRecord(
            word_id,
            self._words_by_id[word_id],
            self._freqs_by_id[word_id],
            self._sources_by_id[word_id],
        )

    @property
    def word_count(self) -> int:
        return len(self._words_by_id)

    @classmethod
    def from_records(cls, word_records: Iterable[WordRecord]) -> InMemoryWordStore:
        store = cls()
        for record in word_records:
            store.add_record(record)
        return store

    # ---------------- Internal Helpers ----------------
    def _word_id_exists(self, word_id: WordId) -> bool:
        return word_id in self._words_by_id

    def _word_id_exists_or_raise(self, word_id: WordId) -> None:
        """Guard check: raises WordStoreError if word_id is not stored."""
        if not self._word_id_exists(word_id):
            raise WordStoreError(f'No record with WordId {word_id!r} exists in store')

    def _word_id_must_not_exist(self, word_id: WordId) -> None:
        if self._word_id_exists(word_id):
            raise WordStoreError(f'A record with WordId {word_id!r} already exists in store')
