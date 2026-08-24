"use client";

import { useRef, useState } from "react";
import type { ProcessJobRequest } from "@/lib/types";

export default function StepUploadPages({
  files,
  onFilesChange,
  metadata,
  onMetadataChange,
  onSubmit,
  onBack,
  submitting,
  error,
}: {
  files: File[];
  onFilesChange: (files: File[]) => void;
  metadata: ProcessJobRequest;
  onMetadataChange: (metadata: ProcessJobRequest) => void;
  onSubmit: () => void;
  onBack: () => void;
  submitting: boolean;
  error: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  function addFiles(newFiles: FileList | null) {
    if (!newFiles) return;
    const accepted = Array.from(newFiles).filter(
      (file) => file.type === "image/jpeg" || file.type === "image/png",
    );
    onFilesChange([...files, ...accepted]);
  }

  function removeFile(index: number) {
    onFilesChange(files.filter((_, i) => i !== index));
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-50">
          Upload your photographed pages
        </h2>
        <p className="mt-2 max-w-xl text-stone-600 dark:text-stone-400">
          JPEG or PNG, one file per page. You don&apos;t need to upload every page at once.
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragActive(false);
          addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center text-sm transition-colors ${
          dragActive
            ? "border-violet-600 bg-violet-50 dark:border-violet-500 dark:bg-stone-900"
            : "border-stone-300 text-stone-500 dark:border-stone-700 dark:text-stone-400"
        }`}
      >
        <p>Drag photos here, or click to choose files</p>
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png"
          multiple
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <ul className="flex flex-col gap-2">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${index}`}
              className="flex items-center justify-between rounded-lg bg-stone-100 px-4 py-2 text-sm dark:bg-stone-800"
            >
              <span className="truncate text-stone-700 dark:text-stone-300">
                {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
              </span>
              <button
                type="button"
                onClick={() => removeFile(index)}
                className="ml-3 shrink-0 text-stone-500 hover:text-red-600 dark:text-stone-400 dark:hover:text-red-400"
                aria-label={`Remove ${file.name}`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <fieldset className="flex flex-col gap-3 rounded-lg border border-stone-200 p-4 dark:border-stone-800">
        <legend className="px-1 text-sm font-medium text-stone-700 dark:text-stone-300">
          Font details
        </legend>
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
          disabled={files.length === 0 || submitting}
          className="rounded-full bg-violet-700 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:bg-violet-100 disabled:text-violet-400 dark:bg-violet-500 dark:text-stone-950 dark:hover:bg-violet-400 dark:disabled:bg-violet-950 dark:disabled:text-violet-600"
        >
          {submitting ? "Uploading..." : "Upload & generate font"}
        </button>
      </div>
    </div>
  );
}
