import type { RewriteCharacter } from "@/lib/types";

// Shown before a freeform (no-template) photo upload so the user copies
// this exact order onto plain paper — extraction matches purely by
// position (see backend pipeline.segmentation.freeform), so the numbers
// aren't decorative, they're the contract the photo has to satisfy.
export default function CharacterChecklist({ characters }: { characters: RewriteCharacter[] }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(44px,1fr))] gap-1.5 rounded-xl border border-stone-200 bg-stone-50 p-4 dark:border-stone-800 dark:bg-stone-900">
      {characters.map((c, i) => (
        <div
          key={c.character_id}
          className="flex flex-col items-center gap-0.5 rounded-md bg-white px-1 py-2 shadow-sm dark:bg-stone-800"
        >
          <span className="text-lg font-medium leading-none text-stone-900 dark:text-stone-50">
            {c.character}
          </span>
          <span className="text-[10px] leading-none text-stone-400 dark:text-stone-500">{i + 1}</span>
        </div>
      ))}
    </div>
  );
}
