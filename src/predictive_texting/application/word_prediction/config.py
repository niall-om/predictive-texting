from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from predictive_texting.domain.encoding.languages import Language
from predictive_texting.domain.encoding.schemes import EncodingScheme
from predictive_texting.exceptions.application import WordPredictionConfigError


class RankingPolicyType(str, Enum):
    """
    Supported ranking policy choices for the word prediction service.

    The config stores the policy type rather than a concrete policy instance so
    bootstrap can construct the correct policy after its runtime dependencies
    have been created.
    """

    FREQUENCY = 'frequency'


@dataclass(frozen=True, slots=True)
class WordPredictionConfig:
    """
    Configuration required to bootstrap the word prediction service.

    This object captures high-level service choices such as database location,
    language, encoding scheme, ranking policy, and number of candidates to
    return. Concrete runtime components are built from this config during
    bootstrap.
    """

    db_path: Path
    language: Language
    encoding_scheme: EncodingScheme
    ranking_policy_type: RankingPolicyType
    k: int

    def __post_init__(self) -> None:
        """
        Validate configuration values after initialisation.

        Ensures all fields are correctly typed and within expected ranges.
        """
        self._validate_path()
        self._validate_language()
        self._validate_encoding_scheme()
        self._validate_ranking_policy_type()
        self._validate_k()

    def _validate_path(self) -> None:
        """Validate that the configured database path is a Path with a valid parent directory."""
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
        """Validate that the configured language is a supported Language value."""
        if not isinstance(self.language, Language):
            raise WordPredictionConfigError(f'Invalid language: {self.language!r}; expected a Language value')

    def _validate_encoding_scheme(self) -> None:
        """Validate that the configured encoding scheme is a supported EncodingScheme value."""
        if not isinstance(self.encoding_scheme, EncodingScheme):
            raise WordPredictionConfigError(
                f'Invalid encoding scheme: {self.encoding_scheme!r}; expected an EncodingScheme value'
            )

    def _validate_ranking_policy_type(self) -> None:
        """Validate that the configured ranking policy type is supported."""
        if not isinstance(self.ranking_policy_type, RankingPolicyType):
            raise WordPredictionConfigError(
                f'Invalid ranking policy type: {self.ranking_policy_type!r}; expected a RankingPolicyType value'
            )

    def _validate_k(self) -> None:
        """Validate that the candidate limit is a positive integer."""
        if type(self.k) is not int:
            raise WordPredictionConfigError(f'Invalid type for parameter k; expected int, got {type(self.k)!r}')
        if self.k < 1:
            raise WordPredictionConfigError(f'Invalid value for parameter k; expected k >= 1, got {self.k!r}')
