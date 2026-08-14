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
        <h2 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Your font is ready
        </h2>
        <p className="mt-2 max-w-xl text-zinc-600 dark:text-zinc-400">
          Download the <strong>{familyName}</strong> package — it includes the font in both
          formats, a preview image and PDF, your individual glyphs, and a README with install
          instructions.
        </p>
      </div>

      <a
        href={downloadUrl(jobId, "zip")}
        className="w-fit rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
      >
        Download .zip package
      </a>

      <div className="flex flex-col gap-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Individual files</p>
        <div className="flex flex-wrap gap-3 text-sm">
          <a
            href={downloadUrl(jobId, "ttf")}
            className="rounded-full border border-zinc-300 px-4 py-2 font-medium text-zinc-900 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-800"
          >
            .ttf
          </a>
          <a
            href={downloadUrl(jobId, "otf")}
            className="rounded-full border border-zinc-300 px-4 py-2 font-medium text-zinc-900 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-800"
          >
            .otf
          </a>
          <a
            href={previewUrl(jobId, "png")}
            className="rounded-full border border-zinc-300 px-4 py-2 font-medium text-zinc-900 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-800"
          >
            preview.png
          </a>
          <a
            href={previewUrl(jobId, "pdf")}
            className="rounded-full border border-zinc-300 px-4 py-2 font-medium text-zinc-900 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-800"
          >
            preview.pdf
          </a>
        </div>
      </div>

      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Install like any other font: double-click the .ttf or .otf file on macOS/Windows, or add
        it via your OS&apos;s font manager on Linux.
      </p>

      <button
        type="button"
        onClick={onRestart}
        className="w-fit text-sm font-medium text-zinc-500 underline-offset-2 hover:underline dark:text-zinc-400"
      >
        Start over with a new upload
      </button>
    </div>
  );
}
