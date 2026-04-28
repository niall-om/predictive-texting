from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import NewType, TypeAlias

IndexKey = NewType('IndexKey', int)


@dataclass(frozen=True, slots=True)
class Character:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError(f'Invalid character type; expected str, got {type(self.value)!r}')
        if len(self.value) != 1:
            raise ValueError(f'Invalid character value; expected a single character string, got {self.value!r}')

    def __str__(self) -> str:
        return self.value


CharacterSet: TypeAlias = frozenset[Character]
Char2KeyMap: TypeAlias = dict[Character, IndexKey]


@dataclass(frozen=True, slots=True)
class EncodedIndexKeySequence:
    _keys: tuple[IndexKey, ...]

    def __iter__(self) -> Iterator[IndexKey]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def __getitem__(self, index: int) -> IndexKey:
        return self._keys[index]

    def append(self, key: IndexKey) -> EncodedIndexKeySequence:
        return EncodedIndexKeySequence(self._keys + (key,))

    # factory methods
    @classmethod
    def from_iterable(cls, keys: Iterable[IndexKey]) -> EncodedIndexKeySequence:
        """Build and return an EncodedKeySequence from an iterable of IndexKeys."""
        return cls(tuple(keys))

    @classmethod
    def empty(cls) -> EncodedIndexKeySequence:
        """Return an empty EncodedKeySequence"""
        return cls(())
