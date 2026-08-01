import { describe, expect, test } from "vitest";
import { resolveAutoSendAction, resolveGreetingBatchActions } from "./greetingActions";

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

describe("resolveAutoSendAction", () => {
  test("blocks automatic sending until the BOSS login preflight has succeeded", () => {
    expect(resolveAutoSendAction({
      autoSendEnabled: true,
      loggedIn: false,
      selectedCount: 1,
      isBusy: false,
      safetyBlocked: false,
      dailyLimit: 15,
      sentToday: 0,
      grayBatchAllowed: true,
    })).toEqual({ enabled: false, reason: "请先验证 BOSS 登录" });
  });

  test("blocks automatic sending when today's configured quota is exhausted", () => {
    const action = resolveAutoSendAction({
      autoSendEnabled: true,
      loggedIn: true,
      selectedCount: 1,
      isBusy: false,
      safetyBlocked: false,
      dailyLimit: 15,
      sentToday: 15,
      grayBatchAllowed: true,
    } as Parameters<typeof resolveAutoSendAction>[0]);

    expect(action).toEqual({ enabled: false, reason: "今日发送额度已用完" });
  });

  test("blocks a multi-job batch until gray-mode verification has passed", () => {
    const action = resolveAutoSendAction({
      autoSendEnabled: true,
      loggedIn: true,
      selectedCount: 2,
      isBusy: false,
      safetyBlocked: false,
      dailyLimit: 15,
      sentToday: 0,
      grayBatchAllowed: false,
    } as Parameters<typeof resolveAutoSendAction>[0]);

    expect(action).toEqual({ enabled: false, reason: "灰度模式下请先成功发送 1 个岗位" });
  });
});
