from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
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


class WordResponse(BaseModel):
    """Response payload representing a word resource."""

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


@app.get('/', response_class=HTMLResponse)
def demo_ui() -> HTMLResponse:
    """
    Serve a minimal browser-based demo UI for the predictive text service.

    This endpoint returns a lightweight HTML page with embedded JavaScript that
    demonstrates the core capabilities of the system:

    - Real-time word prediction via `/predict/text`
    - Word insertion into a textarea editor
    - Selection tracking via `/words/{word_id}/select` to update frequency and ranking

    Design Notes:
    - The UI is intentionally minimal and self-contained (no build step, no frameworks).
    - All editor state is managed client-side in the browser.
    - The backend remains focused on prediction, persistence, and ranking logic.
    - The UI extracts the current word at the cursor and queries the backend for suggestions.
    - Selecting a suggestion updates both the UI and backend state, enabling a live personalization loop.

    Performance Considerations:
    - The frontend uses a simple debounce to limit request frequency.
    - The backend remains fast due to the in-memory completion index (Trie),
    avoiding database lookups on each prediction request.

    This endpoint is designed for demonstration and exploratory use, providing
    a tangible interface to interact with the system without introducing the
    complexity of a full frontend architecture.
    """

    return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Predictive Text Demo</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                    max-width: 760px;
                    margin: 48px auto;
                    padding: 0 20px;
                    background: #fafafa;
                    color: #222;
                }

                .card {
                    background: white;
                    border: 1px solid #e5e5e5;
                    border-radius: 14px;
                    padding: 24px;
                    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
                }

                h1 {
                    margin-top: 0;
                    margin-bottom: 8px;
                    font-size: 28px;
                }

                .subtitle {
                    margin-top: 0;
                    color: #666;
                    line-height: 1.5;
                }

                textarea {
                    width: 100%;
                    height: 140px;
                    box-sizing: border-box;
                    margin-top: 16px;
                    padding: 14px;
                    font-size: 16px;
                    line-height: 1.5;
                    border: 1px solid #ccc;
                    border-radius: 10px;
                    resize: vertical;
                }

                textarea:focus {
                    outline: none;
                    border-color: #555;
                    box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.08);
                }

                .section-title {
                    margin-top: 24px;
                    margin-bottom: 8px;
                    font-size: 16px;
                    font-weight: 700;
                }

                .hint {
                    margin-top: 0;
                    margin-bottom: 10px;
                    color: #777;
                    font-size: 14px;
                }

                #suggestions {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 8px;
                    min-height: 42px;
                }

                .suggestion {
                    cursor: pointer;
                    border: 1px solid #ddd;
                    border-radius: 999px;
                    padding: 8px 12px;
                    background: #f7f7f7;
                    font-size: 15px;
                    transition: transform 0.08s ease, background 0.12s ease, border-color 0.12s ease;
                }

                .suggestion:hover {
                    background: #eeeeee;
                    border-color: #cfcfcf;
                    transform: translateY(-1px);
                }

                .suggestion:active {
                    transform: translateY(0);
                }

                .empty {
                    color: #999;
                    font-size: 14px;
                    padding: 8px 0;
                }

                #status {
                    margin-top: 18px;
                    padding: 10px 12px;
                    border-radius: 8px;
                    background: #f2f2f2;
                    color: #555;
                    font-size: 14px;
                    min-height: 20px;
                }

                .status-success {
                    background: #eef8ef !important;
                    color: #256b2c !important;
                }

                .status-error {
                    background: #fdeeee !important;
                    color: #8a2525 !important;
                }

                .footer-note {
                    margin-top: 18px;
                    color: #777;
                    font-size: 13px;
                    line-height: 1.5;
                }

                code {
                    background: #f1f1f1;
                    padding: 2px 5px;
                    border-radius: 4px;
                }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Predictive Text Demo</h1>
                <p class="subtitle">
                    Type a message below. The app predicts the current word using the backend
                    prediction service and an in-memory completion index.
                </p>

                <textarea id="editor" placeholder="Start typing a message..."></textarea>

                <div class="section-title">Suggestions</div>
                <p class="hint">Click a suggestion to insert it and record the selection.</p>
                <div id="suggestions">
                    <div class="empty">Start typing to see predictions.</div>
                </div>

                <div id="status">Ready.</div>

                <p class="footer-note">
                    Demo behaviour: selecting a suggestion calls <code>POST /words/{word_id}/select</code>,
                    which increments frequency and refreshes ranking state.
                </p>
            </div>

        <script>
        const editor = document.getElementById("editor");
        const suggestionsDiv = document.getElementById("suggestions");
        const statusDiv = document.getElementById("status");

        let timeout = null;
        let latestRequestId = 0;

        editor.addEventListener("input", () => {
            clearTimeout(timeout);
            timeout = setTimeout(fetchSuggestions, 180);
        });

        editor.addEventListener("click", () => {
            clearTimeout(timeout);
            timeout = setTimeout(fetchSuggestions, 180);
        });

        editor.addEventListener("keyup", () => {
            clearTimeout(timeout);
            timeout = setTimeout(fetchSuggestions, 180);
        });

        function setStatus(message, kind = "neutral") {
            statusDiv.textContent = message;
            statusDiv.classList.remove("status-success", "status-error");

            if (kind === "success") {
                statusDiv.classList.add("status-success");
            } else if (kind === "error") {
                statusDiv.classList.add("status-error");
            }
        }

        function getCurrentWordInfo() {
            const text = editor.value;
            const cursor = editor.selectionStart;

            const before = text.slice(0, cursor);
            const match = before.match(/([a-zA-Z]+)$/);

            if (!match) {
                return null;
            }

            const word = match[1];
            const start = cursor - word.length;

            return {
                word,
                start,
                end: cursor
            };
        }

        function renderEmpty(message) {
            suggestionsDiv.innerHTML = "";
            const empty = document.createElement("div");
            empty.className = "empty";
            empty.textContent = message;
            suggestionsDiv.appendChild(empty);
        }

        async function fetchSuggestions() {
            const requestId = ++latestRequestId;
            const current = getCurrentWordInfo();

            if (!current || current.word.length === 0) {
                renderEmpty("Start typing a word to see predictions.");
                return;
            }

            try {
                const res = await fetch(`/predict/text?text=${encodeURIComponent(current.word)}`);

                if (!res.ok) {
                    renderEmpty("No suggestions available.");
                    return;
                }

                const data = await res.json();

                if (requestId !== latestRequestId) {
                    return;
                }

                suggestionsDiv.innerHTML = "";

                if (!data.candidates || data.candidates.length === 0) {
                    renderEmpty(`No suggestions for "${current.word}".`);
                    return;
                }

                data.candidates.forEach(candidate => {
                    const button = document.createElement("button");
                    button.className = "suggestion";
                    button.type = "button";
                    button.textContent = candidate.word;
                    button.title = `Insert "${candidate.word}"`;

                    button.onclick = () => applySuggestion(candidate);

                    suggestionsDiv.appendChild(button);
                });

            } catch (err) {
                renderEmpty("Could not fetch suggestions.");
                setStatus("Prediction request failed.", "error");
            }
        }

        async function applySuggestion(candidate) {
            const current = getCurrentWordInfo();

            if (!current) {
                return;
            }

            const text = editor.value;
            const before = text.slice(0, current.start);
            const after = text.slice(current.end);

            editor.value = before + candidate.word + after;

            const newCursor = current.start + candidate.word.length;
            editor.focus();
            editor.setSelectionRange(newCursor, newCursor);

            try {
                const res = await fetch(`/words/${candidate.word_id}/select`, {
                    method: "POST"
                });

                if (!res.ok) {
                    setStatus(`Inserted "${candidate.word}", but selection update failed.`, "error");
                    return;
                }

                setStatus(`Inserted "${candidate.word}" and recorded selection.`, "success");
                await fetchSuggestions();

            } catch (err) {
                setStatus(`Inserted "${candidate.word}", but selection update failed.`, "error");
            }
        }
        </script>
        </body>
        </html>
            """)


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


@app.get('/words/{word_id}', response_model=WordResponse)
def get_word(word_id: int, request: Request) -> WordResponse:
    """Retrieve a word resource by identifier."""
    service = _get_service(request)

    try:
        record = service.get_word(WordId(word_id))

        if record is None:
            raise HTTPException(status_code=404, detail='Word not found')

    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    except WordPredictionServiceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return WordResponse(
        word_id=record.word_id.value,
        word=record.word,
        frequency=record.frequency,
        source=record.source,
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
