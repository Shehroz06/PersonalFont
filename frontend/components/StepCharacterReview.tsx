import type { ValidationResult } from "@/lib/types";

// The backend's ValidationResult is binary (valid/invalid) with warnings
// attached to the invalid case (see pipeline/validation/validate.py) — it
// never marks a *valid* glyph with warnings. Spec §16 asks the UI for
// three states (✓ valid / ⚠ warning / ✗ invalid), so the middle state is
// derived here rather than by changing the backend's model: a totally
// unwritten box (zero confidence, "empty glyph") reads as a hard miss
// (✗), while anything with *some* ink that still failed a check (small,
// noisy, wrong stroke count, ...) reads as needing another look (⚠)
// rather than a flat failure.
type ReviewStatus = "valid" | "warning" | "missing";

function classify(result: ValidationResult): ReviewStatus {
  if (result.valid) return "valid";
  return result.confidence > 0 ? "warning" : "missing";
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

export default function StepCharacterReview({
  validations,
  onContinue,
  onBack,
}: {
  validations: ValidationResult[];
  onContinue: () => void;
  onBack: () => void;
}) {
  const counts = validations.reduce(
    (acc, v) => {
      acc[classify(v)] += 1;
      return acc;
    },
    { valid: 0, warning: 0, missing: 0 } as Record<ReviewStatus, number>,
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Review your characters
        </h2>
        <p className="mt-2 max-w-xl text-zinc-600 dark:text-zinc-400">
          {counts.valid} valid, {counts.warning} need a closer look, {counts.missing} missing or
          unreadable. Only valid characters are included in your font — go back and re-upload a
          clearer photo for any page with characters that need attention.
        </p>
      </div>

      <div className="grid grid-cols-[repeat(auto-fill,minmax(76px,1fr))] gap-2">
        {validations.map((result) => {
          const status = classify(result);
          const style = STATUS_STYLES[status];
          return (
            <div
              key={result.character_id}
              title={result.warnings.join("; ") || `Confidence ${result.confidence.toFixed(2)}`}
              className={`flex flex-col items-center gap-1 rounded-lg border px-2 py-3 ${style.classes}`}
            >
              <span className="text-lg font-medium leading-none">{result.character}</span>
              <span aria-hidden className="text-xs leading-none">
                {style.icon}
              </span>
            </div>
          );
        })}
      </div>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-full px-5 py-2.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
        >
          Upload more / different pages
        </button>
        <button
          type="button"
          onClick={onContinue}
          disabled={counts.valid === 0}
          className="rounded-full bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Continue to preview
        </button>
      </div>
    </div>
  );
}
