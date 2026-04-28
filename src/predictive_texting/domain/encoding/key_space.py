from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from ...exceptions.domain import EncodingError
from .types import IndexKey


@dataclass(frozen=True, slots=True)
class IndexKeySpace:
    keys: tuple[IndexKey, ...]
    _index_map: dict[IndexKey, int] = field(init=False)

    def __post_init__(self) -> None:
        if not self.keys:
            raise EncodingError('IndexKeySpace cannot be empty.')

        if len(self.keys) != len(set(self.keys)):
            raise EncodingError('Duplicate index keys in IndexKeySpace')

        object.__setattr__(self, '_index_map', {key: i for i, key in enumerate(self)})

    @classmethod
    def from_iterable(cls, index_keys: Iterable[IndexKey]) -> IndexKeySpace:
        return cls(tuple(index_keys))

    def __len__(self) -> int:
        return len(self.keys)

    def __contains__(self, index_key: IndexKey) -> bool:
        return index_key in self._index_map

    def __iter__(self) -> Iterator[IndexKey]:
        return iter(self.keys)

    def size(self) -> int:
        return len(self.keys)

    def index(self, index_key: IndexKey) -> int:
        try:
            return self._index_map[index_key]
        except KeyError:
            raise EncodingError(f'Index key {index_key!r} not in IndexKeySpace') from None
