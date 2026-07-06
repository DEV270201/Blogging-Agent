// Mirrors the server's generation stages (Server/persistence/job_repository.py).
// Order matters: the progress stepper renders these top-to-bottom.

export const STAGES = [
  { key: "queued", label: "Queued", emoji: "📥", blurb: "Waiting to start…" },
  {
    key: "generating_queries",
    label: "Generating search queries",
    emoji: "🔍",
    blurb: "Deciding what to look up…",
  },
  {
    key: "researching",
    label: "Researching sources",
    emoji: "🌐",
    blurb: "Reading the web for evidence…",
  },
  {
    key: "planning",
    label: "Planning the outline",
    emoji: "🗺️",
    blurb: "Structuring the blog…",
  },
  {
    key: "writing_sections",
    label: "Writing sections",
    emoji: "✍️",
    blurb: "Drafting each section…",
  },
  {
    key: "synthesizing",
    label: "Synthesizing the blog",
    emoji: "🧩",
    blurb: "Stitching it all together…",
  },
  {
    key: "complete",
    label: "Complete",
    emoji: "✅",
    blurb: "Your blog is ready!",
  },
];

export function stageIndex(stageKey) {
  const idx = STAGES.findIndex((s) => s.key === stageKey);
  return idx === -1 ? 0 : idx;
}

export const STATUS_META = {
  "IN-PROGRESS": { label: "Generating", className: "progress" },
  COMPLETE: { label: "Complete", className: "complete" },
  HALTED: { label: "Halted", className: "halted" },
  FAILED: { label: "Failed", className: "failed" },
};

export function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
