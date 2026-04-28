from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ...exceptions.domain import EncodingError
from .encoding_specs import LanguageEncodingSpec
from .key_space import IndexKeySpace
from .protocols import KeyEncoderProtocol
from .types import Character, CharacterSet, EncodedIndexKeySequence, IndexKey


@dataclass(frozen=True, slots=True)
class KeyEncoder(KeyEncoderProtocol):
    """
    Encodes strings into index-key sequences according to a language encoding spec.

    Design Note:
    This encoder stores `Character` value objects in its internal reverse mapping
    (`_key_to_chars`) rather than raw strings. This keeps the implementation aligned
    with encoding-domain concepts and ensures character invariants are respected.

    In practice, the memory overhead of storing `Character` objects is expected to
    be small because character sets are typically bounded by the size of a language
    alphabet. If needed, the encoder could be optimized in future to use primitive
    strings internally while preserving the same external interface and behavior.
    """

    spec: LanguageEncodingSpec
    _key_to_chars: dict[IndexKey, CharacterSet] = field(init=False)
    _index_key_space: IndexKeySpace = field(init=False)

    def __post_init__(self) -> None:
        """
        Build derived lookup structures after initialisation.

        Constructs the reverse key-to-characters mapping and the encoder's
        IndexKeySpace from the configured character-to-key map.
        """
        # build _key_to_chars reverse lookup mapping
        temp: dict[IndexKey, set[Character]] = {}
        for char, key in self.spec.char_to_key_map.items():
            temp.setdefault(key, set()).add(char)

        key_to_chars = {k: frozenset(v) for k, v in temp.items()}

        object.__setattr__(self, '_key_to_chars', key_to_chars)
        object.__setattr__(self, '_index_key_space', IndexKeySpace.from_iterable(key_to_chars.keys()))

    def encode(self, word: str) -> EncodedIndexKeySequence:
        """Encode a string into an EncodedIndexKeySequence."""
        encoded: list[IndexKey] = []
        for c in word:
            try:
                encoded.append(self.spec.char_to_key_map[Character(c)])
            except (TypeError, ValueError, KeyError):
                raise EncodingError(f'Invalid character {c!r}; expected {self.character_set!r}') from None
        return EncodedIndexKeySequence(tuple(encoded))

    def decode(self, index_key: IndexKey) -> CharacterSet:
        """Return all characters mapped to the given index key."""
        try:
            return self._key_to_chars[index_key]
        except KeyError:
            raise EncodingError(f'Index key {index_key!r} not found') from None

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
        keys = tuple(index_keys)

        for index_key in keys:
            if index_key not in self._index_key_space:
                raise EncodingError(f'Invalid index key {index_key!r}')
        return EncodedIndexKeySequence(keys)

    @property
    def character_set(self) -> CharacterSet:
        """The set of valid characters for this encoder."""
        return self.spec.character_set

    @property
    def index_key_space(self) -> IndexKeySpace:
        """The key space derived from the encoder's character-to-key mapping."""
        return self._index_key_space
