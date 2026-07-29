import { describe, expect, test } from "vitest";
import { resolveGreetingBatchActions } from "./greetingActions";

describe("resolveGreetingBatchActions", () => {
  test("disables resume optimization when no jobs are selected", () => {
    const actions = resolveGreetingBatchActions({
      selectedCount: 0,
      hasResumeProfile: true,
      isBusy: false,
    });

    expect(actions.canOptimizeResume).toBe(false);
    expect(actions.optimizeResumeTitle).toBe("请先勾选岗位");
  });

  test("enables resume optimization when a resume and selected jobs exist", () => {
    const actions = resolveGreetingBatchActions({
      selectedCount: 2,
      hasResumeProfile: true,
      isBusy: false,
    });

    expect(actions.canOptimizeResume).toBe(true);
    expect(actions.optimizeResumeTitle).toBe("AI 优化简历");
  });
});
