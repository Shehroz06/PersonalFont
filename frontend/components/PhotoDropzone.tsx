"use client";

import { useRef, useState } from "react";

export default function PhotoDropzone({
  file,
  onFileChange,
  label,
}: {
  file: File | null;
  onFileChange: (file: File | null) => void;
  label?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  function pick(list: FileList | null) {
    const picked = list?.[0];
    if (picked && (picked.type === "image/jpeg" || picked.type === "image/png")) {
      onFileChange(picked);
    }
  }

  if (file) {
    return (
      <div className="flex items-center justify-between rounded-lg bg-stone-100 px-4 py-2 text-sm dark:bg-stone-800">
        <span className="truncate text-stone-700 dark:text-stone-300">
          {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
        </span>
        <button
          type="button"
          onClick={() => onFileChange(null)}
          className="ml-3 shrink-0 text-stone-500 hover:text-red-600 dark:text-stone-400 dark:hover:text-red-400"
          aria-label={`Remove ${file.name}`}
        >
          Remove
        </button>
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragActive(false);
        pick(e.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
      className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-10 text-center text-sm transition-colors ${
        dragActive
          ? "border-violet-600 bg-violet-50 dark:border-violet-500 dark:bg-stone-900"
          : "border-stone-300 text-stone-500 dark:border-stone-700 dark:text-stone-400"
      }`}
    >
      <p>{label ?? "Drag a photo here, or click to choose a file"}</p>
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png"
        className="hidden"
        onChange={(e) => pick(e.target.files)}
      />
    </div>
  );
}
