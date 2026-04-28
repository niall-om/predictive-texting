from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from predictive_texting.domain.encoding.languages import Language

_BASE_DIR = Path(__file__).resolve().parent
_SEED_FILES_DIR = _BASE_DIR / 'seed_files'


_SEED_FILE_REGISTRY: Mapping[Language, Path] = {
    Language.ENGLISH: _SEED_FILES_DIR / 'ENGLISH.txt',
}


# public accessors
def get_seed_file(language: Language) -> Path:
    try:
        path = _SEED_FILE_REGISTRY[language]
    except KeyError:
        raise ValueError(f'No seed file registered for language {language!r}') from None

    if not path.exists():
        raise ValueError(f'Seed file does not exist for language {language!r}: {path!r}')

    if not path.is_file():
        raise ValueError(f'Seed path is not a file for language {language!r}: {path!r}')

    return path


def load_seed_words(language: Language) -> list[str]:
    path = get_seed_file(language)

    try:
        with path.open('r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]

    except OSError as e:
        raise ValueError(f'Failed to load seed words for language {language!r} from {path!r}') from e
