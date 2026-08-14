# PersonalFont — Architecture & Progress

Source specs: `Initial_project_prompt.txt`, `Project_spec.txt`, `Functional_requirements.txt`, `Non_Functional_requirements`.

## Development order (from Initial_project_prompt.txt §21)

| Phase | Description | Status |
|---|---|---|
| 1 | Project scaffolding | done |
| 2 | Template generation + template JSON | done |
| 3 | Image preprocessing | done |
| 4 | Template alignment | done |
| 5 | Character extraction | done |
| 6 | Character validation | done |
| 7 | Glyph normalization | done |
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

## Phase 5 design decisions

**Glyph filenames use `character_id`, not the raw character.** The spec's example (`A.png`) is illustrative, not literal: several punctuation characters in the V1 set (`"`, `:`, `?`) are invalid in Windows paths, and `A.png`/`a.png` collide on case-insensitive filesystems (macOS, Windows — a real risk since jobs may run cross-platform). `character_id` (e.g. `uppercase_A`, `punctuation_colon`) is already the template's stable, unique, filesystem-safe identifier for each glyph — reusing it avoids inventing a second naming scheme, and keeps every stage referring to glyphs the same way.

**Extraction confidence is inherited from alignment, not recomputed.** `extract_glyphs` takes `extraction_confidence` as a parameter (the caller passes `AlignmentResult.confidence`) rather than deriving its own score — a crop's *location* is only as trustworthy as the homography that produced the image it's cropped from. Content-based quality (empty box, noise, multiple components, touching the crop boundary) is deliberately left to Phase 6 validation, which looks at pixels, not geometry.

**Fixed padding around each template box** (`SegmentationConfig.padding_px`, default 6px): handwriting routinely overflows its printed guide box (ascenders, wide flourishes), so cropping to the box's exact bounds would clip real strokes. A crop that ends up touching its own boundary because of this is a signal for Phase 6 to flag, not something this stage should try to avoid by guessing at content.

**A crop that lands entirely outside the aligned image raises `SegmentationError`** rather than being silently skipped or returning an empty image (spec §16: never silently discard a failed glyph) — in practice this means alignment went wrong in a way its own confidence check didn't catch, and the caller should be told which character and page, not just that "processing failed."

**`app/services/jobs.py`** introduces the per-job directory layout from spec §15 (`uploads/processed/glyphs/svg/font/preview/logs`) now, since extraction is the first stage that actually writes job-scoped files to disk. `job_id` is restricted to uuid4-hex and validated before ever being joined into a path (`resolve_job_paths` raises `ValueError` on anything else), closing off path-traversal via a crafted id (spec §18). This module intentionally does *not* track job status/lifecycle — that's the API layer's job (Phase 11); here it's just safe path resolution.

## Verified — Phase 5

- `backend/tests/test_segmentation.py` (6 tests) and `backend/tests/test_jobs.py` (12 tests, incl. parametrized invalid-id cases) — 56 total tests passing across the whole suite. Covers: one file per element with correct metadata, character_id-based filenames (explicitly asserting the raw-character filename is *not* used), crop content correctness, padding behavior, the out-of-bounds `SegmentationError` path, an align→extract integration test, and job-id validation/isolation including a path-traversal attempt. Synthetic fixtures in `tests/segmentation_helpers.py` (built on `tests/alignment_helpers.py`).
- Manually ran the real `template_v1.json` through align → extract on the same simulated rotated/noisy photo used for the Phase 4 manual check: all 56 characters on page 1 extracted into an isolated job directory (`jobs/{uuid}/glyphs/`), and visually confirmed a sample crop (`uppercase_A.png`) is a clean, correctly-boxed glyph.

## Phase 6 design decisions

**Checks score 0-1, not just pass/fail.** Each rule in `rules.py` (`check_foreground_ratio`, `check_glyph_size`, `check_touches_boundary`, `check_component_count`) returns a continuous score plus an optional warning string, rather than a boolean. `validate_glyph` combines the scores multiplicatively into the glyph's `confidence` — this is what lets the spec §8 example numbers (0.97, 0.31) arise naturally: one check being noticeably off drags confidence down proportionally, while several checks being individually fine multiply to something less than a flat 1.0, matching real photographed handwriting instead of a binary "good/bad" split.

**Warnings and confidence are decoupled by a threshold** (`warning_score_threshold`, default 0.85): a score dipping slightly below 1.0 lowers confidence without being reported as a distinct problem; a check scoring below the threshold both lowers confidence *and* is named in `warnings`. Without this split, a glyph scoring e.g. 0.97 could never have an empty `warnings` list (any imperfection would immediately produce a warning message), which contradicts the spec's own valid-glyph example.

**Component-count expectations are character-specific.** Most of the V1 character set is expected to be a single connected ink stroke (even a crossed "t" or "x" — the crossing strokes touch and merge into one component), but `i`, `j`, `:`, `;`, and `"` legitimately split into two. `expected_component_range()` in `rules.py` encodes this; not accounting for it would systematically penalize otherwise-correct handwriting for these five characters.

**Consistent ink=255/background=0 input.** Every rule assumes the binary convention established in `pipeline.preprocessing.thresholding` (documented in `validate.py`'s module docstring) — validation is meant to run on the deskewed binary crop produced by extraction, not a raw grayscale scan. Feeding it the wrong convention isn't silently "handled"; it correctly (if uselessly) reports the image as excessive noise, since an inverted image reads as almost entirely foreground — verified manually (see below) rather than assumed.

**One glyph can never fail the batch** (spec §8/§16/NFR-06): `validate_glyphs` wraps each glyph's read-and-score in a `try/except`, converting any failure (corrupt file, missing file) into an invalid `ValidationResult` with an explanatory warning instead of letting the exception propagate and abort the whole job.

**Page-level checks ("invalid page", "incorrect template") are not reimplemented here.** They're already handled by Phase 4's `AlignmentError` (wrong template/page, insufficient markers) — spec §8 lists them alongside the glyph-level checks, but duplicating that logic in validation would just be two places disagreeing about the same failure mode.

## Verified — Phase 6

- `backend/tests/test_validation.py` (18 tests, 74 total across the suite): each rule tested in isolation against purpose-built synthetic crops (`tests/validation_helpers.py` — clean stroke, blank, sparse dot, noise, boundary-touching, two-dot), `validate_glyph` tested end-to-end for the valid case (no warnings, high confidence) and each invalid case, and `validate_glyphs` tested for the mixed-batch and unreadable-file paths without raising.
- Manually confirmed the ink-convention dependency behaves correctly both ways: feeding raw (non-thresholded) grayscale crops from the real Phase 5 extraction run correctly produces "excessive noise" (inverted convention reads background as foreground); feeding the same crop through `binarize_otsu` first produces a sensible result (flags the printed guide box/letter outline as touching-boundary and multi-component, which is accurate — it's a printed guide, not handwriting).

## Phase 7 design decisions

**A shared baseline, not just per-glyph bottom-alignment.** Naively cropping and centering each glyph independently (e.g. scaling every glyph's bounding box to the same height and bottom-aligning it) would make "p" sit on the same line as "A" incorrectly — "p" should hang below the line its neighbors sit on. `app.template_gen.character_set` gains a deliberately simple V1 classification (`is_tall_glyph`, `is_descender`): most of the set is bucketed into "tall" (cap-height: uppercase, digits, ascender lowercase like b/d/f/h/i/j/k/l/t, and tall punctuation like brackets/parens/quotes) or "short" (x-height: the remaining lowercase and punctuation), plus a separate descender flag (g/j/p/q/y, and comma's tail) that reserves extra room below the baseline. This is explicitly *not* per-glyph stroke analysis or real font metrics — it's the minimum classification needed for the rendered font's baseline to look coherent, and is called out as a known simplification future phases (e.g. Phase 14's handwriting engine integration) could refine.

**Normalization outputs a fixed-size canvas bitmap** (`NormalizationConfig`, default 500×500px) rather than just a scaled crop — this is the "consistent font metrics" requirement from spec §9: every glyph shares one coordinate space (canvas size + baseline position) that Phase 8 (vectorization) and Phase 9 (font generation) can both rely on without re-deriving it.

**Scale is bounded by whichever dimension is tighter** (height-class target vs. horizontal margin), preserving aspect ratio exactly rather than stretching to fill a fixed box — directly satisfying spec §9's "preserve aspect ratio" and "do not distort glyphs unnecessarily." Interpolation switches between `INTER_CUBIC` (upsampling — the common case, since crops are typically much smaller than the 500px canvas) and `INTER_AREA` (downsampling), and the result is re-binarized after resizing to keep the ink=255/background=0 convention strict for vectorization.

**`normalize_glyphs` only processes glyphs Phase 6 marked valid**, silently excluding invalid ones from its own output — this is not the "silently discard a failed glyph" spec §16 warns against, since Phase 6 already surfaced them (with warnings) for the user to rewrite; they simply don't advance further. A failure reading an *already-validated* glyph's file, or an unrecognized `character_id`, is treated differently — those raise `NormalizationError`, since at that point the failure indicates a system-level problem, not ordinary bad handwriting data.

## Verified — Phase 7

- `backend/tests/test_normalization.py` (12 tests, 86 total across the suite): canvas sizing, aspect-ratio preservation, tall-vs-short height classes (incl. ascender lowercase matching cap-height), baseline alignment for non-descenders, descender extension below baseline, horizontal centering, output stays strictly binary after resampling, the empty-glyph error path, and `normalize_glyphs` batch behavior (valid-only filtering, unknown character_id, unreadable image).
- Manually rendered normalized synthetic letters ("A", "a", "g", "b") drawn as actual letterforms (not just rectangles) side by side and visually confirmed: "A" and "b" (ascender) reach the same cap-height, "a" sits shorter at x-height, all three bottoms align to one shared baseline, and "g" correctly descends below it.
