from __future__ import annotations

from string import ascii_lowercase

from .types import Character, CharacterSet

# ------------------------------ Alphabets -----------------------------------------
ENGLISH_LOWERCASE_ALPHABET: CharacterSet = frozenset(Character(c) for c in ascii_lowercase)
