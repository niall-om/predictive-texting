"""
Core domain types for the lexicon (word storage and validation).

Defines value objects and validation logic for words, identifiers, frequencies,
and word creation. These types enforce domain constraints before persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

# WordId = NewType('WordId', int)
Word: TypeAlias = str


class WordSource(str, Enum):
    SEED = 'seed'
    USER = 'user'


@dataclass(frozen=True, slots=True)
class WordId:
    """Unique identifier for a persisted word."""

    value: int

    def __post_init__(self) -> None:
        if type(self.value) is not int:
            raise TypeError(f'Invalid WordId type; expected int, got {type(self.value)!r}')
        if self.value < 1:
            raise ValueError(f'WordId must be >= 1; got {self.value!r}')


@dataclass(frozen=True, slots=True)
class WordRecord:
    """Represents a persisted word record."""

    word_id: WordId
    word: Word
    frequency: int
    source: WordSource

    def __post_init__(self) -> None:
        if not isinstance(self.word_id, WordId):
            raise TypeError(f'Invalid WordId type; expected WordId, got {type(self.word_id)!r}')

        normalised_word = normalise_word(self.word)
        object.__setattr__(self, 'word', normalised_word)
        validate_word(self.word)
        validate_frequency(self.frequency)
        validate_source(self.source)


@dataclass(frozen=True, slots=True)
class NewWord:
    """
    Domain object representing a word to be created.

    Encapsulates validation for:
    - word text
    - frequency
    - source

    Used by repositories to persist new word entries.
    """

    word: Word
    frequency: int
    source: WordSource

    def __post_init__(self) -> None:
        normalised_word = normalise_word(self.word)
        object.__setattr__(self, 'word', normalised_word)
        validate_word(self.word)
        validate_frequency(self.frequency)
        validate_source(self.source)


# ------- Public Normalisation / Input Validation Helpers


def normalise_word(word: Word) -> str:
    """
    Normalise a word into its canonical form.

    Applies standard transformations (e.g. trimming whitespace, converting to
    lowercase) so that words are stored and compared consistently.

    Args:
        word: Raw input word.

    Returns:
        Normalised word string.
    """
    if not isinstance(word, str):
        raise TypeError(f'Invalid word type; expected `str`, got {type(word)!r}')
    return word.strip().lower()


def validate_word_id(word_id: WordId) -> None:
    """
    Validate that a word identifier is valid.

    Ensures the identifier is a positive integer suitable for use as a primary
    key in the lexicon.

    Raises:
        ValueError: If the identifier is invalid.
    """
    if not isinstance(word_id, WordId):
        raise TypeError(f'Invalid word_id type; expected `int`, got {type(word_id)!r}')
    if word_id.value < 1:
        raise ValueError(f'word_id must be >= 1; got {word_id!r}')


def validate_word(word: Word) -> None:
    """
    Validate that a word meets domain constraints.

    Ensures the word contains only valid alphabetic characters and is not empty.

    Raises:
        ValueError: If validation fails.
    """
    # runtime type checking handled by _normalise_word()
    if not word:
        raise ValueError('Word must be non-empty')
    if not word.isalpha():
        raise ValueError(f'Word must contain only alphabetic characters; got {word!r}')


def validate_frequency(frequency: int) -> None:
    """
    Validate frequency value.

    NOTE:
    Frequency is currently represented as a primitive `int`.
    This means validation may be repeated across store/repository/service layers.
    If validation logic becomes more complex or starts to diverge,
    consider promoting frequency to a dedicated value object.
    """

    if type(frequency) is not int:
        raise TypeError(f'Invalid frequency type; expected `int`, got {type(frequency)!r}')
    if frequency < 0:
        raise ValueError(f'Frequency must be >= 0, got {frequency!r}')


def validate_source(source: WordSource) -> None:
    if not isinstance(source, WordSource):
        raise TypeError(f'Invalid source type; expected `WordSource`, got {type(source)!r}')
