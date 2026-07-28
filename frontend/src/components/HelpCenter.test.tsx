import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import HelpCenter from "./HelpCenter";
import { getHelpCenter } from "../lib/api";

vi.mock("../lib/api", () => ({
  getHelpCenter: vi.fn(),
}));

const mockedGetHelpCenter = vi.mocked(getHelpCenter);

describe("HelpCenter", () => {
  beforeEach(() => {
    mockedGetHelpCenter.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  test("接口失败时显示内置帮助和重试入口", async () => {
    mockedGetHelpCenter.mockRejectedValueOnce(new Error("Request failed: 404"));

    render(<HelpCenter show onClose={() => {}} onNavigate={() => {}} />);

    expect(await screen.findByText("帮助内容使用内置版本")).toBeVisible();
    expect(screen.getByText("推荐步骤")).toBeVisible();
    expect(screen.getByText("重试加载")).toBeVisible();
  });

  test("点击重试后展示接口返回的帮助内容", async () => {
    mockedGetHelpCenter
      .mockRejectedValueOnce(new Error("Request failed: 404"))
      .mockResolvedValueOnce({
        kind: "help_center",
        version: 1,
        quickStart: [{ label: "接口帮助", page: "dashboard" }],
        modules: [
          {
            key: "dashboard",
            label: "接口仪表盘",
            purpose: "来自接口的帮助内容。",
            whenToUse: ["接口可用时", "需要最新帮助时"],
            nextStep: "继续使用最新帮助。",
            steps: ["打开帮助", "查看模块", "按提示操作"],
            goodSignals: ["接口已恢复"],
            commonFailures: ["无"],
            safetyNotes: ["按页面提示操作"],
            repairActions: [{ label: "进入仪表盘", page: "dashboard", type: "navigate" }],
          },
        ],
        principles: ["接口原则"],
        faq: [{ question: "接口问题", answer: "接口已恢复。", page: "dashboard" }],
        glossary: [{ term: "接口术语", meaning: "来自接口。" }],
      });

    render(<HelpCenter show onClose={() => {}} onNavigate={() => {}} />);
    await screen.findByText("帮助内容使用内置版本");

    await userEvent.click(screen.getByText("重试加载"));

    expect(await screen.findByText("来自接口的帮助内容。")).toBeVisible();
    await waitFor(() => {
      expect(screen.queryByText("帮助内容使用内置版本")).not.toBeInTheDocument();
    });
  });
});
