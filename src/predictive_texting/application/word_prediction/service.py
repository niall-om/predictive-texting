from __future__ import annotations

from collections.abc import Iterable

from ...domain.encoding.protocols import KeyEncoderProtocol
from ...domain.encoding.types import EncodedIndexKeySequence, IndexKey
from ...domain.lexicon.protocols import RankedCompletionIndexProtocol, WordStoreProtocol
from ...domain.lexicon.types import NewWord, Word, WordId, WordRecord, WordSource, normalise_word, validate_word
from ...exceptions.application import WordPredictionServiceError
from ...exceptions.domain import CompletionIndexError, EncodingError, WordStoreError
from ...exceptions.infrastructure import RepositoryError
from .dtos import CandidateWord
from .interfaces import WordRepositoryProtocol


class WordPredictionService:
    __slots__ = (
        '_word_repository',
        '_word_store',
        '_key_encoder',
        '_completion_index',
        '_is_hydrated',
    )
    _word_repository: WordRepositoryProtocol
    _word_store: WordStoreProtocol
    _key_encoder: KeyEncoderProtocol
    _completion_index: RankedCompletionIndexProtocol
    _is_hydrated: bool

    def __init__(
        self,
        word_repository: WordRepositoryProtocol,
        word_store: WordStoreProtocol,
        key_encoder: KeyEncoderProtocol,
        completion_index: RankedCompletionIndexProtocol,
    ) -> None:
        # validate expected runtime lifecycle contract:
        # repository/encoder may already be ready, but in-memory runtime structures
        # should be empty and populated via hydrate
        if word_store.word_count != 0:
            raise WordPredictionServiceError(
                f'Expected empty WordStore at service construction; got word_count={word_store.word_count}'
            )

        if completion_index.word_count != 0:
            raise WordPredictionServiceError(
                f'Expected empty RankedCompletionIndex at service construction; '
                f'got word_count={completion_index.word_count}'
            )

        self._word_repository = word_repository
        self._word_store = word_store
        self._key_encoder = key_encoder
        self._completion_index = completion_index
        self._is_hydrated = False

    def hydrate(self) -> None:
        """
        Rebuilds in-memory datastructures from current contents of word repository.

        Idempotent with respect to repository contents
        (same repository => same runtime state after hydration).

        Atomic: either full hydration succeeds or rollback to empty in-memory runtme state.
        Ensures consistent empty state on failures.

        Raise WordPredictionServiceError when hydration fails.
        """
        self._word_store.clear()
        self._completion_index.clear()
        self._is_hydrated = False

        # hydration should be atomic
        try:
            for record in self._word_repository.load_all():
                self._word_store.add_record(record)
                sequence = self._key_encoder.encode(record.word)
                self._completion_index.insert(record.word_id, sequence)

        # catch broad exception here as hydration is an explicitly atomic rebuild path;
        # any failure means hyrdation failed.
        except Exception as e:
            # ensure consistent empty state on ANY failure
            self._word_store.clear()
            self._completion_index.clear()
            raise WordPredictionServiceError('Failed to hydrate service') from e

        self._is_hydrated = True

    def add_word(self, word: Word, source: WordSource = WordSource.USER) -> WordRecord:
        """
        Add a new word to the system and synchronize all runtime structures.

        This method performs the following steps:
        1. Validates and normalizes the input using domain value objects.
        2. Encodes the word into an index key sequence.
        3. Persists the word in the repository (source of truth).
        4. Updates in-memory structures (WordStore and CompletionIndex).

        The operation is designed to be atomic with respect to system consistency:
        - If persistence fails, no changes are made.
        - If in-memory synchronization fails after persistence, a best-effort rollback
        is performed by undoing applied changes in reverse order
        (CompletionIndex → WordStore → Repository).
        - If rollback itself fails, the service is marked as not hydrated and must be
        rehydrated before further use.

        Args:
        - word: Raw word input.
        - source: Origin of the word (default is user-provided).

        Returns:
        - WordRecord: Persisted record including generated WordId.

        Raises:
        - TypeError, ValueError: If the input word or source is invalid (domain validation).
        - EncodingError: If the word cannot be encoded by the configured KeyEncoder.
        - WordPredictionServiceError: If persistence fails or runtime state cannot be
        synchronized after persistence.
        """
        self._ensure_hydrated()

        # Validate early at boundary, let domain/input errors bubble
        new_word = NewWord(word, frequency=0, source=source)
        index_sequence = self._key_encoder.encode(new_word.word)

        # Persist in repo first
        try:
            record = self._word_repository.add_word(new_word)
        except RepositoryError as e:
            raise WordPredictionServiceError(f'Failed to persist word {word!r}') from e

        # rollback flags (help rollback in-memory mutations)
        store_added = False
        index_added = False
        rollback_failed = False

        # Sync in-memory data structures
        try:
            self._word_store.add_record(record)
            store_added = True

            self._completion_index.insert(record.word_id, index_sequence)
            index_added = True

            return record

        except (WordStoreError, CompletionIndexError) as e:
            # rollback index if it was updated
            if index_added:
                try:
                    self._completion_index.delete(record.word_id, index_sequence)
                except CompletionIndexError:
                    rollback_failed = True

            # rollback store if it was updated
            if store_added:
                try:
                    self._word_store.remove_record(record.word_id)
                except WordStoreError:
                    rollback_failed = True

            # rollback repo
            try:
                self._word_repository.remove_word(record.word_id)
            except RepositoryError:
                rollback_failed = True

            # when rollback fails service needs to be rehydrated
            if rollback_failed:
                self._is_hydrated = False

            raise WordPredictionServiceError(
                f'Failed to synchronize runtime state after adding word {record.word!r}'
            ) from e

    def record_selection(self, word_id: WordId) -> None:
        """
        Record selection of an existing word by incrementing its frequency.

        This method performs the following steps:
        1. Retrieves the current word record from the in-memory store.
        2. Encodes the word to locate its path in the completion index.
        3. Persists the incremented frequency in the repository (source of truth).
        4. Updates the in-memory WordStore.
        5. Refreshes ranking summaries in the completion index.

        The operation is designed to maintain consistency across persistence and
        in-memory structures:
        - If persistence fails, no changes are made.
        - If in-memory synchronization fails after persistence, a best-effort rollback
        is performed to restore the previous state.
        - If rollback itself fails, the service is marked as not hydrated and must be
        rehydrated before further use.

        Args:
        - word_id: Identifier of the selected word.

        Raises:
        - WordPredictionServiceError: If the service is not hydrated, if the word cannot
        be resolved from runtime state, if persistence fails, or if runtime
        synchronization fails and rollback cannot be guaranteed.
        """
        self._ensure_hydrated()

        try:
            record = self._word_store.get_record(word_id)
            index_sequence = self._key_encoder.encode(record.word)
        except (WordStoreError, EncodingError) as e:
            raise WordPredictionServiceError(f'Failed to prepare selection update for word_id {word_id.value!r}') from e

        old_frequency = record.frequency
        new_frequency = old_frequency + 1

        # Persist in repo first
        try:
            self._word_repository.update_frequency(word_id, new_frequency)
        except RepositoryError as e:
            raise WordPredictionServiceError(f'Failed to persist new frequency for word_id {word_id.value!r}') from e

        # rollback flags
        store_updated = False
        rollback_failed = False

        try:
            self._word_store.update_frequency(word_id, new_frequency)
            store_updated = True
            self._completion_index.refresh_index(index_sequence)

        except (WordStoreError, CompletionIndexError) as e:
            # rollback repo first (source of truth)
            try:
                self._word_repository.update_frequency(word_id, old_frequency)
            except RepositoryError:
                rollback_failed = True

            # rollback store if it was updated
            if store_updated:
                try:
                    self._word_store.update_frequency(word_id, old_frequency)
                except WordStoreError:
                    rollback_failed = True

            # refresh index to reflect restored state
            try:
                self._completion_index.refresh_index(index_sequence)
            except CompletionIndexError:
                rollback_failed = True

            if rollback_failed:
                self._is_hydrated = False

            raise WordPredictionServiceError(f'Failed to synchronize runtime state updating {record.word!r}') from e

    def get_word(self, word_id: WordId) -> Word | None:
        """
        Return the word associated with a given WordId from the in-memory store.

        This is a query operation and does not modify system state. The method reads
        exclusively from the in-memory WordStore and does not query the underlying
        repository. As such, results reflect the current hydrated runtime state.

        Args:
        - word_id: Identifier of the word to retrieve.

        Returns:
        - Word | None: The word if present in the runtime store, or None if not found.

        Raises:
        - WordPredictionServiceError: If the service has not been hydrated and cannot
        safely access runtime state, or if an internal runtime state inconsistency is
        detected. In such cases the service is marked as not hydrated and must be
        rehydrated before further use.
        """
        self._ensure_hydrated()
        if word_id not in self._word_store:
            return None
        try:
            return self._word_store.get_word(word_id)
        except WordStoreError as e:
            self._is_hydrated = False
            raise WordPredictionServiceError(
                f'Internal inconsistency detected while retrieving word_id {word_id.value!r}'
            ) from e

    def get_candidates_by_keys(self, keys: Iterable[IndexKey]) -> list[CandidateWord]:
        """
        Return ranked candidate words for a sequence of index keys.

        This method validates the provided keys using the configured KeyEncoder and
        queries the completion index using the resulting encoded key sequence.
        Results are derived from the current hydrated in-memory state.

        Args:
        - keys: Iterable of index keys representing user input.

        Returns:
        - list[CandidateWord]: Ranked candidate words matching the given key sequence.
        Returns an empty list if no candidates are found.

        Raises:
        - EncodingError: If any key is invalid for the configured encoder.
        - WordPredictionServiceError: If the service is not hydrated or if an internal
        inconsistency is detected while querying the completion index. In such cases,
        the service is marked as not hydrated and must be rehydrated before further use.
        """
        self._ensure_hydrated()

        # boundary/domain validation, let errors bubble
        index_key_sequence = self._key_encoder.validate_keys(keys)

        # get candidate word Ids and transform to CandidateWord value objects
        return self._get_candidates_by_sequence(index_key_sequence)

    def get_candidates_by_word(self, word: Word) -> list[CandidateWord]:
        """
        Return ranked candidate words for a given word/word-stem.

        This method validates and encodes the provided word using the configured KeyEncoder.
        It queries the completion index using the resulting encoded key sequence.
        Results are derived from the current hydrated in-memory state.

        Args:
        - word: A string representing a word or word-stem

        Returns:
        - list[CandidateWord]: Ranked candidate words matching the encoded key sequence
        of the given word/word-stem. Returns an empty list if no candidates are found.

        Raises:
        - EncodingError: If any character in word is invalid for the configured encoder;
        invalid => character does not map to a key in the encoders index key space.

        - WordPredictionServiceError: If the service is not hydrated or if an internal
        inconsistency is detected while querying the in-memory completion index or word store.
        In such cases the service is marked as not hydrated and must be rehydrated before
        further use.
        """

        self._ensure_hydrated()

        # boundary/domain validation, let errors bubble
        index_key_sequence = self._key_encoder.encode(word)

        # get candidate word Ids and transform to CandidateWord value objects
        return self._get_candidates_by_sequence(index_key_sequence)

    def contains_word(self, word: Word) -> bool:
        """
        Return True if a word exists in the current system state.

        This method validates and normalizes the input word, then queries the
        repository to determine if the word exists in persistent storage.
        If a record is found, the method verifies that the corresponding WordId
        is present in the hydrated in-memory WordStore.

        The repository is queried because the WordStore does not provide a
        reverse lookup by word text. If such a lookup were available, this method
        could rely solely on the in-memory store, consistent with other query
        methods in the service.

        Args:
        - word: Raw word input.

        Returns:
        - bool: True if the word exists, otherwise False.

        Raises:
        - TypeError, ValueError: If the input word is invalid (domain validation).
        - WordPredictionServiceError: If the service is not hydrated, if the
        repository cannot be queried, or if persisted and in-memory state are
        inconsistent. If an inconsistency is detected, the service is marked as
        not hydrated and must be rehydrated before further use.
        """
        self._ensure_hydrated()

        # delegate to domain helpers for normalisaton/validation, let domain errors bubble
        normalised_word = self._normalise_and_validate_word(word)

        try:
            record = self._word_repository.get_by_word(normalised_word)
        except RepositoryError as e:
            raise WordPredictionServiceError(
                f'Failed while checking existence of {word!r} in persistent storage'
            ) from e

        if record is None:
            return False

        if record.word_id not in self._word_store:
            # Critical error, implies runtime inconsistency and violates the service invariant.
            # Mark service as not hydrated to force rehydration.

            self._is_hydrated = False
            raise WordPredictionServiceError(
                f'Inconsistent runtime state for word {record.word!r}; '
                f'word_id {record.word_id.value!r} exists in repository but not in WordStore'
            )

        return True

    # -------- Internal Helpers ----------
    def _ensure_hydrated(self) -> None:
        if not self._is_hydrated:
            raise WordPredictionServiceError('Service is not hyrdated, call hydrate() endpoint')

    @staticmethod
    def _normalise_and_validate_word(word: str) -> str:
        """
        Normalises and validates a given word and returns transformed string.

        Delegates to domain helpers for word normalisation/validation rules.

        Args:
        - word: Raw word input.

        Returns:
        - str: The normalised, validated word

        Raises:
        - TypeError: If word is not a string.
        - ValueError: If word is an empty string or contains non-alphabetic characters.
        """

        normalised_word = normalise_word(word)
        validate_word(normalised_word)
        return normalised_word

    def _get_candidates_by_sequence(self, index_key_sequence: EncodedIndexKeySequence) -> list[CandidateWord]:
        """
        Retrieve ranked candidate words for a validated encoded key sequence.

        This method queries the in-memory completion index to obtain ranked
        candidate WordIds, then resolves each WordId to its corresponding word
        using the in-memory WordStore.

        This method assumes:
        - The service is hydrated.
        - The provided key sequence has already been validated at the service boundary.

        Returns:
        - list[CandidateWord]: Ranked candidate words matching the given key sequence.
        Returns an empty list if no candidates are found.

        Raises:
        - WordPredictionServiceError:
            - If the completion index returns invalid data (CompletionIndexError).
            - If a candidate WordId cannot be resolved in the WordStore (WordStoreError).

        Notes:
        - Any inconsistency between the CompletionIndex and WordStore is treated as a
        critical runtime invariant violation. In such cases, the service is marked
        as not hydrated and must be rehydrated before further use.
        """

        try:
            # get candidates from the completion index
            candidate_word_ids = self._completion_index.get_ranked_candidates(index_key_sequence)
        except CompletionIndexError as e:
            # inconsistent internal state
            self._is_hydrated = False
            raise WordPredictionServiceError(
                'Inconsistent runtime state detected while querying completion index: '
                f'key_sequence {index_key_sequence!r}'
            ) from e

        # transform from candidate WordIds to CandidateWord objects
        # DESIGN: consider refactoring to a helper method if there is a clear use case.
        candidates: list[CandidateWord] = []
        for word_id in candidate_word_ids:
            try:
                candidates.append(CandidateWord(word_id, self._word_store.get_word(word_id)))
            except WordStoreError as e:
                # inconsistent internal state
                self._is_hydrated = False
                raise WordPredictionServiceError(
                    f'Inconsistent runtime state detected while querying word store for word_id {word_id.value!r}'
                ) from e

        return candidates
