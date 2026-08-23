import cv2
import numpy as np

from pipeline.ink_geometry import ink_bounding_box, ink_pixel_count, remove_small_components


def test_ink_pixel_count():
    image = np.zeros((50, 50), dtype=np.uint8)
    image[10:20, 10:15] = 255  # 10x5 = 50 px

    assert ink_pixel_count(image) == 50


def test_ink_bounding_box_tight():
    image = np.zeros((50, 50), dtype=np.uint8)
    image[10:20, 15:25] = 255

    assert ink_bounding_box(image) == (15, 10, 25, 20)


def test_ink_bounding_box_none_for_empty_image():
    assert ink_bounding_box(np.zeros((50, 50), dtype=np.uint8)) is None


# --- remove_small_components -------------------------------------------


def test_remove_small_components_leaves_single_component_untouched():
    image = np.zeros((100, 100), dtype=np.uint8)
    cv2.circle(image, (50, 50), 20, 255, -1)

    cleaned = remove_small_components(image)

    assert np.array_equal(cleaned, image)


def test_remove_small_components_leaves_empty_image_untouched():
    image = np.zeros((100, 100), dtype=np.uint8)

    cleaned = remove_small_components(image)

    assert cleaned.max() == 0


def test_remove_small_components_drops_tiny_noise_speck():
    image = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(image, (50, 50), (100, 150), 255, -1)  # large real stroke
    cv2.circle(image, (170, 20), 2, 255, -1)  # a few-pixel speck of noise, far away

    cleaned = remove_small_components(image)

    num_labels, _labels, _stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    assert num_labels == 2  # background + the one real stroke
    assert cleaned[20, 170] == 0  # the noise speck's location is gone
    assert cleaned[100, 75] == 255  # the real stroke survived untouched


def test_remove_small_components_preserves_legitimate_dot_like_second_stroke():
    # Mimics an "i" or "j": a tall stem plus a proportionally-sized dot,
    # at roughly the same relative size measured on a real scanned glyph
    # (~41% of the main stroke's area) — must survive.
    image = np.zeros((200, 100), dtype=np.uint8)
    cv2.rectangle(image, (40, 80), (60, 180), 255, -1)  # stem: 20x100 = 2000px
    cv2.circle(image, (50, 40), 16, 255, -1)  # dot: ~804px ~= 40% of stem

    cleaned = remove_small_components(image)

    num_labels, _labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    assert num_labels == 3  # background + stem + dot, both survived


def test_remove_small_components_preserves_two_similar_sized_components():
    # Mimics a ":" — two dots of roughly equal size, neither "the main
    # stroke" in a meaningful sense; both must survive regardless of
    # which one happens to be marginally larger.
    image = np.zeros((150, 100), dtype=np.uint8)
    cv2.circle(image, (50, 40), 15, 255, -1)
    cv2.circle(image, (50, 110), 15, 255, -1)

    cleaned = remove_small_components(image)

    num_labels, _labels, _stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    assert num_labels == 3  # background + both dots


def test_remove_small_components_drops_several_small_specks_around_one_stroke():
    # Approximates what a partially-surviving background element looks
    # like after thresholding: one real stroke plus a handful of small,
    # scattered fragments, none individually significant.
    image = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(image, (60, 60), (140, 140), 255, -1)  # real stroke, 80x80=6400px

    rng = np.random.default_rng(0)
    for _ in range(15):
        x, y = rng.integers(10, 190, size=2)
        radius = int(rng.integers(1, 4))
        cv2.circle(image, (int(x), int(y)), radius, 255, -1)

    cleaned = remove_small_components(image)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    # Only the one large stroke should remain (small specks that happened
    # to touch/merge with it become part of its component and are fine).
    areas = stats[1:, cv2.CC_STAT_AREA]
    assert num_labels >= 2
    assert areas.max() >= 6400
    assert all(area >= 6400 * 0.15 for area in areas)
