import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

const page = readFileSync(resolve(process.cwd(), "src/pages/ranked-jobs.tsx"), "utf8");
const api = readFileSync(resolve(process.cwd(), "src/lib/api.ts"), "utf8");

describe("ranking continuation", () => {
  test("continues only the selected jobs that are still missing ranking results", () => {
    expect(page).toContain("function onContinueRanking()");
    expect(page).toContain("unrankedSelectedJobs.map(job => job.id)");
    expect(page).toContain("继续排序");
    expect(page).toMatch(/rankJobs\(ids, resumeProfile, diligenceReports, weights, continueExisting, isAiRefresh\)/);
    expect(api).toContain("continue_existing: continueExisting");
  });

  test("offers a continuation action after a ranking request fails", () => {
    expect(page).toContain("rankingFailed");
    expect(page).toMatch(/上一轮排序未完成/);
  });

  test("restores a retry action from a persisted failed ranking task after reload", () => {
    expect(page).toContain("getWorkflowCenter");
    expect(page).toMatch(/task\.type === "ranking"/);
    expect(page).toMatch(/重新排序未完成岗位/);
  });

  test("reports an actionable result after refreshing temporary AI matches", () => {
    expect(page).toContain("AI 匹配度已更新");
    expect(page).toContain("遗留临时结果未被替换");
  });
});
