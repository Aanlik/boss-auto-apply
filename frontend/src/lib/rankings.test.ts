import { describe, expect, test } from "vitest";
import type { RankingResult } from "./types";
import { filterRankingsBySelectedJobs } from "./rankings";

function ranking(jobId: string): RankingResult {
  return {
    jobId,
    jobTitle: `岗位 ${jobId}`,
    company: "示例科技",
    salary: "20-30K",
    companyScore: 80,
    matchScore: 75,
    compositeScore: 78,
    recommendation: "recommend",
    reason: "匹配度较高",
    matchHighlights: [],
    matchGaps: [],
  };
}

describe("filterRankingsBySelectedJobs", () => {
  test("keeps ranking results linked to current job selection", () => {
    const results = [ranking("job-a"), ranking("job-b"), ranking("job-c")];

    expect(filterRankingsBySelectedJobs(results, ["job-a", "job-c"]).map(r => r.jobId)).toEqual([
      "job-a",
      "job-c",
    ]);
  });

  test("hides stale ranking results when no jobs are selected", () => {
    expect(filterRankingsBySelectedJobs([ranking("job-a")], [])).toEqual([]);
  });
});
