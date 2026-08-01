import { describe, expect, test } from "vitest";
import type { JobPosting, RankingResult } from "./types";
import { filterRankingsByMinimumScore, findFallbackRankingsBySelectedJobs, findUnrankedSelectedJobs, isFallbackRanking, resolveGreetingSelectionFromRankings } from "./rankings";

function job(id: string, company: string): JobPosting {
  return {
    id,
    title: "HRBP",
    company,
    city: "郑州",
    salary: "",
    salary_min: 0,
    salary_max: 0,
    jd_text: "负责 HRBP",
    keywords: [],
    structured_summary: "",
    source: "boss_api",
    source_url: "",
    fetched_at: "",
    dedupe_key: "",
  };
}

function ranking(jobId: string): RankingResult {
  return {
    jobId,
    jobTitle: "HRBP",
    company: "示例科技",
    salary: "",
    companyScore: 80,
    matchScore: 80,
    compositeScore: 80,
    recommendation: "recommend",
    reason: "",
    matchHighlights: [],
    matchGaps: [],
  };
}

describe("findUnrankedSelectedJobs", () => {
  test("returns selected jobs that do not have ranking results yet", () => {
    const missing = findUnrankedSelectedJobs(
      [job("job-1", "A"), job("job-2", "示例信息科技有限公司"), job("job-3", "C")],
      ["job-1", "job-2", "job-3"],
      [ranking("job-1"), ranking("job-3")],
    );

    expect(missing.map(item => [item.id, item.company])).toEqual([
      ["job-2", "示例信息科技有限公司"],
    ]);
  });
});

describe("findFallbackRankingsBySelectedJobs", () => {
  test("returns only selected rankings generated while AI was unavailable", () => {
    const results = [
      { ...ranking("fallback"), reason: "匹配度分析待AI配置后更新（请在设置中配置API Key）", matchScore: 50 },
      { ...ranking("failed"), reason: "AI 调用失败: 网络超时", matchScore: 50 },
      ranking("complete"),
    ];

    expect(findFallbackRankingsBySelectedJobs(results, ["fallback", "failed", "complete"]).map(item => item.jobId)).toEqual(["fallback", "failed"]);
  });
});

test("treats an explicitly failed AI result as a fallback regardless of its message", () => {
  expect(isFallbackRanking({ ...ranking("failed-status"), matchStatus: "failed", failureReason: "invalid_schema" })).toBe(true);
});

describe("ranking handoff", () => {
  test("filters rankings at or above the selected recommendation score", () => {
    const results = [
      ranking("job-90"),
      { ...ranking("job-70"), compositeScore: 70 },
      { ...ranking("job-69"), compositeScore: 69 },
    ];

    expect(filterRankingsByMinimumScore(results, 70).map(item => item.jobId)).toEqual(["job-90", "job-70"]);
  });

  test("only hands checked ranking rows to the greeting workflow", () => {
    const results = [
      ranking("job-1"),
      { ...ranking("job-2"), reason: "匹配度分析待AI配置后更新（请在设置中配置API Key）", matchScore: 50 },
    ];

    expect(resolveGreetingSelectionFromRankings(["job-1", "job-2", "missing"], results)).toEqual(["job-1"]);
  });
});
