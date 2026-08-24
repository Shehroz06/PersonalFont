import { templatePdfUrl } from "@/lib/api";
import type { TemplateSummary } from "@/lib/types";

export default function StepDownloadTemplate({
  templates,
  selectedTemplateId,
  onSelectTemplate,
  onContinue,
  onBack,
  loading,
  error,
}: {
  templates: TemplateSummary[];
  selectedTemplateId: string | null;
  onSelectTemplate: (templateId: string) => void;
  onContinue: () => void;
  onBack: () => void;
  loading: boolean;
  error: string | null;
}) {
  const selected = templates.find((t) => t.template_id === selectedTemplateId) ?? templates[0];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-50">
          Download the template
        </h2>
        <p className="mt-2 max-w-xl text-stone-600 dark:text-stone-400">
          Print it, write one character per box staying inside the lines, then photograph each
          page in good, even lighting.
        </p>
      </div>

      {error && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {templates.length > 1 && (
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium text-stone-700 dark:text-stone-300">
            Template
          </legend>
          {templates.map((template) => (
            <label key={template.template_id} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="template"
                checked={template.template_id === selectedTemplateId}
                onChange={() => onSelectTemplate(template.template_id)}
              />
              {template.template_id} (v{template.template_version})
            </label>
          ))}
        </fieldset>
      )}

      {selected && (
        <div className="rounded-lg border border-stone-200 p-4 text-sm text-stone-600 dark:border-stone-800 dark:text-stone-400">
          <p>
            <strong className="text-stone-900 dark:text-stone-100">{selected.template_id}</strong>{" "}
            &middot; {selected.page_count} page{selected.page_count === 1 ? "" : "s"} &middot;{" "}
            {selected.character_count} characters
          </p>
        </div>
      )}

      {selected && (
        <a
          href={templatePdfUrl(selected.template_id)}
          target="_blank"
          rel="noopener noreferrer"
          className="w-fit rounded-full border border-stone-300 px-6 py-3 text-sm font-medium text-stone-900 transition-colors hover:bg-stone-100 dark:border-stone-700 dark:text-stone-100 dark:hover:bg-stone-800"
        >
          Download template PDF
        </a>
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
          disabled={!selected || loading}
          className="rounded-full bg-violet-700 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-violet-600 disabled:cursor-not-allowed disabled:bg-violet-100 disabled:text-violet-400 dark:bg-violet-500 dark:text-stone-950 dark:hover:bg-violet-400 dark:disabled:bg-violet-950 dark:disabled:text-violet-600"
        >
          {loading ? "Starting job..." : "I've filled it in, continue"}
        </button>
      </div>
    </div>
  );
}
