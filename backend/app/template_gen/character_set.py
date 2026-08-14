"""Single source of truth for which characters PersonalFont V1 supports.

No other module should hardcode a character list or its Unicode codepoint.
Everything downstream (template layout, extraction, validation, font
generation) must read the set from here so a future template version can
change the character set without touching pipeline code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CharacterSpec:
    """Describes one character the template will collect a sample for."""

    character: str
    character_id: str
    category: str  # "uppercase" | "lowercase" | "digit" | "punctuation"

    @property
    def codepoint(self) -> str:
        return f"U+{ord(self.character):04X}"


_PUNCTUATION_NAMES = {
    ".": "period",
    ",": "comma",
    "!": "exclamation",
    "?": "question",
    "'": "apostrophe",
    ":": "colon",
    ";": "semicolon",
    '"': "quote",
    "-": "hyphen",
    "(": "paren_open",
    ")": "paren_close",
    "[": "bracket_open",
    "]": "bracket_close",
    "_": "underscore",
}


def _build_default_character_set() -> tuple[CharacterSpec, ...]:
    specs: list[CharacterSpec] = []

    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        specs.append(CharacterSpec(ch, f"uppercase_{ch}", "uppercase"))

    for ch in "abcdefghijklmnopqrstuvwxyz":
        specs.append(CharacterSpec(ch, f"lowercase_{ch}", "lowercase"))

    for ch in "0123456789":
        specs.append(CharacterSpec(ch, f"digit_{ch}", "digit"))

    for ch in ".,!?':;\"-()[]_":
        name = _PUNCTUATION_NAMES[ch]
        specs.append(CharacterSpec(ch, f"punctuation_{name}", "punctuation"))

    return tuple(specs)


# Default V1 character set, per Project spec section 3.
DEFAULT_CHARACTER_SET: tuple[CharacterSpec, ...] = _build_default_character_set()


def get_character_set() -> tuple[CharacterSpec, ...]:
    """Return the character set to use for template generation.

    Kept as a function (rather than importing the constant directly) so a
    future version can swap in a config-driven or per-template character
    set without changing call sites.
    """
    return DEFAULT_CHARACTER_SET
