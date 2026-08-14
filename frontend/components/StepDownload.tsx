import { downloadUrl } from "@/lib/api";

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
          Download <strong>{familyName}</strong> as a TTF or OTF file, then install it like any
          other font (double-click the file on macOS/Windows, or add it via your OS&apos;s font
          manager).
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <a
          href={downloadUrl(jobId, "ttf")}
          className="rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Download .ttf
        </a>
        <a
          href={downloadUrl(jobId, "otf")}
          className="rounded-full border border-zinc-300 px-6 py-3 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-800"
        >
          Download .otf
        </a>
      </div>

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
