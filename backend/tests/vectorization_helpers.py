"""Synthetic glyph shapes and a minimal SVG-path rasterizer for the
vectorization tests. Built directly in the ink=255/background=0
convention. Not a test module itself (no test_ prefix) — pytest won't
collect it.
"""

from __future__ import annotations

import re

import cv2
import numpy as np


def letter_l_stroke(size: tuple[int, int] = (500, 500), thickness: int = 30) -> np.ndarray:
    """A single connected stroke with no hole — an "L" shape."""
    h, w = size
    image = np.zeros(size, dtype=np.uint8)
    cv2.line(image, (3 * w // 10, h // 6), (3 * w // 10, 5 * h // 6), 255, thickness)
    cv2.line(image, (3 * w // 10, 5 * h // 6), (7 * w // 10, 5 * h // 6), 255, thickness)
    return image


def letter_a_with_hole(size: tuple[int, int] = (500, 500), thickness: int = 25) -> np.ndarray:
    """An "A"-like shape whose interior triangle is a genuine hole."""
    h, w = size
    image = np.zeros(size, dtype=np.uint8)
    cv2.line(image, (w // 2, h // 10), (2 * w // 10, 9 * h // 10), 255, thickness)
    cv2.line(image, (w // 2, h // 10), (8 * w // 10, 9 * h // 10), 255, thickness)
    cv2.line(image, (3 * w // 10, 6 * h // 10), (7 * w // 10, 6 * h // 10), 255, thickness)
    return image


def filled_circle(size: tuple[int, int] = (500, 500), radius: int = 150) -> np.ndarray:
    h, w = size
    image = np.zeros(size, dtype=np.uint8)
    cv2.circle(image, (w // 2, h // 2), radius, 255, -1)
    return image


_TOKEN_RE = re.compile(r"[MLCZ]|-?\d+\.?\d*")


def rasterize_single_subpath(path_data: str, size: tuple[int, int]) -> np.ndarray:
    """Rasterize a path `d` string containing exactly one "M ... Z"
    subpath (no holes) back into a binary image, by sampling any Bezier
    (C) segments and filling the resulting polygon. Used to check
    round-trip shape fidelity for hole-free glyphs; deliberately doesn't
    handle multiple subpaths / evenodd hole punching, since that's a
    rendering concern beyond what these tests need.
    """
    tokens = _TOKEN_RE.findall(path_data)
    points: list[tuple[float, float]] = []
    current: tuple[float, float] | None = None
    i = 0
    while i < len(tokens):
        command = tokens[i]
        if command == "M" or command == "L":
            x, y = float(tokens[i + 1]), float(tokens[i + 2])
            current = (x, y)
            points.append(current)
            i += 3
        elif command == "C":
            c1 = (float(tokens[i + 1]), float(tokens[i + 2]))
            c2 = (float(tokens[i + 3]), float(tokens[i + 4]))
            end = (float(tokens[i + 5]), float(tokens[i + 6]))
            p0 = current
            for t in np.linspace(0, 1, 15)[1:]:
                x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * c1[0] + 3 * (1 - t) * t**2 * c2[0] + t**3 * end[0]
                y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * c1[1] + 3 * (1 - t) * t**2 * c2[1] + t**3 * end[1]
                points.append((x, y))
            current = end
            i += 7
        elif command == "Z":
            i += 1
        else:
            raise ValueError(f"Unexpected token in path data: {command!r}")

    canvas = np.zeros(size, dtype=np.uint8)
    polygon = np.array(points, dtype=np.int32)
    cv2.fillPoly(canvas, [polygon], 255)
    return canvas


def iou(a: np.ndarray, b: np.ndarray) -> float:
    a_bool = a > 0
    b_bool = b > 0
    intersection = int(np.logical_and(a_bool, b_bool).sum())
    union = int(np.logical_or(a_bool, b_bool).sum())
    return intersection / union if union else 1.0
