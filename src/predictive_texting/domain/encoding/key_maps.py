"""
Character-to-key mappings for supported encoding schemes.

Defines how characters are converted into index keys for different encoding
strategies (e.g. T9, QWERTY).

Design Note:
Mappings are defined using domain value objects (`Character`, `IndexKey`)
rather than primitive `str`/`int` values. This keeps the data aligned with
encoding-domain concepts and ensures invariants are applied at construction.

In principle, a more memory-efficient primitive representation could be used,
but these mappings are small and fixed in size, so the current design
prioritizes clarity and correctness.
"""

from __future__ import annotations

from .types import Char2KeyMap, Character, IndexKey

# T9 keypad mapping for English characters.
# Multiple characters share the same numeric key.
ENGLISH_T9_MAP: Char2KeyMap = {
    Character(c): IndexKey(k)
    for k, chars in {
        2: 'abc',
        3: 'def',
        4: 'ghi',
        5: 'jkl',
        6: 'mno',
        7: 'pqrs',
        8: 'tuv',
        9: 'wxyz',
    }.items()
    for c in chars
}


# QWERTY-style mapping where each character maps to a unique integer key.
# This enables standard prefix-based autocomplete behaviour.
ENGLISH_QWERTY_MAP: Char2KeyMap = {
    Character(c): IndexKey(k) for k, c in enumerate('abcdefghijklmnopqrstuvwxyz', start=1)
}
