import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

describe("Jobs JD enrichment UI regressions", () => {
  test("keeps a large selected job list collapsed until requested", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("showSelectedJobs");
    expect(jobsPage).toContain("展开已选岗位");
  });
  test("refreshes job data while JD enrichment is running without reloading the window", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("JD 抓取期间增量刷新岗位数据");
    expect(jobsPage).toMatch(/loading === "enrich" \|\| loading === "enrich-force"/);
    expect(jobsPage).toMatch(/window\.setInterval\(refreshLiveJdResults, 800\)/);
  });

  test("keeps capture batch details collapsed and permanently deletes only the chosen batch", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("抓取批次详情");
    expect(jobsPage).toContain("const [batchesExpanded, setBatchesExpanded] = useState(false)");
    expect(jobsPage).toContain("deleteCaptureBatch");
    expect(jobsPage).toContain("永久删除该批次");
    expect(jobsPage).toContain("显示全部批次");
    expect(jobsPage).toMatch(/aria-expanded=\{batchesExpanded\}/);
  });

  test("offers a full application refresh action on the jobs page", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("刷新当前页面");
    expect(jobsPage).toContain("function refreshCurrentPage()");
    expect(jobsPage).toMatch(/window\.location\.reload\(\)/);
  });

  test("uses stable containers when jobs are grouped by company", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain('className="job-company-groups"');
    expect(jobsPage).toContain("<Fragment key={group.key}>");
  });

  test("adds clickable diligence risk and AI-revision quality filters", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain('"ai_feedback_needs_revision"');
    expect(jobsPage).toContain('"risk_jobs"');
    expect(jobsPage).toContain("AI 反馈需修改");
    expect(jobsPage).toContain("尽调高风险岗位");
    expect(jobsPage).toContain("aiFeedbackNeedsRevisionJobIds");
    expect(jobsPage).toContain("riskJobIds");
  });

  test("labels quality metrics as an all-pool view rather than the current selection", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("岗位池质量 · 全库（不含黑名单）");
  });

  test("keeps login heartbeat passive and only probes after an explicit request", () => {
    const jobsPage = readFileSync(resolve(process.cwd(), "src/pages/jobs.tsx"), "utf8");

    expect(jobsPage).toContain("checkStatus(false)");
    expect(jobsPage).toMatch(/window\.setInterval\(\(\) => \{\s*checkStatus\(false\);\s*\}, 60_000\)/);
    expect(jobsPage).toContain("onClick={() => checkStatus(true)}");
    expect(jobsPage).toContain("验证登录有效性");
  });
});
