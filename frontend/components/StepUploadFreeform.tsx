"use client";

import { useEffect, useState } from "react";
import { ApiError, getCharacterSet } from "@/lib/api";
import type { ProcessJobRequest, RewriteCharacter } from "@/lib/types";
import CharacterChecklist from "@/components/CharacterChecklist";
import PhotoDropzone from "@/components/PhotoDropzone";

export default function StepUploadFreeform({
  file,
  onFileChange,
  metadata,
  onMetadataChange,
  onSubmit,
  onBack,
  submitting,
  error,
}: {
  file: File | null;
  onFileChange: (file: File | null) => void;
  metadata: ProcessJobRequest;
  onMetadataChange: (metadata: ProcessJobRequest) => void;
  onSubmit: () => void;
  onBack: () => void;
  submitting: boolean;
  error: string | null;
}) {
  const [characters, setCharacters] = useState<RewriteCharacter[]>([]);
  const [listError, setListError] = useState<string | null>(null);

  useEffect(() => {
    getCharacterSet()
      .then(setCharacters)
      .catch((err) => setListError(err instanceof ApiError ? err.message : "Could not load the character list."));
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-50">
          Write freeform, no template needed
        </h2>
        <p className="mt-2 max-w-xl text-stone-600 dark:text-stone-400">
          On a blank sheet of plain paper, write every character below, in this exact order, left
          to right, wrapping to a new row as needed. Leave clear gaps between characters. Then
          photograph the page in even lighting, avoiding shadows falling across it, and upload it.
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

      {characters.length > 0 && <CharacterChecklist characters={characters} />}

      <PhotoDropzone file={file} onFileChange={onFileChange} label="Drag your photo here, or click to choose it" />

      <fieldset className="flex flex-col gap-3 rounded-lg border border-stone-200 p-4 dark:border-stone-800">
        <legend className="px-1 text-sm font-medium text-stone-700 dark:text-stone-300">Font details</legend>
        <label className="flex flex-col gap-1 text-sm">
          Family name
          <input
            type="text"
            spellCheck={false}
            value={metadata.family_name}
            onChange={(e) => onMetadataChange({ ...metadata, family_name: e.target.value })}
            className="rounded-md border border-stone-300 px-3 py-1.5 dark:border-stone-700 dark:bg-stone-900"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Creator
          <input
            type="text"
            spellCheck={false}
            value={metadata.creator}
            onChange={(e) => onMetadataChange({ ...metadata, creator: e.target.value })}
            className="rounded-md border border-stone-300 px-3 py-1.5 dark:border-stone-700 dark:bg-stone-900"
          />
        </label>
      </fieldset>

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onBack}
          disabled={submitting}
          className="rounded-full px-5 py-2.5 text-sm font-medium text-stone-600 hover:bg-stone-100 disabled:opacity-50 dark:text-stone-400 dark:hover:bg-stone-800"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={!file || submitting}
          className="rounded-full bg-violet-700 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:bg-violet-100 disabled:text-violet-400 dark:bg-violet-500 dark:text-stone-950 dark:hover:bg-violet-400 dark:disabled:bg-violet-950 dark:disabled:text-violet-600"
        >
          {submitting ? "Uploading..." : "Upload & generate font"}
        </button>
      </div>
    </div>
  );
}
