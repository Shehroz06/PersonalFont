# PersonalFont — Architecture & Progress

Source specs: `Initial_project_prompt.txt`, `Project_spec.txt`, `Functional_requirements.txt`, `Non_Functional_requirements`.

## Development order (from Initial_project_prompt.txt §21)

| Phase | Description | Status |
|---|---|---|
| 1 | Project scaffolding | done |
| 2 | Template generation + template JSON | done |
| 3 | Image preprocessing | done |
| 4 | Template alignment | done |
| 5 | Character extraction | not started |
| 6 | Character validation | not started |
| 7 | Glyph normalization | not started |
| 8 | Bitmap → SVG | not started |
| 9 | SVG → TTF/OTF | not started |
| 10 | End-to-end CLI pipeline | not started |
| 11 | FastAPI API | not started |
| 12 | Frontend | not started |
| 13 | Preview + ZIP packaging | not started |
| 14 | Integration with Handwriting Detection Engine | not started |

## Phase 2 design decisions

**Character set is a single source of truth** (`backend/app/template_gen/character_set.py`). It is the only place the V1 character list (A-Z, a-z, 0-9, `.,!?':;"-()[]_`) is enumerated. Layout, JSON export, and (later) segmentation/validation/font generation all read from it — no character coordinates or lists are duplicated elsewhere.

**Layout is pure geometry, separate from rendering** (`layout.py` vs `pdf_renderer.py`). `compute_layout()` returns plain dataclasses (`PageLayout`, `ElementBox`, `MarkerBox`) in PDF point units, independent of reportlab, so the packing logic is unit-testable without generating a PDF. Character boxes are packed into a fixed grid (rows × columns derived from page size, margins, and box size in `LayoutConfig`) — adding characters or changing box size never requires touching per-character coordinates.

**Alignment markers use ArUco (`cv2.aruco`, `DICT_4X4_50`)**, one per page corner. The marker ID encodes both the page index and the corner (`marker_id = page_index * 4 + corner_index`), so the alignment stage (Phase 4) can identify which page and orientation a photographed sheet corresponds to from the marker IDs alone, and recover a homography for perspective/rotation/scale correction (NFR-02: rotation, perspective distortion, moderate camera distortion). Plain OpenCV squares were considered but rejected — they don't encode an ID or provide the four correspondence points needed for a robust homography under arbitrary rotation.

**Template JSON schema** (`schema.py`, Pydantic): matches the conceptual shape from Project spec §4 but is more complete — each page carries both `elements` (character boxes: character, id, category, unicode codepoint, x/y/width/height) and `markers` (id, corner, position, size, ArUco dictionary). `template_version` and `template_id` are top-level so future `template_v2` / `urdu_template` / etc. can coexist without code changes, per Project_spec.txt's "data-driven, not hardcoded" requirement.

Generated artifacts: `templates/template_v1.pdf` (printable) and `templates/template_v1.json` (machine-readable description consumed by later phases). Regenerate with `scripts/generate_template.py`.

## Verified

- `backend/tests/test_template_gen.py`: character-set integrity, layout packing (no duplicates, no overlaps, in-bounds, markers don't collide with character boxes), and JSON/PDF generation. `10 passed`.
- Rendered PDF visually inspected at 100 DPI (via `pdftoppm`) to confirm no visual overlap between header text, ArUco markers, and character grid.

## Phase 3 design decisions

**One module per pipeline stage** under `backend/pipeline/preprocessing/`: `page_detection.py`, `perspective_correction.py`, `crop.py`, `grayscale.py`, `noise_removal.py`, `thresholding.py`, `deskew.py`, each a small pure function operating on numpy arrays with no filesystem/job knowledge. `pipeline.py` only chains them (per §5's "do not create one huge processing function") — it contains no image-processing logic of its own.

**Page detection vs. template alignment are kept separate.** `page_detection.py` finds the largest plausible 4-sided contour in a photo using classical edge/contour detection (Canny + `approxPolyDP`) — it knows nothing about the template's ArUco markers or character grid. Matching a detected page to a *specific* template version, scoring alignment confidence, and rejecting low-confidence pages with an actionable error (spec §6) is deferred to Phase 4, which will consume the ArUco markers laid down in Phase 2.

**Binary image convention**: after `thresholding.py`, ink/foreground = 255 (white), background = 0 (black) — inverted from the original scan. This is documented once in `thresholding.py`'s docstring; `deskew.py` and (later) segmentation rely on it rather than re-deriving it.

**`PreprocessingConfig.output_size_px`** derives the rectified image's pixel dimensions from the *same* `LayoutConfig` page size (points) used by template generation, plus a configurable working DPI (default 200) — avoiding a second, independently-hardcoded page size that could drift out of sync with the template JSON's coordinate space.

**Deskew angle sign convention**: `cv2.minAreaRect`'s angle range has changed across OpenCV versions ([0, 90) currently). `estimate_skew_angle` normalizes it via `((raw + 45) % 90) - 45`, verified empirically (see `test_preprocessing.py`) to match the sign `cv2.getRotationMatrix2D` expects to *correct* the rotation, so no extra sign flip is needed downstream. Angles beyond `MAX_CORRECTABLE_SKEW_DEGREES` (15°) are treated as a likely detection failure rather than corrected, since perspective correction should have already removed gross rotation — large residual skew signals something upstream went wrong.

**Errors are explicit** (`errors.py`: `PageDetectionError`, `DeskewError`), each raised with a specific, user-actionable message per spec §17 — never a bare "processing failed".

## Verified — Phase 3

- `backend/tests/test_preprocessing.py` (29 tests, all passing): each stage unit-tested in isolation (geometry ordering, page detection incl. failure case, perspective correction, autocrop, grayscale, noise removal, both thresholding methods, deskew angle estimation/correction incl. the large-angle skip), plus two integration-lite tests running `preprocess_page` end-to-end on a synthetic photographed page. Synthetic test fixtures live in `tests/preprocessing_helpers.py`.
- Manually rendered a synthetic tilted/noisy photo through the full pipeline and visually confirmed the rectified output is properly de-rotated with ink strokes preserved as clean binary content.

## Phase 4 design decisions

**Alignment is independent of Phase 3's page detection.** `pipeline/alignment/` detects the printed ArUco markers directly (`marker_detection.py`) rather than depending on Phase 3's contour-based page/perspective correction. Markers give precise, identifiable correspondence points (4 corners each, with a decodable ID) that a generic paper-edge contour can't — they're what makes it possible to (a) recognize *which* template page a photo shows, and (b) fit an accurate homography under rotation/perspective/scale in one step (spec §6). Phase 3's output can still feed into this stage (e.g. its grayscale/denoised image), but alignment does not require it — it can run on a raw photo directly, and re-derives its own homography rather than trusting Phase 3's generic rectification for the final crop coordinates.

**Marker ID encodes the page.** Since `layout.py` assigns `marker_id = page_index * 4 + corner_index`, `align.py` recovers the page a photo belongs to purely from which marker IDs were detected (majority vote across detected markers), before ever looking at pixel content. This means a caller doesn't need to know in advance which page of a multi-page submission they're aligning — one function handles all pages of a template.

**Confidence is coverage × accuracy** (`confidence.py`): the fraction of expected markers actually matched, times a linear falloff based on mean reprojection error after fitting the homography. Both matter independently — 4/4 markers found but a blurry, poorly-fit photo should still score low, and vice versa. Below `min_confidence` (default 0.6) or below `min_matched_markers` (default 3, since 2 markers don't spread enough correspondence points across the page for a trustworthy perspective fit), `align_page_to_template` raises `AlignmentError` with the specific reason and an actionable next step, matching the spec §6 example message format.

**New shared coordinate-conversion module** (`app/template_gen/coordinates.py`): converts template JSON's point-based, y-up boxes into pixel-based, y-down boxes at a caller-chosen DPI. This is needed by alignment (to know where markers are *expected* in the rectified image) and will be reused unchanged by character extraction (Phase 5, to crop each glyph's box) — written once rather than re-deriving the y-flip per stage. `PreprocessingConfig.output_size_px` and `ARUCO_DICTIONARY`/`POINTS_PER_INCH` were refactored to live in `layout.py` and be reused here and in `pdf_renderer.py`, rather than staying duplicated across Phase 2 and Phase 3 code.

## Verified — Phase 4

- `backend/tests/test_alignment.py` (9 tests, all passing): marker detection (found / not found), homography + confidence math in isolation, and `align_page_to_template` end-to-end — recovers a rotated/scaled/translated page, identifies the correct page among a multi-page template, and raises `AlignmentError` for no markers, too few markers, and markers belonging to a page absent from the given template. Synthetic fixtures in `tests/alignment_helpers.py`.
- Manually verified against the *real* `template_v1.json`/`template_v1.pdf` (not just synthetic test fixtures): rendered page 1 via `pdftoppm`, simulated a photo (11° rotation, 0.92 scale, translation, onto a larger noisy background), and ran it through `align_page_to_template` — recovered with 96.4% confidence, 4/4 markers, 0.29px mean reprojection error, and the rectified output visually matches the original template layout exactly.
