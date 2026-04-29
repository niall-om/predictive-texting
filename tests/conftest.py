"""
Shared pytest fixtures for the predictive_texting test suite.

This module defines reusable fixtures that provide isolated runtime
environments for tests, including:

- Temporary filesystem paths (via pytest's built-in tmp_path fixture)
- Test-specific configuration objects
- Fully bootstrapped WordPredictionService instances

Fixtures are used to ensure tests are deterministic, isolated, and
do not share state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from predictive_texting.application.word_prediction.config import RankingPolicyType, WordPredictionConfig
from predictive_texting.domain.encoding.languages import Language
from predictive_texting.domain.encoding.schemes import EncodingScheme
from predictive_texting.infrastructure.bootstrap.word_prediction import bootstrap_word_prediction_service

# NOTE:
# tmp_path is a built-in pytest fixture (not from the standard library).
# It provides a unique temporary directory per test, ensuring filesystem isolation.


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """
    Provide a temporary SQLite database path for a test.

    Uses pytest's built-in `tmp_path` fixture, which creates a unique
    temporary directory per test invocation.

    This ensures:
    - Each test gets its own isolated database file
    - No shared state between tests
    - Safe parallel execution

    Args:
    - tmp_path: pytest-provided temporary directory (not part of stdlib)

    Returns:
    - Path: File path to a test-specific SQLite database
    """

    # tmp_path is a pytest fixture that provides a unique temporary
    # directory per test. We create a database file inside it.
    return tmp_path / 'test_predictive_texting.sqlite3'


@pytest.fixture
def word_prediction_config(db_path: Path) -> WordPredictionConfig:
    """
    Provide a WordPredictionConfig configured for testing.

    This fixture builds a configuration object that points to the
    test-specific SQLite database and uses deterministic settings
    for encoding and ranking.

    Depends on:
    - db_path: ensures each config uses an isolated database

    Returns:
    - WordPredictionConfig: configuration used to bootstrap the service
    """

    return WordPredictionConfig(
        db_path=db_path,
        language=Language.ENGLISH,
        encoding_scheme=EncodingScheme.QWERTY,
        ranking_policy_type=RankingPolicyType.FREQUENCY,
        k=10,
    )


@pytest.fixture
def word_prediction_service(word_prediction_config: WordPredictionConfig):
    """
    Provide a fully bootstrapped WordPredictionService for testing.

    This fixture initialises the complete application stack, including:
    - SQLite database and schema
    - Repository layer
    - In-memory WordStore
    - CompletionIndex (Trie)
    - Hydrated WordPredictionService

    The returned service is ready for use in tests without additional setup.

    Depends on:
    - word_prediction_config: provides test-specific configuration

    Returns:
    - WordPredictionService: fully initialised service instance
    """

    return bootstrap_word_prediction_service(word_prediction_config)
