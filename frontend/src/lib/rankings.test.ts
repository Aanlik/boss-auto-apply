import { describe, expect, test } from "vitest";
import type { JobPosting, RankingResult } from "./types";
import { findUnrankedSelectedJobs } from "./rankings";

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
