from __future__ import annotations

from ..lexicon.protocols import WordStoreProtocol
from ..lexicon.types import WordId
from .protocols import RankingPolicy


class FrequencyRankingPolicy(RankingPolicy):
    __slots__ = ('_word_store',)
    _word_store: WordStoreProtocol

    def __init__(self, word_store: WordStoreProtocol) -> None:
        self._word_store = word_store

    def rank(self, candidates: set[WordId], k: int) -> list[WordId]:
        """
        Returns the top-k candidates, ranked by word frequency.

        Ties are broken by:
            - word length: when two candidates have the same frequency
            - lexigraphically: when two candidates have the same frequency and length
        """
        return sorted(
            candidates,
            key=lambda word_id: (
                -self._word_store.get_frequency(word_id),
                len(self._word_store.get_word(word_id)),
                self._word_store.get_word(word_id),
            ),
        )[:k]
