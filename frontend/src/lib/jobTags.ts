import type { JobPosting } from "./types";

function normalizeTag(tag: string) {
  return tag.trim();
}

export function buildCommonTags(jobs: JobPosting[], hiddenTags: string[] = [], limit = 12) {
  const hidden = new Set(hiddenTags.map(t => t.toLowerCase()));
  const tags = new Set<string>();

  for (const job of jobs) {
    for (const tag of [...(job.keywords || []), ...(job.tags || [])]) {
      const normalized = normalizeTag(tag);
      if (!normalized || normalized.startsWith("@")) continue;
      if (hidden.has(normalized.toLowerCase())) continue;
      tags.add(normalized);
    }
  }

  return [...tags].sort((a, b) => a.localeCompare(b, "zh-CN")).slice(0, limit);
}
