export function resolveGreetingBatchActions(input: {
  selectedCount: number;
  hasResumeProfile: boolean;
  isBusy: boolean;
}) {
  const hasSelection = input.selectedCount > 0;
  const canOptimizeResume = hasSelection && input.hasResumeProfile && !input.isBusy;
  let optimizeResumeTitle = "AI 优化简历";
  if (!hasSelection) optimizeResumeTitle = "请先勾选岗位";
  else if (!input.hasResumeProfile) optimizeResumeTitle = "请先上传简历";

  return {
    canOptimizeResume,
    optimizeResumeTitle,
  };
}

export function resolveAutoSendAction(input: {
  autoSendEnabled: boolean;
  loggedIn: boolean;
  selectedCount: number;
  isBusy: boolean;
  safetyBlocked: boolean;
  dailyLimit: number;
  sentToday: number;
  grayBatchAllowed: boolean;
}): { enabled: boolean; reason: string } {
  if (!input.loggedIn) return { enabled: false, reason: "请先验证 BOSS 登录" };
  if (!input.autoSendEnabled) return { enabled: false, reason: "请先开启真实自动发送" };
  if (input.selectedCount === 0) return { enabled: false, reason: "请先选择岗位" };
  if (input.isBusy) return { enabled: false, reason: "正在处理，请稍候" };
  if (input.safetyBlocked) return { enabled: false, reason: "安全阈值未通过" };
  if (input.sentToday >= input.dailyLimit) return { enabled: false, reason: "今日发送额度已用完" };
  if (input.selectedCount > 1 && !input.grayBatchAllowed) return { enabled: false, reason: "灰度模式下请先成功发送 1 个岗位" };
  return { enabled: true, reason: "登录预检通过，可发送" };
}
