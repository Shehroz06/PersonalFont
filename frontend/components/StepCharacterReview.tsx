"use client";

import { useState } from "react";
import { ApiError, excludeCharacters } from "@/lib/api";
import type { ValidationResult } from "@/lib/types";

// The backend's ValidationResult is binary (valid/invalid) with warnings
// attached to the invalid case (see pipeline/validation/validate.py). It
// never marks a *valid* glyph with warnings. Spec §16 asks the UI for
// three states (✓ valid / ⚠ warning / ✗ invalid), so the middle state is
// derived here rather than by changing the backend's model: a totally
// unwritten box ("Empty glyph", the box was genuinely left blank) reads
// as a hard miss (✗), while anything with *some* ink that still failed a
// check (small, noisy, wrong stroke count, ...) reads as needing another
// look (⚠) rather than a flat failure.
//
// This has to key off the actual "Empty glyph" warning text, not
// confidence === 0: confidence is a *product* of several check scores
// (pipeline/validation/validate.py), so a severely undersized glyph can
// round that product to exactly 0 even though ink was genuinely found,
// which used to land it in "missing" (red) purely by rounding
// coincidence while a slightly-less-tiny glyph with the identical
// problem landed in "warning" (orange) instead.
type ReviewStatus = "valid" | "warning" | "missing";

function classify(result: ValidationResult): ReviewStatus {
  if (result.valid) return "valid";
  const isBlank = result.warnings.some((w) => w.toLowerCase().startsWith("empty glyph"));
  return isBlank ? "missing" : "warning";
}

const STATUS_STYLES: Record<ReviewStatus, { icon: string; classes: string }> = {
  valid: {
    icon: "✓",
    classes: "border-green-300 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-300",
  },
  warning: {
    icon: "⚠",
    classes:
      "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300",
  },
  missing: {
    icon: "✗",
    classes: "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-300",
  },
};

// A viewer can mark any character (even a valid one) to be left out of
// the font on purpose — bad stroke layering, a shape they just don't
// like, whatever. This is a local, not-yet-submitted selection; it gets
// its own bright yellow flag look so it reads as "you chose this"
// rather than colliding with the amber/red validation states above.
const PENDING_EXCLUDE_CLASSES =
  "border-yellow-400 bg-yellow-100 text-yellow-900 dark:border-yellow-500 dark:bg-yellow-950 dark:text-yellow-300";

export default function StepCharacterReview({
  jobId,
  validations,
  onContinue,
  onBack,
  onRewrite,
  onExcluded,
}: {
  jobId: string;
  validations: ValidationResult[];
  onContinue: () => void;
  onBack: () => void;
  onRewrite: () => void;
  onExcluded: () => void;
}) {
  const [pendingExclusions, setPendingExclusions] = useState<Set<string>>(new Set());
  const [excluding, setExcluding] = useState(false);
  const [excludeError, setExcludeError] = useState<string | null>(null);

  const counts = validations.reduce(
    (acc, v) => {
      acc[classify(v)] += 1;
      return acc;
    },
    { valid: 0, warning: 0, missing: 0 } as Record<ReviewStatus, number>,
  );

  function toggleExclude(characterId: string) {
    setPendingExclusions((prev) => {
      const next = new Set(prev);
      if (next.has(characterId)) {
        next.delete(characterId);
      } else {
        next.add(characterId);
      }
      return next;
    });
  }

  async function handleContinue() {
    if (pendingExclusions.size === 0) {
      onContinue();
      return;
    }
    setExcluding(true);
    setExcludeError(null);
    try {
      await excludeCharacters(jobId, Array.from(pendingExclusions));
      onExcluded();
    } catch (err) {
      setExcludeError(err instanceof ApiError ? err.message : "Could not exclude those characters.");
    } finally {
      setExcluding(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-50">
          Review your characters
        </h2>
        <p className="mt-2 max-w-xl text-stone-600 dark:text-stone-400">
          {counts.valid} valid, {counts.warning} flagged, {counts.missing} missing. Only valid
          characters are included in your font.
        </p>
        {counts.warning + counts.missing > 0 && (
          <p className="mt-1 max-w-xl text-sm text-stone-500 dark:text-stone-400">
            You can fix the rest without reprinting anything. Write just the flagged characters
            on plain paper and upload a photo.
          </p>
        )}
      </div>

      {excludeError && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {excludeError}
        </p>
      )}

      <div className="mt-6 grid grid-cols-[repeat(auto-fill,minmax(76px,1fr))] gap-2">
        {validations.map((result) => {
          const status = classify(result);
          const style = STATUS_STYLES[status];
          const isPendingExclude = pendingExclusions.has(result.character_id);
          const detail = isPendingExclude
            ? "Marked to leave out of the font"
            : result.warnings.join("; ") || `Confidence ${result.confidence.toFixed(2)}`;
          // A character that's already invalid is already left out of the
          // font — offering an "exclude" toggle on it too would be a
          // meaningless no-op that just confuses "excluded on purpose"
          // with "already failed validation". Only a valid character has
          // anything for this toggle to actually change.
          const canExclude = status === "valid";
          return (
            <button
              key={result.character_id}
              type="button"
              onClick={canExclude ? () => toggleExclude(result.character_id) : undefined}
              className={`group relative flex flex-col items-center gap-1 rounded-lg border px-2 py-3 outline-none transition-colors ${
                canExclude ? "cursor-pointer" : "cursor-default"
              } ${isPendingExclude ? PENDING_EXCLUDE_CLASSES : style.classes}`}
            >
              <span className="text-lg font-medium leading-none">{result.character}</span>
              <span aria-hidden className="text-xs leading-none">
                {isPendingExclude ? "⊘" : style.icon}
              </span>
              {(status !== "valid" || isPendingExclude) && (
                <div
                  role="tooltip"
                  className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 w-max max-w-48 -translate-x-1/2 rounded-lg bg-stone-900 px-3 py-2 text-center text-xs font-normal text-stone-50 opacity-0 shadow-lg transition-opacity duration-100 group-hover:opacity-100 group-focus:opacity-100 dark:bg-stone-100 dark:text-stone-900"
                >
                  {detail}
                  <div className="absolute top-full left-1/2 -mt-1 h-2 w-2 -translate-x-1/2 rotate-45 bg-stone-900 dark:bg-stone-100" />
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onBack}
          disabled={excluding}
          className="rounded-full px-5 py-2.5 text-sm font-medium text-stone-600 hover:bg-stone-100 disabled:opacity-50 dark:text-stone-400 dark:hover:bg-stone-800"
        >
          Upload more / different pages
        </button>
        {counts.warning + counts.missing > 0 && (
          <button
            type="button"
            onClick={onRewrite}
            disabled={excluding}
            className="rounded-full border border-stone-300 px-5 py-2.5 text-sm font-medium text-stone-900 transition-colors hover:bg-stone-100 disabled:opacity-50 dark:border-stone-700 dark:text-stone-100 dark:hover:bg-stone-800"
          >
            Rewrite flagged characters
          </button>
        )}
        <button
          type="button"
          onClick={handleContinue}
          disabled={counts.valid === 0 || excluding}
          className="rounded-full bg-violet-700 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:bg-violet-100 disabled:text-violet-400 dark:bg-violet-500 dark:text-stone-950 dark:hover:bg-violet-400 dark:disabled:bg-violet-950 dark:disabled:text-violet-600"
        >
          {excluding ? "Rebuilding..." : "Continue to preview"}
        </button>
      </div>
    </div>
  );
}
