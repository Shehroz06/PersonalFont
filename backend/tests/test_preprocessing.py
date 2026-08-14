import cv2
import numpy as np
import pytest

from pipeline.preprocessing.config import PreprocessingConfig
from pipeline.preprocessing.crop import autocrop_borders
from pipeline.preprocessing.deskew import deskew, estimate_skew_angle
from pipeline.preprocessing.errors import DeskewError, PageDetectionError
from pipeline.preprocessing.geometry import order_points
from pipeline.preprocessing.grayscale import to_grayscale
from pipeline.preprocessing.noise_removal import remove_noise
from pipeline.preprocessing.page_detection import detect_page_contour
from pipeline.preprocessing.perspective_correction import correct_perspective
from pipeline.preprocessing.pipeline import preprocess_page
from pipeline.preprocessing.thresholding import binarize_adaptive, binarize_otsu
from tests.preprocessing_helpers import build_synthetic_photo, draw_ink_strokes


# --- geometry -----------------------------------------------------------


def test_order_points_is_stable_regardless_of_input_order():
    tl, tr, br, bl = (0, 0), (100, 0), (100, 200), (0, 200)
    shuffled = np.array([br, tl, bl, tr], dtype=np.float32)

    ordered = order_points(shuffled)

    assert np.allclose(ordered[0], tl)
    assert np.allclose(ordered[1], tr)
    assert np.allclose(ordered[2], br)
    assert np.allclose(ordered[3], bl)


# --- page_detection -------------------------------------------------------


def test_detect_page_contour_finds_expected_corners():
    image, expected_corners = build_synthetic_photo()

    detected = detect_page_contour(image)

    # cv2's polygon approximation won't be pixel-perfect; a few px per
    # corner is an acceptable tolerance for a synthetic, noise-free page.
    assert np.allclose(detected, expected_corners, atol=6)


def test_detect_page_contour_raises_on_blank_noise_image():
    rng = np.random.default_rng(1)
    blank = rng.integers(0, 80, size=(400, 400, 3), dtype=np.uint8)

    with pytest.raises(PageDetectionError):
        detect_page_contour(blank)


# --- perspective_correction ------------------------------------------------


def test_correct_perspective_produces_requested_output_size():
    image, corners = build_synthetic_photo()

    rectified = correct_perspective(image, corners, output_size=(200, 300))

    assert rectified.shape[:2] == (300, 200)  # (height, width)


def test_correct_perspective_recovers_mostly_uniform_page():
    image, corners = build_synthetic_photo()

    rectified = correct_perspective(image, corners, output_size=(200, 300))
    gray = to_grayscale(rectified)

    # The synthetic page is a solid white rectangle: after rectifying it
    # should be almost entirely bright, away from the warp edges.
    interior = gray[20:-20, 20:-20]
    assert interior.mean() > 230


# --- crop -----------------------------------------------------------------


def test_autocrop_borders_trims_to_bright_content():
    canvas = np.zeros((100, 100), dtype=np.uint8)
    canvas[20:80, 30:70] = 255

    cropped = autocrop_borders(canvas)

    assert cropped.shape == (60, 40)
    assert cropped.min() == 255


def test_autocrop_borders_returns_unchanged_on_empty_image():
    blank = np.zeros((50, 50), dtype=np.uint8)

    result = autocrop_borders(blank)

    assert result.shape == blank.shape


# --- grayscale --------------------------------------------------------------


def test_to_grayscale_converts_color_image():
    color = np.full((10, 10, 3), 128, dtype=np.uint8)

    gray = to_grayscale(color)

    assert gray.ndim == 2
    assert gray.shape == (10, 10)


def test_to_grayscale_passthrough_for_already_gray():
    gray_in = np.full((10, 10), 128, dtype=np.uint8)

    result = to_grayscale(gray_in)

    assert result is gray_in


# --- noise_removal ------------------------------------------------------


def test_remove_noise_preserves_shape_and_dtype():
    rng = np.random.default_rng(2)
    noisy = rng.integers(0, 255, size=(80, 80), dtype=np.uint8)

    denoised = remove_noise(noisy)

    assert denoised.shape == noisy.shape
    assert denoised.dtype == noisy.dtype


def test_remove_noise_reduces_salt_and_pepper_variance():
    rng = np.random.default_rng(3)
    base = np.full((80, 80), 200, dtype=np.uint8)
    salt_pepper = rng.choice([0, 200, 255], size=(80, 80), p=[0.05, 0.9, 0.05]).astype(np.uint8)

    denoised = remove_noise(salt_pepper)

    assert denoised.std() < base.astype(np.float32).std() + salt_pepper.std()
    assert denoised.std() < salt_pepper.std()


# --- thresholding -----------------------------------------------------------


def test_binarize_otsu_separates_ink_from_background():
    gray = np.full((100, 100), 240, dtype=np.uint8)  # bright page
    gray[40:60, 40:60] = 20  # dark ink stroke

    binary = binarize_otsu(gray)

    assert set(np.unique(binary)).issubset({0, 255})
    assert binary[50, 50] == 255  # ink -> foreground (white)
    assert binary[5, 5] == 0  # background -> 0


def test_binarize_adaptive_returns_binary_image():
    gray = np.full((100, 100), 240, dtype=np.uint8)
    gray[40:60, 40:60] = 20

    binary = binarize_adaptive(gray)

    assert set(np.unique(binary)).issubset({0, 255})


# --- deskew -----------------------------------------------------------------


def _skewed_rect_image(skew_deg: float, size: int = 300) -> np.ndarray:
    """A binary image of an axis-aligned rectangle rotated by ``skew_deg``
    (as getRotationMatrix2D would need to *correct*), built via warpAffine
    so the ground-truth angle is unambiguous."""
    image = np.zeros((size, size), dtype=np.uint8)
    box = cv2.boxPoints(((size / 2, size / 2), (200, 100), 0)).astype(np.int32)
    cv2.fillConvexPoly(image, box, 255)

    matrix = cv2.getRotationMatrix2D((size / 2, size / 2), -skew_deg, 1.0)
    return cv2.warpAffine(image, matrix, (size, size))


def test_estimate_skew_angle_recovers_known_rotation():
    binary = _skewed_rect_image(skew_deg=12)

    angle = estimate_skew_angle(binary)

    assert abs(angle - 12) < 1.0


def test_estimate_skew_angle_raises_on_empty_image():
    blank = np.zeros((100, 100), dtype=np.uint8)

    with pytest.raises(DeskewError):
        estimate_skew_angle(blank)


def test_deskew_reduces_measured_skew():
    binary = _skewed_rect_image(skew_deg=10)

    rotated, applied_angle = deskew(binary)
    remaining_angle = estimate_skew_angle(rotated)

    assert abs(applied_angle - 10) < 1.0
    assert abs(remaining_angle) < 1.0


def test_deskew_skips_large_angles():
    binary = _skewed_rect_image(skew_deg=40)

    result, applied_angle = deskew(binary, angle=40)

    assert applied_angle == 0.0
    assert np.array_equal(result, binary)


# --- pipeline (integration-lite) --------------------------------------------


def test_preprocess_page_runs_all_stages_end_to_end():
    image, corners = build_synthetic_photo(angle_deg=6.0)
    image = draw_ink_strokes(image, corners)

    config = PreprocessingConfig(working_dpi=50)  # small output keeps the test fast
    result = preprocess_page(image, config)

    expected_size = config.output_size_px  # (width, height)
    assert result.binary.shape[:2][::-1] == expected_size
    assert set(np.unique(result.binary)).issubset({0, 255})
    assert result.deskewed.shape == result.binary.shape
    assert (result.binary == 255).sum() > 0  # ink survived thresholding


def test_preprocess_page_raises_actionable_error_on_blank_photo():
    rng = np.random.default_rng(4)
    blank = rng.integers(0, 80, size=(300, 300, 3), dtype=np.uint8)

    with pytest.raises(PageDetectionError):
        preprocess_page(blank)
