from __future__ import annotations

from dataclasses import dataclass

from ...exceptions.domain import EncodingError
from .character_sets import ENGLISH_LOWERCASE_ALPHABET
from .key_maps import ENGLISH_QWERTY_MAP, ENGLISH_T9_MAP
from .languages import Language
from .schemes import EncodingScheme
from .types import Char2KeyMap, CharacterSet


@dataclass(frozen=True, slots=True)
class LanguageEncodingSpec:
    """
    Defines the character-to-key mapping for a given language.

    Design Note:
    This specification uses `Character` value objects and `CharacterSet`
    abstractions rather than raw strings. This ensures that character-level
    invariants (e.g. single-character constraint) are enforced consistently
    across the encoding domain.

    The spec enforces two key invariants:
    - Every character in the language character set must be mapped to a key.
    - No character outside the character set may appear in the mapping.

    These guarantees allow downstream components (e.g. KeyEncoder and
    completion index) to assume a consistent and complete mapping without
    additional validation.

    In principle, a more memory-efficient representation using primitive
    strings could be used internally, but the current design prioritizes
    correctness and clarity at the domain boundary.
    """

    language: Language
    character_set: CharacterSet
    char_to_key_map: Char2KeyMap

    def __post_init__(self) -> None:
        # Validation Rules:
        # 1) Every character in character set must be mapped to a key
        # 2) Every character in char_to_key_map must be in the language character set.

        missing = self.character_set - self.char_to_key_map.keys()
        if missing:
            raise EncodingError(f'Characters not mapped to keys: {missing!r}')

        extra = self.char_to_key_map.keys() - self.character_set
        if extra:
            raise EncodingError(f'Characters in key map not in character set: {extra!r}')


# Private Registry
_ENCODING_SPECS: dict[tuple[Language, EncodingScheme], LanguageEncodingSpec] = {
    (Language.ENGLISH, EncodingScheme.T9): LanguageEncodingSpec(
        language=Language.ENGLISH,
        character_set=ENGLISH_LOWERCASE_ALPHABET,
        char_to_key_map=ENGLISH_T9_MAP,
    ),
    (Language.ENGLISH, EncodingScheme.QWERTY): LanguageEncodingSpec(
        language=Language.ENGLISH,
        character_set=ENGLISH_LOWERCASE_ALPHABET,
        char_to_key_map=ENGLISH_QWERTY_MAP,
    ),
}


# ---------------------------- Public API -----------------------------------------


# Language encoding specs should be fetched via this function.
def get_encoding_spec(language: Language, scheme: EncodingScheme) -> LanguageEncodingSpec:
    try:
        return _ENCODING_SPECS[(language, scheme)]
    except KeyError:
        raise EncodingError(f'No encoding spec registered for language={language!r}, scheme={scheme!r}') from None
