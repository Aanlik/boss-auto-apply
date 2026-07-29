import type { JobPosting, RankingResult } from "./types";

export function filterRankingsBySelectedJobs(
  rankings: RankingResult[],
  selectedJobIds: string[],
): RankingResult[] {
  if (selectedJobIds.length === 0) return [];
  const selected = new Set(selectedJobIds);
  return rankings.filter(result => selected.has(result.jobId));
}

export function findUnrankedSelectedJobs(
  jobs: JobPosting[],
  selectedJobIds: string[],
  rankings: RankingResult[],
): JobPosting[] {
  if (selectedJobIds.length === 0) return [];
  const selected = new Set(selectedJobIds);
  const ranked = new Set(rankings.map(result => result.jobId));
  return jobs.filter(job => selected.has(job.id) && !ranked.has(job.id));
}
