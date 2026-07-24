import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import ResumesPage from "../resumes";
import type { JobPosting } from "../../lib/types";

const makeJob = (overrides: Partial<JobPosting> = {}): JobPosting => ({
  id: "job-1",
  title: "Python 后端工程师",
  company: "A 公司",
  city: "深圳",
  salary: "20-30K",
  salary_min: 20,
  salary_max: 30,
  jd_text: "负责 Python、FastAPI、SQLAlchemy 和 Redis 的后端开发，参与支付系统与订单系统建设。",
  keywords: ["Python", "FastAPI", "Redis"],
  structured_summary: "A 公司·Python 后端工程师 | 深圳 | 20-30K",
  source: "captured",
  source_url: "",
  fetched_at: "",
  dedupe_key: "abc",
  ...overrides,
});

vi.mock("../../lib/api", () => ({
  parseResumeFile: vi.fn(async () => ({
    name: "张三",
    title: "Python 后端工程师",
    skills: ["Python", "FastAPI", "Docker"],
    target_titles: ["后端工程师"],
    summary: "3年Python后端开发经验",
    work_experience: [
      {
        company: "A 公司",
        title: "后端工程师",
        duration: "2021.06 - 至今",
        description: "负责支付系统开发",
      },
    ],
    education: [{ institution: "清华大学", degree: "本科", major: "计算机科学", graduation: "2021" }],
    projects: [{ name: "支付网关", description: "三方支付对接", technologies: ["FastAPI", "Redis"] }],
  })),
  optimizeResume: vi.fn(async () => ({
    summary: "面向 Python 后端工程师（A 公司）：你的技能 Python, FastAPI 与 JD 高度匹配，重点强化项目成果表述。",
    bullets: [
      "保持并突出 Python, FastAPI 的项目成果",
      "保留真实经历，不新增虚构内容",
    ],
    matched_skills: ["Python", "FastAPI"],
    missing_skills: ["Redis"],
  })),
}));

describe("ResumesPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("parses and optimizes resume content", async () => {
    const user = userEvent.setup();

    render(<ResumesPage selectedJob={makeJob()} />);

    const file = new File(["张三\nPython 后端工程师\n技能: Python, FastAPI"], "resume.txt", {
      type: "text/plain",
    });
    await user.upload(screen.getByLabelText("resume-upload"), file);

    await waitFor(() => {
      expect(screen.getByText("张三")).toBeInTheDocument();
    });

    expect(screen.getAllByText("后端工程师").length).toBeGreaterThanOrEqual(1);

    await user.click(screen.getByRole("button", { name: "生成优化建议" }));

    await waitFor(() => {
      expect(screen.getByText(/与 JD 高度匹配/)).toBeInTheDocument();
    });
    expect(screen.getByText("已匹配技能")).toBeInTheDocument();
    expect(screen.getByText("缺失技能")).toBeInTheDocument();
    expect(screen.getAllByText("Redis").length).toBeGreaterThanOrEqual(2);
  });

  it("shows the selected target and result panels together", () => {
    render(<ResumesPage selectedJob={makeJob()} />);

    expect(screen.getByTestId("resume-summary-rail")).toBeInTheDocument();
    expect(screen.getByTestId("resume-output-region")).toBeInTheDocument();
    expect(screen.getByText("上传简历后这里会显示结构化解析结果。")).toBeInTheDocument();
  });

  it("blocks optimization when no job is selected", () => {
    render(<ResumesPage selectedJob={null} />);

    const btn = screen.getByRole("button", { name: "请先选择岗位" });
    expect(btn).toBeDisabled();
  });
});
