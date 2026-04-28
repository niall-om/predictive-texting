from __future__ import annotations

from .base import AppError


class WordPredictionServiceError(AppError):
    """Raised when a predictive text service operation fails."""

    ...


class WordPredictionConfigError(WordPredictionServiceError):
    """Raised when a config for Word Prediction Service is invalid."""

    ...
