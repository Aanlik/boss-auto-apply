import type { DashboardNavigation, JobQualityFilter } from "./dashboardNavigation";

export type DashboardScope = "selected" | "history";

export function dashboardScopeLabel(scope: DashboardScope, selectedCount = 0): "当前已选岗位（0）" | "当前已选岗位（1）" | "当前已选岗位（2）" | "当前已选岗位（3）" | "当前已选岗位（4）" | "当前已选岗位（5）" | "当前已选岗位（6）" | "当前已选岗位（7）" | "当前已选岗位（8）" | "当前已选岗位（9）" | `当前已选岗位（${number}）` | "全库历史" {
  return scope === "history" ? "全库历史" : `当前已选岗位（${selectedCount}）`;
}

export function buildJobNavigation(input: {
  qualityFilter?: JobQualityFilter;
  applicationStatus?: string;
  decisionStatus?: string;
  scope?: DashboardScope;
  selectedCount?: number;
}): DashboardNavigation {
  const scope = input.scope || "selected";
  return {
    page: "jobs",
    jobs: {
      qualityFilter: input.qualityFilter,
      applicationStatus: input.applicationStatus,
      decisionStatus: input.decisionStatus,
      scopeLabel: dashboardScopeLabel(scope, input.selectedCount),
      ...(scope === "selected" ? { selectedOnly: true } : {}),
    },
  };
}
