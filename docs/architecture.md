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
| 8 | Bitmap → SVG | done |
| 9 | SVG → TTF/OTF | done |
| 10 | End-to-end CLI pipeline | done |
| 11 | FastAPI API | done |
| 12 | Frontend | done |
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

## Phase 8 design decisions

**Uses potrace (via the pure-Python `potracer` package), not a hand-written tracer.** Project_spec.txt is explicit: use an established bitmap-to-vector approach rather than writing a Bezier-tracing algorithm from scratch. `potracer` reimplements the well-known Potrace algorithm in pure Python — no C extension or system library dependency (unlike `pypotrace`, which needs libpotrace/libagg), which matters for keeping the stack "boring and reliable" per the spec's own tech-stack guidance. `opticurve`/`alphamax`/`opttolerance` (exposed via `VectorizationConfig`) are what directly satisfy spec §10's "clean contours, smooth paths, avoid excessive nodes."

**potrace inverts internally — confirmed empirically, not assumed.** `potrace.Bitmap.__init__` unconditionally calls `self.invert()` on whatever array it's given. Rather than trust the docs, I traced a known shape, got an unrecognizable result, and worked backward: passing `image == 0` (i.e. pre-inverting so ink=255 pixels are `False`, which the library's own invert then flips to the traced/`True` side) is what makes the ink=255/background=0 convention this pipeline uses actually get traced. This is called out explicitly in `trace.py`'s docstring so it doesn't get "fixed" back to the wrong-looking `image > 0` later.

**Holes are handled via `fill-rule="evenodd"` with multiple `M...Z` subpaths in one `<path>`**, not by treating each potrace contour as a separate shape — this is what makes counters (the enclosed white space in "o", "A", "e", "g", ...) render as actual holes rather than solid blobs. Verified by tracing a shape with a genuine hole and confirming exactly 2 subpaths, then rendering it (via `cairosvg`, used only for manual/local verification — not added as a project dependency) and visually confirming the hole punches through correctly.

**No coordinate flip between bitmap and SVG.** Both the source bitmap and SVG use top-left-origin, y-down coordinates, so pixel coordinates map to SVG user units 1:1 via a `viewBox="0 0 width height"` matching the source image's shape exactly — unlike the pt→px conversion in `app.template_gen.coordinates`, no y-axis flip is needed here. (Phase 9's font em-space *is* y-up, so that stage will need its own conversion — this module deliberately doesn't do it, keeping vectorization decoupled from font generation per spec §10.)

**Transparent background is structural, not configured** — the SVG only ever contains a `<path>` element; no background rect is drawn, so there's nothing to make transparent.

**Investigated visible jaggedness in an early manual check** on a synthetic 60-90px test shape (far smaller than a real extraction crop) and traced it to the low source resolution itself — cubic upsampling followed by re-binarization can only preserve a low-resolution shape's existing pixel staircase, not invent missing curve detail; disabling the re-binarization step made results *worse* (speckled), because it broke the strict ink=255/background=0 contract `bitmap_to_path_data` relies on. Re-tested at ~150-180px, matching what Phase 3's default 200 DPI actually produces from a template box, and confirmed the output is clean and smooth — the jaggedness was an artifact of an unrealistic test input, not a defect in the stage, but worth recording since it explains why `bitmap_to_path_data`'s docstring insists on the strict binary convention rather than accepting arbitrary grayscale.

## Verified — Phase 8

- `backend/tests/test_vectorization.py` (10 tests, 96 total across the suite): empty-glyph error, single-contour vs. hole-producing two-subpath shapes, a round-trip shape-fidelity check (custom test-only rasterizer, IoU > 0.9 against the original bitmap for a hole-free "L" shape), `opticurve` producing fewer-or-equal path nodes than with it disabled, well-formed/transparent SVG output, viewBox correctness, and `vectorize_glyphs` batch behavior (file creation, unreadable-image error).
- Manually chained normalization → vectorization → `cairosvg` rendering on synthetic letterforms ("A", "a", "g") and confirmed correct hole rendering (the "A"'s counter), and — after the resolution investigation above — clean, smooth curves at a realistic source resolution.

## Phase 9 design decisions

**Uses FontTools' `FontBuilder`**, per Project_spec.txt's tech-stack guidance (FontTools and/or FontForge) — no FontForge dependency (a system binary, harder to install reliably) needed for V1.

**One shared coordinate transform does the SVG→font-space conversion.** SVG/bitmap space is top-left-origin, y-down (see Phase 8); font em-space is baseline-origin, y-up. Rather than hand-editing path coordinates, `glyph_outline._baseline_transform` builds a single `fontTools.misc.transform.Transform(1,0,0,-1,x_shift,baseline_px)` applied via `TransformPen` — one matrix does the y-flip, the "bitmap row baseline_px is font y=0" translation, and (via `x_shift`) repositioning so each glyph's own ink starts at a consistent left side bearing.

**Advance widths are per-glyph, not fixed.** Phase 7 centers every glyph in the same fixed-size canvas, so naively using that canvas width as every glyph's advance would produce a monospace-looking font with large gaps around narrow letters. Instead, `compute_advance_and_transform` measures each glyph's own ink bounding box (via `BoundsPen`, run once before building the actual outline) and derives `advance_width = ink_width + 2*side_bearing`, then shifts the glyph so its ink starts at `x=left_side_bearing` — giving genuine proportional spacing, and giving the "advance width"/"side bearings" metrics spec §11 lists actual meaning rather than being trivially identical for every character.

**TTF uses `Cu2QuPen` to convert potrace's cubic curves to TrueType's quadratic ones**, with `reverse_direction=True` — required so contour winding survives the conversion correctly (TrueType/CFF use nonzero-winding fill, opposite convention sensitivity from SVG's evenodd). This wasn't assumed: I built a real font from a shape with a genuine hole (a triangular counter) and rendered it with PIL/FreeType to visually confirm the hole punches through correctly in the compiled glyph, not just in the intermediate SVG.

**Found and fixed a real cross-phase bug during end-to-end verification, not a unit test.** `pipeline/alignment/marker_detection.py` used ArUco's default `DetectorParameters()`, which only recognizes the standard dark-marker-on-light-background polarity. Every Phase 4/5 test (and the earlier manual checks) happened to use synthetic photos in that normal polarity — but per the spec's own stage order, alignment is meant to consume Phase 3's *already-thresholded* output, which is ink=255/background=0 (inverted). Chaining the real pipeline together for this phase's verification surfaced that `detect_markers` silently found nothing on that inverted convention. Fixed by setting `detectInvertedMarker = True`, verified empirically to be a strict superset (still detects normal-polarity markers, confirmed both ways with a raw `cv2.aruco` script before touching the module) — and added a regression test (`test_detect_markers_finds_markers_on_inverted_ink255_image`) plus loosened two precision-sensitive assertions that assumed the old (accidentally non-representative) detection precision. This is the clearest example so far of why chaining real modules together, not just each phase's isolated tests, matters.

## Verified — Phase 9

- `backend/tests/test_font_generation.py` (16 tests, 108 total across the suite, run from real normalize→vectorize output rather than hand-crafted SVGs): loadable TTF/OTF creation, `.notdef` presence, cmap correctness, default and custom `FontMetadata` (family name, version), proportional (non-fixed) advance widths, empty-glyph-list and missing-SVG error paths, and — genuine functional checks via PIL/FreeType rendering, not just structural ones — that both formats actually render visible ink, and specifically that the "A" glyph's triangular counter renders as background (the hole survived the SVG→TrueType winding conversion).
- **Full pipeline capstone check**: loaded the real `template_v1.json`, hand-drew "H", "E", "L", "O", "o" at their true template box positions plus the page's real ArUco markers directly in the ink=255 convention (i.e. simulating genuine Phase 3 output, not a Phase-4-style normal-polarity test photo), warped it to simulate a photographed page, and ran it through `align_page_to_template` → `extract_glyphs` → `validate_glyphs` → `normalize_glyphs` → `vectorize_glyphs` → `generate_fonts` unmodified. All 5 characters validated, normalized, vectorized, and compiled into a working font; rendering "HELLO" with it via PIL/FreeType produced a correct, legible word — the first time the full V1 deterministic pipeline ran end to end.

## Phase 10 design decisions

**`app/services/pipeline_runner.run_pipeline`** is the single orchestrator chaining every stage built in Phases 3-9 (upload → preprocess → align → extract → validate → normalize → vectorize → generate font) for one job. It's a *service*, not a pipeline stage — it owns job-directory lifecycle and cross-stage sequencing, but contains no image-processing logic of its own, mirroring the same "orchestrator only chains, stages do the work" split used within `pipeline.preprocessing.pipeline`.

**Resilience is layered, not just per-glyph.** Validation already tolerates one bad *glyph*; this phase applies the same principle one level up, to *pages*: `_process_page` catches `PreprocessingError`/`AlignmentError`/`SegmentationError` and records a failed `PageOutcome` instead of raising, so one bad photo in a multi-page upload doesn't sink an otherwise-good submission (generalizing NFR-06 beyond just characters). The job only raises `PipelineError` outright in the two cases where no font *could* result: every page failed, or no glyph anywhere passed validation — both checked explicitly rather than let a downstream stage fail confusingly (e.g. `generate_fonts` on an empty list).

**Duplicate character_ids across pages are resolved, not left ambiguous.** If the same page is uploaded twice (or, hypothetically, a future template revision reused a character_id across pages), `_deduplicate_glyphs` keeps the higher-confidence extraction and logs which was discarded — otherwise `generate_fonts` would receive two entries for the same glyph name/codepoint and silently let dict-overwrite semantics pick one arbitrarily.

**Structured logging matches spec NFR-10's event names exactly** (`JOB_CREATED`, `PAGE_PREPROCESSED`, `PAGE_ALIGNED`, `GLYPHS_EXTRACTED`, `VALIDATION_COMPLETED`, `FONT_GENERATED`, `JOB_COMPLETED`), written as JSON-lines to `jobs/{id}/logs/pipeline.log` via `app/services/job_logging.py`, plus `PAGE_FAILED`/`JOB_FAILED`/`DUPLICATE_GLYPH_DISCARDED` so failures are just as observable as successes — this is also the first Phase to actually populate the `logs/` directory defined back in Phase 5's job layout.

**Uploaded files are never trusted past the copy step** (spec §18): `_save_uploads` copies each input into `jobs/{id}/uploads/page_N.{ext}` under a generated name, and everything downstream operates on that copy — the original caller-supplied path/filename is never touched again.

**`scripts/run_pipeline.py`** is a thin CLI wrapper (argument parsing, human-readable progress/summary printing) around `run_pipeline` — no logic lives in the script itself, keeping the actual orchestration reusable by Phase 11's API without duplication.

## Verified — Phase 10

- **Required integration test** (spec §19, `backend/tests/test_integration.py`): sample page → preprocessing → alignment → segmentation → validation → normalization → SVG → TTF/OTF, and — deliberately, unlike every other phase's tests — starting from a *synthetic photograph in standard scan polarity* (white paper, black ink, noisy rotated background) rather than a pre-binarized shortcut, so it exercises real Phase 3 page detection/perspective correction/thresholding/deskew, not just the stages downstream of them. Confirms a real, loadable TTF and OTF are produced, per the spec's explicit requirement.
- `backend/tests/test_pipeline_runner.py` (7 tests, 116 total across the suite): empty input, every-page-fails, no-glyph-passes-validation (each raising `PipelineError`), one-bad-page-among-several (job still completes), duplicate-upload deduplication, upload filename safety, and structured log event coverage.
- **Manually ran the actual CLI** (`scripts/run_pipeline.py`) end to end against a synthetic photo: correct per-page/per-character console output (56 extracted, 4 valid with clear per-character warnings for the rest), a working TTF/OTF, and a well-formed JSON-lines log file with all seven expected events in order. Rendered "HOTL" with the resulting font via PIL/FreeType from a *different* synthetic run and confirmed it's correct and legible — real signal survived the full, un-shortcut pipeline a second time, independent of the integration test.

## Phase 11 design decisions

**Upload-saving was pulled out of `run_pipeline` and into `app/services/uploads.py`**, a refactor forced by the API's shape: pages arrive via one request (`POST /jobs/{id}/pages`) well before processing is triggered by another (`POST /jobs/{id}/process`), so validating/saving uploads can no longer be something `run_pipeline` does for you as its first step — it now only processes images already sitting in `job_paths.uploads`. The CLI adapted to call the same `save_local_page_file` helper explicitly before invoking `run_pipeline`, so upload validation (size limit, extension/content-type, safe generated filenames) is identical and shared between both entry points rather than duplicated. This touched Phase 10 code and tests, but was driven by a real architectural need the API surfaced, not scope creep.

**Processing runs via FastAPI's built-in `BackgroundTasks`**, not a task queue (Celery/RQ/etc.) — avoids an "unnecessary dependency" for what NFR-03's 30-60s target doesn't actually require, matching the tech stack's "boring and reliable" framing. The tradeoff (accepted for V1, documented rather than hidden): background tasks only run within the same process that received the request, so a multi-worker deployment needs sticky routing or a real queue later — fine for V1's single-process assumption.

**Job status is persisted to disk** (`jobs/{id}/status.json` via `app/services/job_status.py`), not kept in an in-memory dict — the obvious in-memory alternative would silently break the moment uvicorn runs more than one worker (each worker has its own memory; a status write in one worker wouldn't be visible from a status read handled by another), while a file on shared local storage is correct regardless of worker count. Validation results are similarly persisted (`jobs/{id}/validation.json` via `app/services/validation_store.py`) rather than returned only once and discarded, since `GET /validation` needs to serve them on demand, potentially long after the background task that produced them finished.

**Both `job_id` and `template_id` are validated before ever being joined into a filesystem path** (spec §18) — `job_id` already was (Phase 5's `resolve_job_paths`); `template_id` gained the same treatment now (`is_valid_template_id`, checked in both the templates routes and job creation) since this is the first phase where a template_id arrives from an untrusted HTTP request rather than a trusted local script argument.

**`/preview` was deliberately not implemented.** It's in the spec's suggested endpoint list, but preview *generation* is explicitly Phase 13's job — stubbing a route that returns nothing meaningful would be a half-finished implementation (dev rule: "no half-finished implementations"). `/download` *was* implemented despite ZIP packaging also being Phase 13's job, because it doesn't need to invent anything: the TTF/OTF files already exist on disk from Phase 9/10, so serving them directly via `FileResponse` is a real, working feature today, not a placeholder — it'll likely stay as a fallback even after Phase 13 adds full ZIP packaging.

**Verified two ways, deliberately**: `TestClient`-based tests confirm request/response contracts and — empirically, not assumed — that `BackgroundTasks` execute synchronously within the test client's request cycle (useful for testing, but not representative of a real deployment). A separate manual run against a *live* `uvicorn` server with `curl` confirmed the opposite and more realistic behavior: `/status` genuinely reads "processing" immediately after `/process` returns, only flipping to "completed" once the background task actually finishes — exactly the async behavior the design is meant to provide, which the in-process test client could not have exposed.

## Verified — Phase 11

- `backend/tests/test_uploads.py` (10 tests) for the extracted upload-validation service: size limits, content-type restrictions (incl. rejecting an "executable" content type), safe generated filenames ignoring the original, both the bytes-based (API) and local-file (CLI) code paths.
- `backend/tests/test_api.py` (19 tests, incl. 2 added alongside Phase 12 for the `/pdf` route below; 145 total across the suite) via FastAPI's `TestClient`: health check, template listing/retrieval (incl. a rejected path-traversal attempt in the template id), job creation (incl. unknown-template 404), page upload (incl. wrong content-type, unknown-job 404, rejected after processing has started), process-without-pages 409, unknown-job 404s across every job endpoint, validation/download correctly gated on job state, and a full create → upload → process → status → validation → download round trip that loads the downloaded bytes as a real font via FontTools and confirms the drawn characters are present.
- **Manual live-server verification** (separate from the test suite, using real `uvicorn` + `curl`, not `TestClient`): confirmed genuine asynchronous processing (`/status` reads "processing" immediately after `/process`, "completed" only once the background task finishes on its own schedule), and downloaded a real TTF over HTTP — verified with the `file` command as valid "TrueType Font data" with the correct family name, PostScript name, and creator metadata baked in.

## Phase 12 design decisions

**Next.js (App Router, TypeScript, Tailwind) via `create-next-app`**, per Project_spec.txt's tech-stack guidance. This Next.js version (16.3.1) ships an `AGENTS.md`/`CLAUDE.md` pair warning that it has breaking changes from older training data and pointing at bundled docs in `node_modules/next/dist/docs/` — read the relevant getting-started guides (server/client components, the Middleware→Proxy rename) before writing any App Router code, rather than assuming prior Next.js knowledge still applied.

**The wizard is a single client component tree**, not a page-per-step routed app — `app/page.tsx` owns all wizard state (current step, job id, uploaded files, font metadata, validation results) and renders one of seven step components under `components/`. This app has no server-side data needs (no secrets, no DB, nothing SSR would meaningfully improve — every request goes to the separately-running FastAPI backend), so there was nothing for the App Router's server-component split to buy here; a plain client-side state machine is simpler and matches "don't over-engineer the frontend."

**Character review's ✓/⚠/✗ three-state display is derived on the frontend, not added to the backend.** The backend's `ValidationResult` is binary (`valid`/`invalid` with warnings attached only to the invalid case — see Phase 6's design notes). Rather than change that model to add a real "warning" state, `StepCharacterReview.tsx` classifies purely from data already present: zero-confidence invalid (no ink at all) reads as missing (✗); non-zero-confidence invalid (something written but failed a check) reads as needing another look (⚠); valid reads as done (✓). This satisfies spec §16's three-icon requirement without touching validated, tested backend logic for a presentation-only need.

**Font preview renders the real generated font, not a placeholder.** `StepFontPreview.tsx` downloads the actual TTF from `/download`, registers it as a browser `FontFace` from a blob URL, and renders sample text (and user-typed text) with it directly — verified visually to render only the characters that are actually present in the font (others fall back to the system font per standard browser glyph-substitution behavior), which is a stronger, more honest preview than Phase 13's static preview image/PDF will be, and required no dependency on Phase 13 being done first.

**`/preview`'s backend route still doesn't exist** — deliberately, per the Phase 11 design note — so there's no corresponding frontend call for it; the in-browser `FontFace` preview above covers the same user need today.

**A real integration bug was found and fixed during manual browser testing, not assumed away.** Driving the app in an actual headless browser (Playwright, since `chromium-cli` wasn't available in this environment — see below) surfaced that the backend's CORS default only allowlisted `http://localhost:3000`, but this machine already had an unrelated dev server bound to port 3000, so Next.js's dev server — correctly, by its own design — fell back to 3001, which the backend then silently rejected with a CORS error the browser console would show but a curl-based smoke test never would have caught. Fixed by defaulting `PERSONALFONT_CORS_ORIGINS` to include both `:3000` and `:3001`, since this exact fallback is Next.js's normal, documented behavior whenever the default port is unavailable — not a one-off local quirk worth working around instead of fixing.

**Added `GET /api/templates/{id}/pdf`** (backend), serving the same file `scripts/generate_template.py` already writes to `templates/`, so the frontend's "Download template PDF" step (spec §16) has something real to link to — a small, directly-justified backend addition, not scope creep into Phase 13's packaging.

## Verified — Phase 12

- `npx tsc --noEmit`, `npm run lint`, and `npm run build` all pass clean with zero errors/warnings.
- **Full browser-driven walkthrough** using Playwright against real `uvicorn` + `next dev` servers (not mocked, not `TestClient`): Home → Template → Upload (real file input with the same synthetic photographed-page JPEG used in the Phase 9/10 manual checks) → Processing (polled to real completion) → Character Review → Font Preview → Download, with `console --errors` and HTTP 4xx/5xx response logging active throughout the run. Result: zero console errors, zero network errors, and a downloaded TTF verified with `file` as valid TrueType data carrying the family name entered in the UI.
- Screenshotted every step and visually confirmed: the step indicator tracks progress correctly; the character review grid renders the correct icon/color per character (✓ green for H/L/O/T, ⚠ amber for "I" — genuinely flagged too-small by validation, not staged — ✗ red for the rest); the font preview panel renders H/L/O/T in the actual hand-drawn glyphs while every other character correctly falls back to the system font, proving the live `FontFace` preview reflects the real font content rather than being a static mock.
- This session had no `chromium-cli` skill available, so Playwright was installed standalone (via `npx`, using an already-cached Chromium binary) and driven with a small one-off Node script rather than the bundled REPL — noted here rather than silently treated as equivalent, since a future session should still prefer `chromium-cli`/a project run-skill if one exists.
