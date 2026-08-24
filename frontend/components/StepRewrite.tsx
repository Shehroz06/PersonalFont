"use client";

import { useEffect, useState } from "react";
import { ApiError, getRewriteList, submitRewrite } from "@/lib/api";
import type { RewriteCharacter } from "@/lib/types";
import CharacterChecklist from "@/components/CharacterChecklist";
import PhotoDropzone from "@/components/PhotoDropzone";

export default function StepRewrite({
  jobId,
  onSubmitted,
  onBack,
}: {
  jobId: string;
  onSubmitted: () => void;
  onBack: () => void;
}) {
  const [characters, setCharacters] = useState<RewriteCharacter[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRewriteList(jobId)
      .then((response) => setCharacters(response.characters))
      .catch((err) => setListError(err instanceof ApiError ? err.message : "Could not load the rewrite list."));
  }, [jobId]);

  async function handleSubmit() {
    if (!file) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitRewrite(jobId, file);
      onSubmitted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit the rewrite photo.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-50">
          Rewrite the flagged characters
        </h2>
        <p className="mt-2 max-w-xl text-stone-600 dark:text-stone-400">
          No need to reprint the template. On a blank sheet of plain paper, write just these
          characters, in this exact order, with clear gaps between them, then photograph and
          upload it, evenly lit with no shadows across the page.
        </p>
      </div>

      {listError && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {listError}
        </p>
      )}
      {error && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {characters && characters.length === 0 && (
        <p className="text-sm text-stone-500 dark:text-stone-400">
          Nothing left to rewrite. Every character already passed validation.
        </p>
      )}

      {characters && characters.length > 0 && (
        <>
          <CharacterChecklist characters={characters} />
          <PhotoDropzone file={file} onFileChange={setFile} label="Drag your rewrite photo here, or click to choose it" />
        </>
      )}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          disabled={submitting}
          className="rounded-full px-5 py-2.5 text-sm font-medium text-stone-600 hover:bg-stone-100 disabled:opacity-50 dark:text-stone-400 dark:hover:bg-stone-800"
        >
          Back to review
        </button>
        {characters && characters.length > 0 && (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!file || submitting}
            className="rounded-full bg-violet-700 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:bg-violet-100 disabled:text-violet-400 dark:bg-violet-500 dark:text-stone-950 dark:hover:bg-violet-400 dark:disabled:bg-violet-950 dark:disabled:text-violet-600"
          >
            {submitting ? "Uploading..." : "Submit rewrite"}
          </button>
        )}
      </div>
    </div>
  );
}
