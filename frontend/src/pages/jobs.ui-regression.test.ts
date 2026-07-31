import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

describe("Jobs JD enrichment UI regressions", () => {
  test("refreshes job data while JD enrichment is running without reloading the window", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("JD 抓取期间增量刷新岗位数据");
    expect(jobsPage).toMatch(/loading === "enrich" \|\| loading === "enrich-force"/);
    expect(jobsPage).toMatch(/window\.setInterval\(refreshLiveJdResults, 800\)/);
  });

  test("keeps capture batch details collapsible and removable without deleting jobs", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("抓取批次详情");
    expect(jobsPage).toContain("恢复已删除批次");
    expect(jobsPage).toContain("HIDDEN_CAPTURE_BATCHES_KEY");
    expect(jobsPage).toContain("显示全部批次");
    expect(jobsPage).toMatch(/aria-expanded=\{batchesExpanded\}/);
  });

  test("offers a full application refresh action on the jobs page", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("刷新当前页面");
    expect(jobsPage).toContain("function refreshCurrentPage()");
    expect(jobsPage).toMatch(/window\.location\.reload\(\)/);
  });
});
