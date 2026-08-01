import { describe, expect, test } from "vitest";
import { consumeDashboardNavigation, resolveDashboardQualityFilter, setDashboardNavigation } from "./dashboardNavigation";

describe("dashboard navigation intents", () => {
  test("delivers a jobs quality filter once to the destination page", () => {
    setDashboardNavigation({ page: "jobs", jobs: { qualityFilter: "missing_jd" } });

    expect(consumeDashboardNavigation("jobs")).toEqual({ page: "jobs", jobs: { qualityFilter: "missing_jd" } });
    expect(consumeDashboardNavigation("jobs")).toBeNull();
  });

  test("preserves the metric scope with an application-status filter", () => {
    setDashboardNavigation({
      page: "jobs",
      jobs: { applicationStatus: "greeted", scopeLabel: "全库历史" },
    });

    expect(consumeDashboardNavigation("jobs")).toEqual({
      page: "jobs",
      jobs: { applicationStatus: "greeted", scopeLabel: "全库历史" },
    });
  });

  test("maps every job-based quality card to its destination filter", () => {
    expect(resolveDashboardQualityFilter("duplicate_jobs")).toBe("duplicates");
    expect(resolveDashboardQualityFilter("missing_business_name")).toBe("missing_business_name");
    expect(resolveDashboardQualityFilter("no_rankings")).toBe("no_rankings");
    expect(resolveDashboardQualityFilter("ai_feedback_needs_revision")).toBe("ai_feedback_needs_revision");
    expect(resolveDashboardQualityFilter("unrelated")).toBe("");
  });
});
