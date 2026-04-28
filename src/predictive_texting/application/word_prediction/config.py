from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ...domain.encoding.languages import Language
from ...exceptions.application import WordPredictionConfigError


class RankingPolicyType(str, Enum):
    FREQUENCY = 'frequency'


@dataclass(frozen=True, slots=True)
class WordPredictionConfig:
    db_path: Path
    language: Language
    ranking_policy_type: RankingPolicyType
    k: int

    def __post_init__(self) -> None:
        self._validate_path()
        self._validate_language()
        self._validate_ranking_policy_type()
        self._validate_k()

    def _validate_path(self) -> None:
        db_path = self.db_path
        if not isinstance(db_path, Path):
            raise WordPredictionConfigError(
                f'Invalid Database path: {db_path!r} ; expected a Path object, got {type(db_path)!r}'
            )

        if not db_path.parent.exists():
            raise WordPredictionConfigError(f'Invalid Database path: {db_path!r} ; parent directory does not exist')

        if not db_path.parent.is_dir():
            raise WordPredictionConfigError(f'Invalid Database path: {db_path!r} ; parent is not a directory')

    def _validate_language(self) -> None:
        if not isinstance(self.language, Language):
            raise WordPredictionConfigError(f'Invalid language: {self.language!r}; expected a Language value')

    def _validate_ranking_policy_type(self) -> None:
        if not isinstance(self.ranking_policy_type, RankingPolicyType):
            raise WordPredictionConfigError(
                f'Invalid ranking policy type: {self.ranking_policy_type!r}; expected a RankingPolicyType value'
            )

    def _validate_k(self) -> None:
        if type(self.k) is not int:
            raise WordPredictionConfigError(f'Invalid type for parameter k; expected int, got {type(self.k)!r}')
        if self.k < 1:
            raise WordPredictionConfigError(f'Invalid value for parameter k; expected k >= 1, got {self.k!r}')
