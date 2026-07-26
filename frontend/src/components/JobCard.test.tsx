import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import { JobCard } from "./JobCard";
import type { JobApplicationStatus, JobDecisionStatus, JobPosting } from "../lib/types";

afterEach(() => cleanup());

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

function job(overrides: Partial<JobPosting> = {}): JobPosting {
  return {
    id: "job-1",
    title: "产品经理",
    company: "示例科技有限公司",
    city: "郑州",
    salary: "15-25K",
    salary_min: 15,
    salary_max: 25,
    jd_text: "岗位职责：负责产品规划和需求分析。",
    keywords: ["B端", "AI"],
    structured_summary: "",
    source: "boss",
    source_url: "https://www.zhipin.com/job_detail/demo.html",
    fetched_at: "2026-07-27T08:00:00",
    dedupe_key: "job-1",
    application_status: "pending",
    decision_status: "undecided",
    ...overrides,
  };
}

describe("JobCard", () => {
  test("uses application status as the greeting state control and hides old greeting shortcut", async () => {
    const user = userEvent.setup();
    const onStatusChange = vi.fn();

    render(
      <JobCard
        job={job()}
        selected={false}
        expanded={false}
        customTags={["优先"]}
        tagInput=""
        filterTagList={[]}
        greeted={false}
        statusLabels={statusLabels}
        decisionLabels={decisionLabels}
        onToggleSelected={vi.fn()}
        onToggleDetail={vi.fn()}
        onStatusChange={onStatusChange}
        onDecisionChange={vi.fn()}
        onRemoveCustomTag={vi.fn()}
        onTagInputChange={vi.fn()}
        onAddCustomTag={vi.fn()}
        onToggleKeywordTag={vi.fn()}
        onAddBlacklist={vi.fn()}
        onDelete={vi.fn()}
      />
    );

    expect(screen.queryByText("标记招呼")).not.toBeInTheDocument();
    expect(screen.getByText("求职状态")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("求职状态"), "applied");
    expect(onStatusChange).toHaveBeenCalledWith("applied");
  });

  test("updates decision status separately from application status", async () => {
    const user = userEvent.setup();
    const onDecisionChange = vi.fn();

    render(
      <JobCard
        job={job()}
        selected={false}
        expanded={false}
        customTags={[]}
        tagInput=""
        filterTagList={[]}
        greeted={false}
        statusLabels={statusLabels}
        decisionLabels={decisionLabels}
        onToggleSelected={vi.fn()}
        onToggleDetail={vi.fn()}
        onStatusChange={vi.fn()}
        onDecisionChange={onDecisionChange}
        onRemoveCustomTag={vi.fn()}
        onTagInputChange={vi.fn()}
        onAddCustomTag={vi.fn()}
        onToggleKeywordTag={vi.fn()}
        onAddBlacklist={vi.fn()}
        onDelete={vi.fn()}
      />
    );

    await user.selectOptions(screen.getByLabelText("决策标签"), "recommended");

    expect(onDecisionChange).toHaveBeenCalledWith("recommended");
  });
});
