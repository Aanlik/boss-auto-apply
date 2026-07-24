import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./lib/api", () => ({
  listJobPool: vi.fn(async () => ({
    jobs: [
      {
        id: "job-1",
        title: "Python 后端工程师",
        company: "A 科技有限公司",
        city: "深圳",
        salary: "20-30K",
        salary_min: 20,
        salary_max: 30,
        jd_text: "负责 Python、FastAPI、SQLAlchemy 和 Redis 的后端开发。",
        keywords: ["Python", "FastAPI"],
        structured_summary: "A 科技有限公司·Python 后端工程师",
        source: "captured",
        source_url: "",
        fetched_at: "",
        dedupe_key: "x",
      },
    ],
    total: 1,
  })),
  captureJobs: vi.fn(async () => ({ captured: 0, total: 1 })),
  filterJobPool: vi.fn(async () => ({ jobs: [], total: 0 })),
  addManualJob: vi.fn(async () => ({})),
  parseResumeFile: vi.fn(async () => ({ skills: [], target_titles: [] })),
  optimizeResume: vi.fn(async () => ({ summary: "", bullets: [], matched_skills: [], missing_skills: [] })),
}));

describe("App shell", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders a premium workspace shell with explicit panels", () => {
    render(<App />);

    expect(screen.getByTestId("workspace-shell")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-rail")).toBeInTheDocument();
    expect(screen.getByTestId("target-summary")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-stage")).toBeInTheDocument();
  });

  it("persists the selected job and keeps it visible in the shell", async () => {
    const user = userEvent.setup();

    const { unmount } = render(<App />);

    const rail = screen.getByTestId("workspace-rail");
    await user.click(within(rail).getByRole("button", { name: "岗位" }));

    // 等待岗位加载
    const selectBtn = await screen.findByText("Python 后端工程师");
    expect(selectBtn).toBeInTheDocument();

    // 点击选择按钮
    const selectTargetBtn = screen.getByRole("button", { name: "选为简历优化目标" });
    await user.click(selectTargetBtn);

    expect(screen.getByRole("region", { name: "当前目标岗位" })).toHaveTextContent("Python 后端工程师");
    expect(screen.getByRole("region", { name: "当前目标岗位" })).toHaveTextContent("A 科技有限公司");

    await user.click(screen.getByRole("button", { name: "简历" }));
    expect(screen.getByRole("region", { name: "当前目标岗位" })).toHaveTextContent("Python 后端工程师");

    unmount();
    render(<App />);
    expect(screen.getByRole("region", { name: "当前目标岗位" })).toHaveTextContent("Python 后端工程师");
  });
});
