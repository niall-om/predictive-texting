# connect to DB
# run schema SQL
# create repository
# if repo is empty seed repo
# build encoder, store, completion index
# build service
# hydrate service
# return service

from __future__ import annotations

from ...application.word_prediction.config import WordPredictionConfig
from ...application.word_prediction.service import WordPredictionService
from ...domain.encoding.encoding_specs import get_encoding_spec
from ...domain.encoding.key_encoder import KeyEncoder
from ...domain.lexicon.completion_index import RankedCompletionIndex
from ...domain.lexicon.types import NewWord, WordSource
from ...domain.lexicon.word_store import InMemoryWordStore
from ...exceptions.application import WordPredictionConfigError, WordPredictionServiceError
from ...exceptions.domain import EncodingError
from ...exceptions.infrastructure import BootstrapError, RepositoryError
from ...infrastructure.repositories.sqlite_word_repository import SqliteWordRepository
from .database import bootstrap_sqlite_database
from .db.seed_file_registry import load_seed_words


def bootstrap_word_prediction_service(config: WordPredictionConfig) -> WordPredictionService:
    """
    Build, seed, hydrate, and return a WordPredictionService instance.

    This bootstrapper:
    1. Ensures the SQLite database and schema exist.
    2. Creates the SQLite word repository.
    3. Seeds the repository if it is empty.
    4. Builds the encoder, word store, completion index, and service.
    5. Hydrates the service from persisted repository data.

    Args:
    - config: Validated word prediction service configuration.

    Returns:
    - WordPredictionService: Hydrated service ready for use.

    Raises:
    - BootstrapError: If database setup, seeding, service construction, or
      hydration fails.
    """
    try:
        db_path = bootstrap_sqlite_database(config.db_path)

        repository = SqliteWordRepository(db_path)

        if repository.is_empty():
            seed_words = load_seed_words(config.language)
            repository.seed(NewWord(word, frequency=0, source=WordSource.SEED) for word in seed_words)

        encoding_spec = get_encoding_spec(config.language)
        key_encoder = KeyEncoder(encoding_spec)

        word_store = InMemoryWordStore()

        completion_index = RankedCompletionIndex(
            keyspace=key_encoder.index_key_space,
            ranking_policy=config.ranking_policy,
            k=config.k,
        )

        service = WordPredictionService(
            word_repository=repository,
            word_store=word_store,
            key_encoder=key_encoder,
            completion_index=completion_index,
        )

        service.hydrate()
        return service

    except (
        BootstrapError,
        RepositoryError,
        WordPredictionConfigError,
        WordPredictionServiceError,
        EncodingError,
        TypeError,
        ValueError,
    ) as e:
        raise BootstrapError('Failed to bootstrap word prediction service') from e
