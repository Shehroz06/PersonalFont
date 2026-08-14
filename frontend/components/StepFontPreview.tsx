"use client";

import { useEffect, useState } from "react";
import { downloadUrl } from "@/lib/api";

const PREVIEW_FAMILY = "PersonalFontPreview";

const SAMPLE_LINES = [
  "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
  "abcdefghijklmnopqrstuvwxyz",
  "0123456789",
  "The quick brown fox jumps over the lazy dog.",
];

export default function StepFontPreview({
  jobId,
  onContinue,
  onBack,
}: {
  jobId: string;
  onContinue: () => void;
  onBack: () => void;
}) {
  const [fontUrl, setFontUrl] = useState<string | null>(null);
  const [fontReady, setFontReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customText, setCustomText] = useState("Write anything to preview it here.");

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    async function loadFont() {
      try {
        const response = await fetch(downloadUrl(jobId, "ttf"));
        if (!response.ok) throw new Error("Could not download the generated font.");
        const blob = await response.blob();
        if (cancelled) return;

        objectUrl = URL.createObjectURL(blob);
        setFontUrl(objectUrl);

        const fontFace = new FontFace(PREVIEW_FAMILY, `url(${objectUrl})`);
        await fontFace.load();
        if (cancelled) return;
        document.fonts.add(fontFace);
        setFontReady(true);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load the font preview.");
        }
      }
    }

    loadFont();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [jobId]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Preview your font
        </h2>
        <p className="mt-2 max-w-xl text-zinc-600 dark:text-zinc-400">
          This is your real generated font, rendered directly in the browser.
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {!fontReady && !error && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading font preview...</p>
      )}

      {fontReady && fontUrl && (
        <div className="flex flex-col gap-4 rounded-xl border border-zinc-200 p-6 dark:border-zinc-800">
          {SAMPLE_LINES.map((line) => (
            <p
              key={line}
              style={{ fontFamily: PREVIEW_FAMILY }}
              className="text-2xl leading-relaxed text-zinc-900 dark:text-zinc-50"
            >
              {line}
            </p>
          ))}
        </div>
      )}

      {fontReady && (
        <div className="flex flex-col gap-2">
          <label htmlFor="custom-preview" className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Try your own text
          </label>
          <textarea
            id="custom-preview"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            rows={3}
            style={{ fontFamily: PREVIEW_FAMILY }}
            className="rounded-lg border border-zinc-300 px-4 py-3 text-2xl dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-full px-5 py-2.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onContinue}
          disabled={!fontReady}
          className="rounded-full bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        >
          Continue to download
        </button>
      </div>
    </div>
  );
}
