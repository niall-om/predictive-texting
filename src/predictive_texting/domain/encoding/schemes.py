"""
Encoding scheme definitions.

Defines the available strategies for mapping characters to index keys (e.g.
T9, QWERTY). These are combined with a language to select a concrete encoding
specification.
"""

from __future__ import annotations

from enum import Enum


class EncodingScheme(str, Enum):
    """
    Enumeration of supported encoding schemes.

    T9:
        Groups multiple characters under shared numeric keys (mobile keypad style).

    QWERTY:
        Maps each character to a unique key, enabling standard prefix matching.
    """

    T9 = 't9'
    QWERTY = 'qwerty'
