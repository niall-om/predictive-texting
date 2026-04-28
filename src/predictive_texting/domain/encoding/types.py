"""
Domain value objects and type aliases for text-to-key encoding.

These types define the small primitives used by encoding specs, key encoders,
and completion indexes. They keep validation close to the encoding domain.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import NewType, TypeAlias

# Integer key used by encoding schemes and completion indexes.
# For T9 this corresponds to keypad digits; for QWERTY it currently maps
# characters to stable integer positions.
IndexKey = NewType('IndexKey', int)


@dataclass(frozen=True, slots=True)
class Character:
    """Validated single-character value object used in encoding maps."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError(f'Invalid character type; expected str, got {type(self.value)!r}')
        if len(self.value) != 1:
            raise ValueError(f'Invalid character value; expected a single character string, got {self.value!r}')

    def __str__(self) -> str:
        return self.value


# Immutable set of valid characters for an encoding specification.
CharacterSet: TypeAlias = frozenset[Character]

# Mapping from validated characters to index keys.
Char2KeyMap: TypeAlias = dict[Character, IndexKey]


@dataclass(frozen=True, slots=True)
class EncodedIndexKeySequence:
    """
    Immutable sequence of index keys produced by a key encoder.

    The completion index uses this sequence as the encoded representation of a
    word or input prefix.
    """

    _keys: tuple[IndexKey, ...]

    def __iter__(self) -> Iterator[IndexKey]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def __getitem__(self, index: int) -> IndexKey:
        return self._keys[index]

    def append(self, key: IndexKey) -> EncodedIndexKeySequence:
        """Return a new encoded sequence with key appended."""
        return EncodedIndexKeySequence(self._keys + (key,))

    # factory methods
    @classmethod
    def from_iterable(cls, keys: Iterable[IndexKey]) -> EncodedIndexKeySequence:
        """Build an encoded key sequence from an iterable of index keys."""
        return cls(tuple(keys))

    @classmethod
    def empty(cls) -> EncodedIndexKeySequence:
        """Return an empty encoded key sequence."""
        return cls(())
