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
        // no-store: this job's font can be rebuilt (rewrite, exclude) while
        // the browser still has an HTTP cache entry for the same URL from
        // before the rebuild — without this, a stale font can silently load.
        const response = await fetch(downloadUrl(jobId, "ttf"), { cache: "no-store" });
        if (!response.ok) throw new Error("Could not download the generated font.");
        const blob = await response.blob();
        if (cancelled) return;

        objectUrl = URL.createObjectURL(blob);
        setFontUrl(objectUrl);

        const fontFace = new FontFace(PREVIEW_FAMILY, `url(${objectUrl})`);
        await fontFace.load();
        if (cancelled) return;

        // Revisiting this step (review -> preview -> back -> exclude ->
        // preview) re-mounts this component and re-registers a FontFace
        // under the same family name without ever removing the previous
        // one. document.fonts then holds multiple FontFace objects for
        // "PersonalFontPreview" at once, and the browser can still resolve
        // a character from an older one — so a glyph just excluded from
        // the rebuilt font can silently keep rendering from the stale
        // FontFace. Clear every prior registration for this family first.
        for (const face of document.fonts) {
          if (face.family === PREVIEW_FAMILY) {
            document.fonts.delete(face);
          }
        }
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
        <h2 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-50">
          Preview your font
        </h2>
        <p className="mt-2 max-w-xl text-stone-600 dark:text-stone-400">
          This is your real generated font, rendered directly in the browser.
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {!fontReady && !error && (
        <p className="text-sm text-stone-500 dark:text-stone-400">Loading font preview...</p>
      )}

      {fontReady && fontUrl && (
        <div className="flex flex-col gap-4 rounded-xl border border-stone-200 p-6 dark:border-stone-800">
          {SAMPLE_LINES.map((line) => (
            <p
              key={line}
              style={{ fontFamily: PREVIEW_FAMILY }}
              className="text-2xl leading-relaxed text-stone-900 dark:text-stone-50"
            >
              {line}
            </p>
          ))}
        </div>
      )}

      {fontReady && (
        <div className="flex flex-col gap-2">
          <label htmlFor="custom-preview" className="text-sm font-medium text-stone-700 dark:text-stone-300">
            Try your own text
          </label>
          <textarea
            id="custom-preview"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            rows={3}
            style={{ fontFamily: PREVIEW_FAMILY }}
            className="rounded-lg border border-stone-300 px-4 py-3 text-2xl dark:border-stone-700 dark:bg-stone-900"
          />
        </div>
      )}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          className="rounded-full px-5 py-2.5 text-sm font-medium text-stone-600 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onContinue}
          disabled={!fontReady}
          className="rounded-full bg-violet-700 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:bg-violet-100 disabled:text-violet-400 dark:bg-violet-500 dark:text-stone-950 dark:hover:bg-violet-400 dark:disabled:bg-violet-950 dark:disabled:text-violet-600"
        >
          Continue to download
        </button>
      </div>
    </div>
  );
}
