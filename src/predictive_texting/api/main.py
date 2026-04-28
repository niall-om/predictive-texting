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
from predictive_texting.domain.encoding.types import IndexKey
from predictive_texting.exceptions.application import WordPredictionServiceError
from predictive_texting.exceptions.domain import EncodingError
from predictive_texting.exceptions.infrastructure import BootstrapError
from predictive_texting.infrastructure.bootstrap.word_prediction import bootstrap_word_prediction_service

# -----------------------------------------------------------------------------
# Response Models
# -----------------------------------------------------------------------------


class CandidateResponse(BaseModel):
    word_id: int
    word: str


class PredictionResponse(BaseModel):
    query: str
    candidates: list[CandidateResponse]


class HealthResponse(BaseModel):
    status: str


# -----------------------------------------------------------------------------
# Configuration / Bootstrap
# -----------------------------------------------------------------------------


def _build_config() -> WordPredictionConfig:
    data_dir = Path.cwd() / 'data'
    data_dir.mkdir(exist_ok=True)

    return WordPredictionConfig(
        db_path=data_dir / 'predictive_texting.sqlite3',
        language=Language.ENGLISH,
        ranking_policy_type=RankingPolicyType.FREQUENCY,
        k=10,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    FastAPI lifespan hook.

    Code before `yield` runs once at application startup.
    We bootstrap and hydrate the word prediction service here so it can be reused
    across requests without rebuilding the in-memory index each time.

    Code after `yield` would run once at application shutdown.
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
    description='T9-style predictive text demo using FastAPI, SQLite, and a ranked completion index.',
    version='0.1.0',
    lifespan=lifespan,
)

# -----------------------------------------------------------------------------
# Internal Helpers
# -----------------------------------------------------------------------------


def _get_service(request: Request) -> WordPredictionService:
    return cast(WordPredictionService, request.app.state.word_prediction_service)


def _candidate_to_response(candidate: CandidateWord) -> CandidateResponse:
    return CandidateResponse(
        word_id=candidate.word_id.value,
        word=candidate.word,
    )


def _candidates_to_response(candidates: list[CandidateWord]) -> list[CandidateResponse]:
    return [_candidate_to_response(candidate) for candidate in candidates]


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@app.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status='ok')


@app.get('/predict/keys', response_model=PredictionResponse)
def predict_by_keys(keys: str, request: Request) -> PredictionResponse:
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
