from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..lexicon.types import WordId


# make this protocol type checkable at runtime for service config validation
@runtime_checkable
class RankingPolicy(Protocol):
    def rank(self, candidates: set[WordId], k: int) -> list[WordId]:
        """
        Rank a set of words, `candidates` based on a ranking policy.
        Returns the top k ranked words, defined by policy, in order of rank.
        """
        ...
