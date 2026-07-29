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
