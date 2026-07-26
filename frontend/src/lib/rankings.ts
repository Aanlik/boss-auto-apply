import type { RankingResult } from "./types";

export function filterRankingsBySelectedJobs(
  rankings: RankingResult[],
  selectedJobIds: string[],
): RankingResult[] {
  if (selectedJobIds.length === 0) return [];
  const selected = new Set(selectedJobIds);
  return rankings.filter(result => selected.has(result.jobId));
}
