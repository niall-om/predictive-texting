"""
Tests for the WordPredictionService application layer.

These tests validate the core orchestration logic of the system, including:

- Adding new words and synchronizing runtime state
- Retrieving predictions from the in-memory completion index
- Updating frequency via selection events

The service is tested as a unit of business logic, relying on fully
bootstrapped in-memory and persistence components.
"""

from __future__ import annotations

from predictive_texting.application.word_prediction.service import WordPredictionService
from predictive_texting.domain.lexicon.types import WordSource


def test_service_add_word_makes_word_available_for_prediction(
    word_prediction_service: WordPredictionService,
) -> None:
    """
    Verify that adding a word makes it available for prediction queries.

    This test ensures:
    - Words added via the service are persisted
    - In-memory structures (WordStore and CompletionIndex) are updated
    - The word appears in prediction results for matching prefixes
    """

    record = word_prediction_service.add_word('zzfoobar', source=WordSource.USER)

    candidates = word_prediction_service.get_candidates_by_word('zzfoo')

    assert any(candidate.word_id == record.word_id for candidate in candidates)
    assert any(candidate.word == 'zzfoobar' for candidate in candidates)


def test_service_record_selection_increments_frequency(
    word_prediction_service: WordPredictionService,
) -> None:
    """
    Verify that recording a selection increments word frequency.

    This test ensures:
    - Frequency is incremented in persistent storage
    - In-memory WordStore reflects the updated value
    - The service remains in a consistent hydrated state
    """

    record = word_prediction_service.add_word('zzfoobar', source=WordSource.USER)

    word_prediction_service.record_selection(record.word_id)

    updated = word_prediction_service.get_word(record.word_id)

    assert updated is not None
    assert updated.frequency == 1
