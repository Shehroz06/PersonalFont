export default function StepHome({
  onStartTemplate,
  onStartFreeform,
}: {
  onStartTemplate: () => void;
  onStartFreeform: () => void;
}) {
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-stone-900 dark:text-stone-50">
          Turn your handwriting into a font
        </h1>
        <p className="mt-3 max-w-xl text-stone-600 dark:text-stone-400">
          Write your characters, photograph the page, and PersonalFont builds a real, installable
          TTF/OTF font from your own handwriting. No generative AI, no invented glyphs. What you
          write is what you get.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-3 rounded-xl border border-stone-200 p-5 dark:border-stone-800">
          <div>
            <p className="text-sm font-medium text-stone-900 dark:text-stone-50">Plain paper</p>
            <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
              No print needed. Write every character on any blank sheet, in the order we show
              you, and photograph it. The fastest way to start, and how most people use this.
            </p>
          </div>
          <button
            type="button"
            onClick={onStartFreeform}
            className="mt-auto w-fit rounded-full bg-violet-700 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-600 dark:bg-violet-500 dark:text-stone-950 dark:hover:bg-violet-400"
          >
            Write freeform
          </button>
        </div>

        <div className="flex flex-col gap-3 rounded-xl border border-stone-200 p-5 dark:border-stone-800">
          <div>
            <p className="text-sm font-medium text-stone-900 dark:text-stone-50">Printed template</p>
            <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
              Download a guided PDF with one box per character, print it, fill it in, and
              photograph each page. A bit more structure if you&apos;d rather have guide boxes.
            </p>
          </div>
          <button
            type="button"
            onClick={onStartTemplate}
            className="mt-auto w-fit rounded-full border border-violet-300 px-5 py-2.5 text-sm font-medium text-violet-700 transition-colors hover:bg-violet-50 dark:border-violet-700 dark:text-violet-300 dark:hover:bg-violet-950"
          >
            Use a template
          </button>
        </div>
      </div>

      <p className="max-w-xl text-sm text-stone-500 dark:text-stone-500">
        Either way, if a character doesn&apos;t come out clearly you can rewrite just that one on
        plain paper afterward. No need to redo everything.
      </p>
    </div>
  );
}
