from __future__ import annotations

from dataclasses import dataclass

import potrace


@dataclass(frozen=True)
class VectorizationConfig:
    # Suppress speckles smaller than this many pixels (stray ink specks,
    # scan noise that survived thresholding).
    turdsize: int = 2

    # How potrace resolves ambiguous pixel-corner cases; MINORITY is
    # potrace's own recommended default and works well for handwriting.
    turnpolicy: int = potrace.POTRACE_TURNPOLICY_MINORITY

    # Corner smoothness threshold: higher allows sharper corners to stay
    # sharp rather than being rounded into curves.
    alphamax: float = 1.0

    # Curve optimization: merges consecutive Bezier segments where doing
    # so stays within opttolerance, directly serving spec §10's "avoid
    # excessive nodes" / "smooth paths" requirements.
    opticurve: bool = True
    opttolerance: float = 0.2

    decimal_precision: int = 2
