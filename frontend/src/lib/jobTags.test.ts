import { describe, expect, test } from "vitest";
import type { JobPosting } from "./types";
import { buildCommonTags } from "./jobTags";

function job(overrides: Partial<JobPosting>): JobPosting {
  return {
    id: "job-1",
    title: "产品经理",
    company: "示例科技",
    city: "深圳",
    salary: "20-30K",
    salary_min: 20,
    salary_max: 30,
    jd_text: "",
    keywords: [],
    structured_summary: "",
    source: "boss_api",
    source_url: "",
    fetched_at: "",
    dedupe_key: "",
    ...overrides,
  };
}

describe("buildCommonTags", () => {
  test("includes user-created tags from jobs and hides deleted common tags", () => {
    const jobs = [
      job({ id: "job-1", keywords: ["AI", "B端"], tags: ["优先", "@深圳市示例科技有限公司"] }),
      job({ id: "job-2", keywords: ["远程"], tags: ["跟进", "优先"] }),
    ];

    const commonTags = buildCommonTags(jobs, ["AI"]);

    expect(commonTags).toEqual(expect.arrayContaining(["B端", "优先", "跟进", "远程"]));
    expect(commonTags).not.toContain("AI");
    expect(commonTags).not.toContain("@深圳市示例科技有限公司");
  });
});
