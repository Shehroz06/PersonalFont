export type Step =
  | "home"
  | "template"
  | "upload"
  | "freeform-upload"
  | "processing"
  | "freeform-processing"
  | "review"
  | "rewrite"
  | "rewrite-processing"
  | "exclude-processing"
  | "preview"
  | "download";

// Steps that don't get their own slot in the indicator (freeform upload
// is a variant of "upload"; rewriting/excluding are loops back onto
// "review", not a forward step) map onto the nearest one that does, so
// the indicator always shows something sensible instead of nothing
// highlighted.
const DISPLAY_STEP: Partial<Record<Step, Step>> = {
  "freeform-upload": "upload",
  "freeform-processing": "processing",
  rewrite: "review",
  "rewrite-processing": "review",
  "exclude-processing": "review",
};

const STEPS: { key: Step; label: string }[] = [
  { key: "template", label: "Template" },
  { key: "upload", label: "Upload" },
  { key: "processing", label: "Processing" },
  { key: "review", label: "Review" },
  { key: "preview", label: "Preview" },
  { key: "download", label: "Download" },
];

export default function StepIndicator({ current }: { current: Step }) {
  const displayed = DISPLAY_STEP[current] ?? current;
  const currentIndex = STEPS.findIndex((s) => s.key === displayed);

  return (
    <ol className="flex flex-wrap items-center justify-center gap-x-1 gap-y-2 text-sm">
      {STEPS.map((step, index) => {
        const isCurrent = index === currentIndex;
        const isDone = index < currentIndex;
        return (
          <li key={step.key} className="flex items-center gap-1">
            <span
              className={`flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-xs font-medium ${
                isCurrent
                  ? "bg-violet-700 text-white dark:bg-violet-500 dark:text-stone-950"
                  : isDone
                    ? "bg-stone-200 text-stone-700 dark:bg-stone-700 dark:text-stone-200"
                    : "bg-stone-100 text-stone-400 dark:bg-stone-800 dark:text-stone-500"
              }`}
            >
              {index + 1}
            </span>
            <span
              className={
                isCurrent
                  ? "font-medium text-stone-900 dark:text-stone-100"
                  : "text-stone-500 dark:text-stone-400"
              }
            >
              {step.label}
            </span>
            {index < STEPS.length - 1 && (
              <span className="mx-1 text-stone-300 dark:text-stone-600">&rarr;</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
