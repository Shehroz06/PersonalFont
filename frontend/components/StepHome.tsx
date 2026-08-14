export default function StepHome({ onStart }: { onStart: () => void }) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Turn your handwriting into a font
        </h1>
        <p className="mt-3 max-w-xl text-zinc-600 dark:text-zinc-400">
          Print a template, write on it, photograph the pages, and PersonalFont will build a
          real, installable TTF/OTF font from your own handwriting.
        </p>
      </div>

      <ol className="flex flex-col gap-2 text-sm text-zinc-600 dark:text-zinc-400">
        <li>1. Download and print the handwriting template.</li>
        <li>2. Fill it in and photograph each page.</li>
        <li>3. Upload the photos — we align, extract, and check each character.</li>
        <li>4. Review any characters that need a rewrite.</li>
        <li>5. Preview your font, then download it.</li>
      </ol>

      <p className="max-w-xl text-sm text-zinc-500 dark:text-zinc-500">
        V1 uses a deterministic image-processing pipeline — no generative AI is used to invent
        or fix glyphs. What you write is what you get.
      </p>

      <button
        type="button"
        onClick={onStart}
        className="w-fit rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
      >
        Get started
      </button>
    </div>
  );
}
