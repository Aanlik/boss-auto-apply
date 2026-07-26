import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { JobFilterPanel } from "./JobFilterPanel";
import type { JobApplicationStatus, JobDecisionStatus } from "../lib/types";

const statusLabels: Record<JobApplicationStatus, string> = {
  pending: "待跟进",
  greeted: "已打招呼",
  applied: "已投递",
  interviewing: "面试中",
  rejected: "已拒绝",
  abandoned: "已放弃",
};
const decisionLabels: Record<JobDecisionStatus, string> = {
  undecided: "未决定",
  recommended: "推荐投递",
  watching: "观察",
  abandoned: "放弃",
  risky: "风险",
};

describe("JobFilterPanel", () => {
  test("keeps salary and tag filters in a stable grid and handles common tags", async () => {
    const user = userEvent.setup();
    const onFilterTagsChange = vi.fn();
    const onHideCommonTag = vi.fn();

    render(
      <JobFilterPanel
        totalJobs={12}
        filteredJobs={7}
        filterText=""
        filterCity=""
        filterSalaryMin=""
        filterSalaryMax=""
        filterTags=""
        filterApplicationStatus=""
        filterDecisionStatus=""
        cities={["郑州", "深圳"]}
        commonTags={["远程", "AI"]}
        filterTagList={[]}
        statusLabels={statusLabels}
        decisionLabels={decisionLabels}
        onFilterTextChange={vi.fn()}
        onFilterCityChange={vi.fn()}
        onFilterSalaryMinChange={vi.fn()}
        onFilterSalaryMaxChange={vi.fn()}
        onFilterTagsChange={onFilterTagsChange}
        onFilterApplicationStatusChange={vi.fn()}
        onFilterDecisionStatusChange={vi.fn()}
        onHideCommonTag={onHideCommonTag}
        onClearCommonTags={vi.fn()}
        onSelectAllTags={vi.fn()}
        onSelectAll={vi.fn()}
        onClearSelection={vi.fn()}
        onDeleteSelected={vi.fn()}
        onClearAllJobs={vi.fn()}
        selectedCount={0}
      />
    );

    expect(screen.getByLabelText("最低薪资(K)")).toHaveClass("form-input");
    expect(screen.getByLabelText("最高薪资(K)")).toHaveClass("form-input");
    expect(screen.getByLabelText("标签筛选")).toHaveClass("form-input");
    expect(screen.getByLabelText("决策标签")).toHaveClass("form-input");
    expect(screen.getByText("筛选 (7/12)")).toBeInTheDocument();

    await user.click(screen.getByText("远程"));
    expect(onFilterTagsChange).toHaveBeenCalledWith("远程");

    await user.click(screen.getByLabelText("从常用标签删除 AI"));
    expect(onHideCommonTag).toHaveBeenCalledWith("AI");
  });
});
