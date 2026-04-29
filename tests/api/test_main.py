"""
End-to-end tests for the FastAPI application.

These tests exercise the API layer using FastAPI's TestClient,
verifying the full request lifecycle:

- HTTP request handling
- Application service orchestration
- Persistence and in-memory state updates

Tests in this module simulate real client interactions with the system.

API tests use monkeypatch to override application configuration.

This ensures that each test runs against an isolated temporary database
rather than any real or shared environment.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from predictive_texting.api import main as api_main
from predictive_texting.application.word_prediction.config import RankingPolicyType, WordPredictionConfig
from predictive_texting.domain.encoding.languages import Language
from predictive_texting.domain.encoding.schemes import EncodingScheme


def _build_test_config(tmp_path: Path) -> WordPredictionConfig:
    return WordPredictionConfig(
        db_path=tmp_path / 'api_test_predictive_texting.sqlite3',
        language=Language.ENGLISH,
        encoding_scheme=EncodingScheme.QWERTY,
        ranking_policy_type=RankingPolicyType.FREQUENCY,
        k=10,
    )


def test_health_endpoint(tmp_path: Path, monkeypatch) -> None:
    """
    Verify that the health endpoint returns a successful response.

    This test ensures:
    - The API is running
    - The application is correctly initialised
    - Basic liveness checks pass
    """

    # Replace the real `_build_config` function with a test-specific version.
    #
    # Why:
    # - The app normally builds its own config (e.g. real DB path)
    # - In tests, we want a temporary database (tmp_path)
    #
    # monkeypatch ensures this override only applies during this test.
    monkeypatch.setattr(api_main, '_build_config', lambda: _build_test_config(tmp_path))

    with TestClient(api_main.app) as client:
        response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_add_word_predict_select_and_get_word_flow(tmp_path: Path, monkeypatch) -> None:
    """
    Verify the full end-to-end flow of the predictive text system.

    This test covers:
    - Adding a new word via the API
    - Retrieving predictions that include the new word
    - Recording a selection event to update frequency
    - Fetching the word resource to confirm the updated state

    This test acts as a high-level integration test of the system.
    """

    monkeypatch.setattr(api_main, '_build_config', lambda: _build_test_config(tmp_path))

    with TestClient(api_main.app) as client:
        add_response = client.post('/words', json={'word': 'zzfoobar'})

        assert add_response.status_code == 200

        added_word = add_response.json()
        word_id = added_word['word_id']

        predict_response = client.get('/predict/text', params={'text': 'zzfoo'})

        assert predict_response.status_code == 200
        candidates = predict_response.json()['candidates']
        assert any(candidate['word'] == 'zzfoobar' for candidate in candidates)

        select_response = client.post(f'/words/{word_id}/select')

        assert select_response.status_code == 200

        get_response = client.get(f'/words/{word_id}')

        assert get_response.status_code == 200

        word_resource = get_response.json()
        assert word_resource['word'] == 'zzfoobar'
        assert word_resource['frequency'] == 1
        assert word_resource['source'] == 'user'
