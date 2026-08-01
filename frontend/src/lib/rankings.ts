import type { JobPosting, RankingResult } from "./types";

export function filterRankingsBySelectedJobs(
  rankings: RankingResult[],
  selectedJobIds: string[],
): RankingResult[] {
  if (selectedJobIds.length === 0) return [];
  const selected = new Set(selectedJobIds);
  return rankings.filter(result => selected.has(result.jobId));
}

export function filterRankingsByMinimumScore(
  rankings: RankingResult[],
  minimumScore: number,
): RankingResult[] {
  return rankings.filter(result => result.compositeScore >= minimumScore);
}

export function resolveGreetingSelectionFromRankings(
  selectedRankingIds: string[],
  rankings: RankingResult[],
): string[] {
  const rankedIds = new Set(rankings.filter(result => !isFallbackRanking(result)).map(result => result.jobId));
  return selectedRankingIds.filter((id, index) => rankedIds.has(id) && selectedRankingIds.indexOf(id) === index);
}

export function isFallbackRanking(result: RankingResult): boolean {
  const reason = result.reason.trim();
  return result.matchStatus === "failed" || reason.includes("匹配度分析待AI配置后更新") || reason.startsWith("AI 调用失败");
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

export function findFallbackRankingsBySelectedJobs(
  rankings: RankingResult[],
  selectedJobIds: string[],
): RankingResult[] {
  const selected = new Set(selectedJobIds);
  return rankings.filter(result => selected.has(result.jobId) && isFallbackRanking(result));
}
