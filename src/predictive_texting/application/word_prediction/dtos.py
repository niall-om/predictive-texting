from __future__ import annotations

from dataclasses import dataclass

from predictive_texting.domain.lexicon.types import Word, WordId


@dataclass(frozen=True, slots=True)
class CandidateWord:
    word_id: WordId
    word: Word
