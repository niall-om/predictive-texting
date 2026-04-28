from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from predictive_texting.application.word_prediction.config import RankingPolicyType, WordPredictionConfig
from predictive_texting.application.word_prediction.dtos import CandidateWord
from predictive_texting.application.word_prediction.service import WordPredictionService
from predictive_texting.domain.encoding.languages import Language
from predictive_texting.domain.encoding.schemes import EncodingScheme
from predictive_texting.domain.encoding.types import IndexKey
from predictive_texting.domain.lexicon.types import WordId, WordSource
from predictive_texting.exceptions.application import WordPredictionServiceError
from predictive_texting.exceptions.domain import EncodingError
from predictive_texting.exceptions.infrastructure import BootstrapError
from predictive_texting.infrastructure.bootstrap.word_prediction import bootstrap_word_prediction_service


# -----------------------------------------------------------------------------
# Request / Response Models
# -----------------------------------------------------------------------------
class AddWordRequest(BaseModel):
    """
    Request payload for creating a new word.

    Represents user-provided input that will be validated, normalised,
    and persisted by the word prediction service.
    """

    word: str


class AddWordResponse(BaseModel):
    """
    Response payload returned after successfully adding a new word.

    Includes the persisted word identifier and associated metadata.
    """

    word_id: int
    word: str
    frequency: int
    source: str


class CandidateResponse(BaseModel):
    """API response model for a single candidate word."""

    word_id: int
    word: str


class PredictionResponse(BaseModel):
    """API response model for prediction results."""

    query: str
    candidates: list[CandidateResponse]


class RecordSelectionResponse(BaseModel):
    """
    Response payload for recording a word selection.

    Confirms that the selection event has been processed and applied.
    """

    status: str
    word_id: int


class HealthResponse(BaseModel):
    """API response model for health-check status."""

    status: str


# -----------------------------------------------------------------------------
# Configuration / Bootstrap
# -----------------------------------------------------------------------------


def _build_config() -> WordPredictionConfig:
    """
    Build the demo configuration for the word prediction service.

    The demo currently uses English with QWERTY encoding so `/predict/text`
    behaves like standard prefix-based autocomplete.
    """
    data_dir = Path.cwd() / 'data'
    data_dir.mkdir(exist_ok=True)

    return WordPredictionConfig(
        db_path=data_dir / 'predictive_texting.sqlite3',
        language=Language.ENGLISH,
        encoding_scheme=EncodingScheme.QWERTY,  # default to QWERTY encoding for Demo
        ranking_policy_type=RankingPolicyType.FREQUENCY,
        k=10,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage FastAPI application startup and shutdown.

    On startup, bootstrap and hydrate the word prediction service once, then
    store it on `app.state` so all requests can reuse the same in-memory index.

    Code before `yield` runs during application startup.
    Code after `yield` runs during application shutdown.
    """

    # Note:
    # FastAPI uses an async context manager for application lifecycle.
    # The code before yield runs at startup to initialise shared state, and the code after yield runs at shutdown.
    # Used to bootstrap and store the prediction service once per process.
    # Enables pattern: Initialize once → reuse across requests

    # startup code: build word prediction service and shared in-memory data structures
    try:
        app.state.word_prediction_service = bootstrap_word_prediction_service(_build_config())
    except BootstrapError as e:
        raise RuntimeError('Failed to bootstrap word prediction service') from e

    yield
    # Shutdown cleanup hook.
    # Nothing required yet, but this is where we would close connections/resources.


app = FastAPI(
    title='Predictive Text Service',
    description='Predictive text service supporting pluggable encoding schemes (T9, QWERTY) with in-memory indexing.',
    version='0.1.0',
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# Internal Helpers
# -----------------------------------------------------------------------------


def _get_service(request: Request) -> WordPredictionService:
    """
    Retrieve the shared word prediction service from FastAPI app state.

    The service is created once during application startup and reused across
    requests.
    """
    return cast(WordPredictionService, request.app.state.word_prediction_service)


def _candidate_to_response(candidate: CandidateWord) -> CandidateResponse:
    """Convert an application-layer candidate DTO into an API response model."""
    return CandidateResponse(
        word_id=candidate.word_id.value,
        word=candidate.word,
    )


def _candidates_to_response(candidates: list[CandidateWord]) -> list[CandidateResponse]:
    """Convert candidate DTOs into API response models."""
    return [_candidate_to_response(candidate) for candidate in candidates]


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@app.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    """Return basic service health status."""
    return HealthResponse(status='ok')


@app.get('/predict/keys', response_model=PredictionResponse)
def predict_by_keys(keys: str, request: Request) -> PredictionResponse:
    """
    Predict candidate words from a sequence of encoded index keys.

    This endpoint exposes the lower-level encoded key interface used internally by
    the completion index. The meaning of each key depends on the configured encoding
    scheme.

    For the current QWERTY demo configuration, letters map to integer keys:
        a -> 1, b -> 2, ..., z -> 26

    Example:
        keys = "12" represents the encoded prefix "ab".
    """

    service = _get_service(request)

    try:
        index_keys = [IndexKey(int(char)) for char in keys]
        candidates = service.get_candidates_by_keys(index_keys)

    except ValueError as e:
        raise HTTPException(status_code=400, detail='keys must contain digits only') from e

    except EncodingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    except WordPredictionServiceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return PredictionResponse(
        query=keys,
        candidates=_candidates_to_response(candidates),
    )


@app.get('/predict/text', response_model=PredictionResponse)
def predict_by_text(text: str, request: Request) -> PredictionResponse:
    """
    Predict candidate words from text input using the configured encoding.

    The input text is encoded into index keys using the configured encoding scheme,
    then matched against the in-memory completion index.

    The demo currently uses English QWERTY encoding, where each character maps to a
    unique integer key. This makes the endpoint behave like standard prefix-based
    autocomplete.

    Example:
        text = "he" -> ["he", "her", "hey", "head", ...]
    """

    service = _get_service(request)

    try:
        candidates = service.get_candidates_by_word(text)

    except EncodingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    except WordPredictionServiceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return PredictionResponse(
        query=text,
        candidates=_candidates_to_response(candidates),
    )


@app.post('/words', response_model=AddWordResponse)
def add_word(payload: AddWordRequest, request: Request) -> AddWordResponse:
    """
    Add a new user-provided word to the prediction system.

    The service persists the word and synchronises the in-memory WordStore and
    CompletionIndex so the word is immediately available for predictions.
    """
    service = _get_service(request)

    try:
        record = service.add_word(payload.word, source=WordSource.USER)

    except (TypeError, ValueError, EncodingError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    except WordPredictionServiceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return AddWordResponse(
        word_id=record.word_id.value,
        word=record.word,
        frequency=record.frequency,
        source=record.source,
    )


@app.post('/words/{word_id}/select', response_model=RecordSelectionResponse)
def record_selection(word_id: int, request: Request) -> RecordSelectionResponse:
    """
    Record that a candidate word was selected by the user.

    This increments the word frequency and refreshes the in-memory ranking data,
    allowing repeated selections to influence future prediction ordering.
    """
    service = _get_service(request)

    try:
        service.record_selection(WordId(word_id))

    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    except WordPredictionServiceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return RecordSelectionResponse(status='ok', word_id=word_id)
