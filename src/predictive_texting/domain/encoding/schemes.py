from __future__ import annotations

from enum import Enum


class EncodingScheme(str, Enum):
    T9 = 't9'
    QWERTY = 'qwerty'
