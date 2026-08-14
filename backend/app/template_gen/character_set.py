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


def character_set_by_id() -> dict[str, CharacterSpec]:
    """Lookup from character_id to its CharacterSpec — for stages that
    only carry a character_id (e.g. a saved glyph filename) and need to
    recover its category/character without re-deriving it themselves."""
    return {spec.character_id: spec for spec in get_character_set()}


# --- vertical metrics classification ----------------------------------
#
# Used by glyph normalization (Phase 7) and, later, font generation
# (Phase 9) to position each glyph against a shared baseline instead of
# just bottom-aligning every character's bounding box — which would make
# "p" and "A" sit on the same line incorrectly, since "p" should hang
# below it. This is a deliberately simple, V1-appropriate classification
# (no per-glyph stroke analysis) — good enough to make the font's
# baseline look coherent, not a claim of typographically precise metrics.

# Lowercase letters whose ascender reaches roughly cap-height (rather than
# just x-height). "i" is included because its dot sits high even though
# its stem doesn't.
ASCENDER_LOWERCASE: frozenset[str] = frozenset("bdfhijklt")

# Characters whose main ink legitimately extends below the baseline.
DESCENDER_CHARACTERS: frozenset[str] = frozenset("gjpqy,")

# Punctuation that visually spans close to the full cap-height rather than
# sitting at x-height (brackets, parens, quotes).
TALL_PUNCTUATION: frozenset[str] = frozenset("()[]\"'")


def is_tall_glyph(character: str, category: str) -> bool:
    """Whether this character's main body should be scaled to cap-height
    rather than x-height: uppercase, digits, lowercase ascenders, and
    "tall" punctuation."""
    if category in ("uppercase", "digit"):
        return True
    if category == "lowercase":
        return character in ASCENDER_LOWERCASE
    if category == "punctuation":
        return character in TALL_PUNCTUATION
    return False


def is_descender(character: str) -> bool:
    """Whether this character's ink legitimately extends below the
    baseline."""
    return character in DESCENDER_CHARACTERS
