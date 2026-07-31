import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

describe("Jobs JD enrichment UI regressions", () => {
  test("refreshes job data while JD enrichment is running without reloading the window", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("JD 抓取期间增量刷新岗位数据");
    expect(jobsPage).toMatch(/loading === "enrich" \|\| loading === "enrich-force"/);
    expect(jobsPage).toMatch(/window\.setInterval\(refreshLiveJdResults, 800\)/);
    expect(jobsPage).not.toMatch(/window\.location\.reload\(\)/);
  });
});
