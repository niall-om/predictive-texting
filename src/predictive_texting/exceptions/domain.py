from .base import AppError


# ---------------- Encoding Domain Errors -------------------
class EncodingError(AppError):
    """Base exception for Encoding domain errors."""

    ...


# ---------------- Lexicon Domain Errors -------------------
class LexiconError(AppError):
    """Base exception for Lexicon domain errors."""

    ...


class WordStoreError(LexiconError):
    """Raised when a WordStore operation violates store invariants."""

    ...


class CompletionIndexError(LexiconError):
    """Raised when a CompletionIndex operation violates index invariants."""

    ...
