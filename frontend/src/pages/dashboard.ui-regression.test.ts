import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, test } from "vitest";

function readDashboard() {
  return readFileSync(resolve(process.cwd(), "src/pages/dashboard.tsx"), "utf8");
}

describe("Dashboard live data regressions", () => {
  test("refreshes task center, CRM board, quality, and onboarding data while open", () => {
    const dashboard = readDashboard();

    expect(dashboard).toMatch(/function refreshLiveDashboard/);
    expect(dashboard).toMatch(/getWorkflowCenter\(\)/);
    expect(dashboard).toMatch(/getApplicationBoard\(workflow\.selectedJobIds\)/);
    expect(dashboard).toMatch(/getDataQualityCenter\(workflow\.selectedJobIds\)/);
    expect(dashboard).toMatch(/getOnboardingGuide\(workflow\.selectedJobIds\)/);
    expect(dashboard).toMatch(/setInterval\(refreshLiveDashboard, 10000\)/);
  });

  test("does not truncate CRM cards in the dashboard view", () => {
    expect(readDashboard()).not.toMatch(/column\.jobs\.slice\(0, 3\)/);
  });

  test("lets every CRM status column collapse its job content independently", () => {
    const dashboard = readDashboard();

    expect(dashboard).toMatch(/collapsedBoardColumns/);
    expect(dashboard).toMatch(/toggleBoardColumn\(column\.key\)/);
    expect(dashboard).toMatch(/收起看板内容/);
    expect(dashboard).not.toMatch(/application-board-card__collapse/);
  });

  test("shows every AI version record instead of deep reports only", () => {
    const dashboard = readDashboard();

    expect(dashboard).toMatch(/getAssistantPromptVersions\(\)/);
    expect(dashboard).not.toMatch(/getAssistantPromptVersions\("deep_report"\)/);
    expect(dashboard).toMatch(/记录实际 AI 调用/);
  });

  test("uses the selected jobs when refreshing the flow-quality summary", () => {
    const dashboard = readDashboard();

    expect(dashboard).toMatch(/getDashboardSummary\(workflow\.selectedJobIds\)/);
  });

  test("shows the selected job count as a flow-guidance card", () => {
    expect(readDashboard()).toMatch(/readiness-blocker--selected/);
  });

  test("explains that flow quality and data quality are separate measures", () => {
    expect(readDashboard()).toMatch(/流程完成度，不等同于数据质量/);
  });

  test("labels historical JD rate as all-pool history", () => {
    expect(readDashboard()).toContain("全库 JD");
  });

  test("keeps the flow-quality score and its denominator on one baseline", () => {
    expect(readDashboard()).toContain("readiness-score__value");
  });

  test("routes quality checks to a concrete destination filter", () => {
    const dashboard = readDashboard();

    expect(dashboard).toContain("navigateQualityCheck(check.key, check.page)");
    expect(dashboard).toContain("resolveDashboardQualityFilter(key)");
    expect(dashboard).toContain("goToJobs(qualityFilter)");
  });
});
