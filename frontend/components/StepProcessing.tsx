"use client";

import { useEffect, useRef, useState } from "react";
import { getJobStatus } from "@/lib/api";

const POLL_INTERVAL_MS = 1500;

export default function StepProcessing({
  jobId,
  onCompleted,
  onFailed,
}: {
  jobId: string;
  onCompleted: () => void;
  onFailed: (error: string) => void;
}) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const startedAt = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    startedAt.current = Date.now();

    const poll = async () => {
      try {
        const status = await getJobStatus(jobId);
        if (cancelled) return;

        if (status.state === "completed") {
          onCompleted();
          return;
        }
        if (status.state === "failed") {
          onFailed(status.error ?? "Processing failed for an unknown reason.");
          return;
        }
        setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (!cancelled) {
          onFailed(err instanceof Error ? err.message : "Could not check job status.");
        }
      }
    };

    poll();
    const tick = setInterval(() => {
      if (startedAt.current !== null) {
        setElapsedSeconds(Math.round((Date.now() - startedAt.current) / 1000));
      }
    }, 1000);

    return () => {
      cancelled = true;
      clearInterval(tick);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  return (
    <div className="flex flex-col items-center gap-6 py-16 text-center">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-stone-200 border-t-violet-600 dark:border-stone-700 dark:border-t-violet-500" />
      <div>
        <h2 className="text-xl font-semibold text-stone-900 dark:text-stone-50">
          Processing your pages
        </h2>
        <p className="mt-2 max-w-sm text-sm text-stone-500 dark:text-stone-400">
          Aligning pages, extracting characters, validating, and building your font. This
          usually takes under a minute.
        </p>
        <p className="mt-4 text-xs text-stone-400 dark:text-stone-500">{elapsedSeconds}s elapsed</p>
      </div>
    </div>
  );
}
