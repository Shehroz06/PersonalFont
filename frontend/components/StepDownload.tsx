import { downloadUrl, previewUrl } from "@/lib/api";

export default function StepDownload({
  jobId,
  familyName,
  onRestart,
}: {
  jobId: string;
  familyName: string;
  onRestart: () => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-50">
          Your font is ready
        </h2>
        <p className="mt-2 max-w-xl text-stone-600 dark:text-stone-400">
          Download the <strong>{familyName}</strong> package. It includes the font in both
          formats, a preview image and PDF, your individual glyphs, and a README with install
          instructions.
        </p>
      </div>

      <a
        href={downloadUrl(jobId, "zip")}
        className="w-fit rounded-full bg-violet-700 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-violet-600 dark:bg-violet-500 dark:text-stone-950 dark:hover:bg-violet-400"
      >
        Download .zip package
      </a>

      <div className="flex flex-col gap-3 rounded-lg border border-stone-200 p-4 dark:border-stone-800">
        <p className="text-sm font-medium text-stone-700 dark:text-stone-300">Individual files</p>
        <div className="flex flex-wrap gap-3 text-sm">
          <a
            href={downloadUrl(jobId, "ttf")}
            className="rounded-full border border-stone-300 px-4 py-2 font-medium text-stone-900 transition-colors hover:bg-stone-100 dark:border-stone-700 dark:text-stone-100 dark:hover:bg-stone-800"
          >
            .ttf
          </a>
          <a
            href={downloadUrl(jobId, "otf")}
            className="rounded-full border border-stone-300 px-4 py-2 font-medium text-stone-900 transition-colors hover:bg-stone-100 dark:border-stone-700 dark:text-stone-100 dark:hover:bg-stone-800"
          >
            .otf
          </a>
          <a
            href={previewUrl(jobId, "png")}
            className="rounded-full border border-stone-300 px-4 py-2 font-medium text-stone-900 transition-colors hover:bg-stone-100 dark:border-stone-700 dark:text-stone-100 dark:hover:bg-stone-800"
          >
            preview.png
          </a>
          <a
            href={previewUrl(jobId, "pdf")}
            className="rounded-full border border-stone-300 px-4 py-2 font-medium text-stone-900 transition-colors hover:bg-stone-100 dark:border-stone-700 dark:text-stone-100 dark:hover:bg-stone-800"
          >
            preview.pdf
          </a>
        </div>
      </div>

      <p className="text-sm text-stone-500 dark:text-stone-400">
        Install like any other font: double-click the .ttf or .otf file on macOS/Windows, or add
        it via your OS&apos;s font manager on Linux.
      </p>

      <button
        type="button"
        onClick={onRestart}
        className="w-fit text-sm font-medium text-stone-500 underline-offset-2 hover:underline dark:text-stone-400"
      >
        Start over with a new upload
      </button>
    </div>
  );
}
