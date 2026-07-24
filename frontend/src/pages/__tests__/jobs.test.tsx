import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import JobsPage from "../jobs";

const { mockListJobPool } = vi.hoisted(() => ({
  mockListJobPool: vi.fn(async () => ({
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
        keywords: ["Python", "FastAPI", "Redis"],
        structured_summary: "A 科技有限公司·Python 后端工程师 | 深圳 | 20-30K",
        source: "captured",
        source_url: "",
        fetched_at: "2024-01-01T00:00:00Z",
        dedupe_key: "abc123",
      },
    ],
    total: 1,
  })),
}));

vi.mock("../../lib/api", () => ({
  listJobPool: mockListJobPool,
  captureJobs: vi.fn(async () => ({ captured: 1, total: 1 })),
  filterJobPool: vi.fn(async () => ({ jobs: [], total: 0 })),
  addManualJob: vi.fn(async () => ({})),
}));

describe("JobsPage", () => {
  afterEach(() => {
    cleanup();
  });

  it("loads and renders job pool from backend", async () => {
    render(<JobsPage selectedJobId={null} onSelectJob={() => undefined} />);

    await waitFor(() => {
      expect(screen.getByText("Python 后端工程师")).toBeInTheDocument();
    });

    expect(screen.getAllByText(/科技/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("BOSS 抓取")).toBeInTheDocument();
    expect(screen.getByTestId("job-summary-rail")).toBeInTheDocument();
    expect(screen.getByTestId("job-results-region")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选为简历优化目标" })).toBeInTheDocument();
  });

  it("shows empty state when no jobs", async () => {
    mockListJobPool.mockResolvedValueOnce({ jobs: [], total: 0 });

    render(<JobsPage selectedJobId={null} onSelectJob={() => undefined} />);

    await waitFor(() => {
      expect(screen.getByText(/还没有岗位/)).toBeInTheDocument();
    });
  });
});
