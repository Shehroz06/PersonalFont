export type Step =
  | "home"
  | "template"
  | "upload"
  | "processing"
  | "review"
  | "preview"
  | "download";

const STEPS: { key: Step; label: string }[] = [
  { key: "home", label: "Home" },
  { key: "template", label: "Template" },
  { key: "upload", label: "Upload" },
  { key: "processing", label: "Processing" },
  { key: "review", label: "Review" },
  { key: "preview", label: "Preview" },
  { key: "download", label: "Download" },
];

export default function StepIndicator({ current }: { current: Step }) {
  const currentIndex = STEPS.findIndex((s) => s.key === current);

  return (
    <ol className="flex w-full flex-wrap items-center gap-x-1 gap-y-2 text-sm">
      {STEPS.map((step, index) => {
        const isCurrent = index === currentIndex;
        const isDone = index < currentIndex;
        return (
          <li key={step.key} className="flex items-center gap-1">
            <span
              className={`flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-xs font-medium ${
                isCurrent
                  ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : isDone
                    ? "bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200"
                    : "bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500"
              }`}
            >
              {index + 1}
            </span>
            <span
              className={
                isCurrent
                  ? "font-medium text-zinc-900 dark:text-zinc-100"
                  : "text-zinc-500 dark:text-zinc-400"
              }
            >
              {step.label}
            </span>
            {index < STEPS.length - 1 && (
              <span className="mx-1 text-zinc-300 dark:text-zinc-600">&rarr;</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
