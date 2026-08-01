import { describe, expect, test } from "vitest";
import { dashboardScopeLabel, buildJobNavigation } from "./dashboardScope";

describe("dashboard scope helpers", () => {
  test("labels selected and historical metrics with their data scope", () => {
    expect(dashboardScopeLabel("selected", 17)).toBe("当前已选岗位（17）");
    expect(dashboardScopeLabel("history", 0)).toBe("全库历史");
  });

  test("creates a jobs intent that preserves historical status semantics", () => {
    expect(buildJobNavigation({ applicationStatus: "greeted", scope: "history" })).toEqual({
      page: "jobs",
      jobs: { applicationStatus: "greeted", scopeLabel: "全库历史" },
    });
  });

  test("creates an AI-feedback revision filter for the jobs page", () => {
    expect(buildJobNavigation({ qualityFilter: "ai_feedback_needs_revision", selectedCount: 12 })).toEqual({
      page: "jobs",
      jobs: { qualityFilter: "ai_feedback_needs_revision", scopeLabel: "当前已选岗位（12）", selectedOnly: true },
    });
  });
});
