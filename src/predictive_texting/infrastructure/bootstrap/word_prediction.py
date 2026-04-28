from __future__ import annotations

from predictive_texting.application.word_prediction.config import RankingPolicyType, WordPredictionConfig
from predictive_texting.application.word_prediction.service import WordPredictionService
from predictive_texting.domain.encoding.encoding_specs import get_encoding_spec
from predictive_texting.domain.encoding.key_encoder import KeyEncoder
from predictive_texting.domain.lexicon.completion_index import RankedCompletionIndex
from predictive_texting.domain.lexicon.types import NewWord, WordSource
from predictive_texting.domain.lexicon.word_store import InMemoryWordStore
from predictive_texting.domain.ranking.frequency_ranking import FrequencyRankingPolicy
from predictive_texting.domain.ranking.protocols import RankingPolicy
from predictive_texting.exceptions.application import WordPredictionConfigError, WordPredictionServiceError
from predictive_texting.exceptions.domain import EncodingError
from predictive_texting.exceptions.infrastructure import BootstrapError, RepositoryError
from predictive_texting.infrastructure.repositories.sqlite_word_repository import SqliteWordRepository

from .database import bootstrap_sqlite_database
from .db.seed_file_registry import load_seed_words


def _build_ranking_policy(
    ranking_policy_type: RankingPolicyType,
    word_store: InMemoryWordStore,
) -> RankingPolicy:
    match ranking_policy_type:
        case RankingPolicyType.FREQUENCY:
            return FrequencyRankingPolicy(word_store)


def bootstrap_word_prediction_service(config: WordPredictionConfig) -> WordPredictionService:
    """
    Build, seed, hydrate, and return a WordPredictionService instance.

    This bootstrapper:
    1. Ensures the SQLite database and schema exist.
    2. Creates the SQLite word repository.
    3. Seeds the repository if it is empty.
    4. Builds the encoder, word store, completion index, ranking policy, and service.
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

        encoding_spec = get_encoding_spec(config.language, config.encoding_scheme)
        key_encoder = KeyEncoder(encoding_spec)

        word_store = InMemoryWordStore()

        ranking_policy = _build_ranking_policy(config.ranking_policy_type, word_store)

        completion_index = RankedCompletionIndex(
            keyspace=key_encoder.index_key_space,
            ranking_policy=ranking_policy,
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
