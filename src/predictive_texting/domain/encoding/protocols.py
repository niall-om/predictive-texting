from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .key_space import IndexKeySpace
from .types import CharacterSet, EncodedIndexKeySequence, IndexKey


class KeyEncoderProtocol(Protocol):
    def encode(self, word: str) -> EncodedIndexKeySequence:
        """Encode a string into an index key sequence."""
        ...

    def decode(self, index_key: IndexKey) -> CharacterSet:
        """Return all characters mapped to the given index key."""
        ...

    def validate_keys(self, index_keys: Iterable[IndexKey]) -> EncodedIndexKeySequence:
        """
        Validate a sequence of index keys and return it as an EncodedIndexKeySequence.

        Args:
        - index_keys: Iterable of index keys to validate.

        Returns:
        - EncodedIndexKeySequence: Validated key sequence.

        Raises:
        - EncodingError: If any key is not part of this encoder's key space.
        """
        ...

    @property
    def character_set(self) -> CharacterSet:
        """The set of valid characters for this encoder."""
        ...

    @property
    def index_key_space(self) -> IndexKeySpace:
        """The key space derived from the encoder's character-to-key mapping."""
        ...
