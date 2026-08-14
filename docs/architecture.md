# PersonalFont — Architecture & Progress

Source specs: `Initial_project_prompt.txt`, `Project_spec.txt`, `Functional_requirements.txt`, `Non_Functional_requirements`.

## Development order (from Initial_project_prompt.txt §21)

| Phase | Description | Status |
|---|---|---|
| 1 | Project scaffolding | done |
| 2 | Template generation + template JSON | done |
| 3 | Image preprocessing | done |
| 4 | Template alignment | not started |
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
