import type { BusinessInfo, DiligenceReport, JobPosting, RankingResult, WorkflowRuntimeTask } from "./types";

export type WorkflowTaskStatus = "idle" | "running" | "done" | "warning";

export type WorkflowTask = {
  key: "jobs" | "jd" | "diligence" | "ranking" | "greeting";
  label: string;
  done: number;
  total: number;
  status: WorkflowTaskStatus;
};

export type WorkflowTodo = {
  key: "missing_jd" | "missing_diligence" | "missing_ranking" | "missing_greeting";
  label: string;
  count: number;
  page: "jobs" | "diligence" | "ranking" | "greeting";
  action: string;
  description: string;
};

type BuildWorkflowTaskInput = {
  jobs: JobPosting[];
  selectedJobIds: string[];
  diligenceReports: Record<string, DiligenceReport>;
  rankingResults: RankingResult[];
  greetingTexts?: Record<string, string>;
};

function taskStatus(done: number, total: number): WorkflowTaskStatus {
  if (total <= 0) return "idle";
  if (done <= 0) return "idle";
  if (done >= total) return "done";
  return "running";
}

function hasDiligence(job: JobPosting, reports: Record<string, DiligenceReport>): boolean {
  return Boolean(
    reports[job.company] ||
    (job.company_key && reports[job.company_key]) ||
    Object.values(reports).some(report =>
      report.companyName === job.company ||
      report.sourceCompanyName === job.company ||
      (job.company_key && report.companyKey === job.company_key)
    )
  );
}

export function buildWorkflowTasks(input: BuildWorkflowTaskInput): WorkflowTask[] {
  const selectedJobs = input.jobs.filter(job => input.selectedJobIds.includes(job.id));
  const selectedTotal = selectedJobs.length;
  const jdDone = input.jobs.filter(job => Boolean((job.jd_text || "").trim())).length;
  const diligenceDone = selectedJobs.filter(job => hasDiligence(job, input.diligenceReports)).length;
  const rankingDone = input.rankingResults.filter(item => input.selectedJobIds.includes(item.jobId)).length;
  const greetingDone = Object.keys(input.greetingTexts || {}).filter(id => input.selectedJobIds.includes(id)).length;

  return [
    { key: "jobs", label: "岗位池", done: input.jobs.length, total: input.jobs.length, status: taskStatus(input.jobs.length, input.jobs.length) },
    { key: "jd", label: "JD 详情", done: jdDone, total: input.jobs.length, status: taskStatus(jdDone, input.jobs.length) },
    { key: "diligence", label: "公司尽调", done: diligenceDone, total: selectedTotal, status: taskStatus(diligenceDone, selectedTotal) },
    { key: "ranking", label: "综合排序", done: rankingDone, total: selectedTotal, status: taskStatus(rankingDone, selectedTotal) },
    { key: "greeting", label: "打招呼", done: greetingDone, total: selectedTotal, status: taskStatus(greetingDone, selectedTotal) },
  ];
}

export function buildWorkflowTodos(input: BuildWorkflowTaskInput): WorkflowTodo[] {
  const selectedJobs = input.jobs.filter(job => input.selectedJobIds.includes(job.id));
  const selectedTotal = selectedJobs.length;
  const rankingDone = input.rankingResults.filter(item => input.selectedJobIds.includes(item.jobId)).length;
  const greetingDone = Object.keys(input.greetingTexts || {}).filter(id => input.selectedJobIds.includes(id)).length;
  const todos: WorkflowTodo[] = [];

  const missingJd = selectedJobs.filter(job => !(job.jd_text || "").trim()).length;
  if (missingJd > 0) {
    todos.push({
      key: "missing_jd",
      label: "补全 JD",
      count: missingJd,
      page: "jobs",
      action: "继续获取",
      description: `${missingJd} 个已选岗位缺少详情`,
    });
  }

  const missingDiligence = selectedJobs.filter(job => !hasDiligence(job, input.diligenceReports)).length;
  if (missingDiligence > 0) {
    todos.push({
      key: "missing_diligence",
      label: "公司尽调",
      count: missingDiligence,
      page: "diligence",
      action: "去尽调",
      description: `${missingDiligence} 家公司还没有尽调结论`,
    });
  }

  const missingRanking = Math.max(0, selectedTotal - rankingDone);
  if (missingRanking > 0) {
    todos.push({
      key: "missing_ranking",
      label: "综合排序",
      count: missingRanking,
      page: "ranking",
      action: "去排序",
      description: `${missingRanking} 个岗位还没有排序结果`,
    });
  }

  const missingGreeting = Math.max(0, selectedTotal - greetingDone);
  if (missingGreeting > 0) {
    todos.push({
      key: "missing_greeting",
      label: "招呼语",
      count: missingGreeting,
      page: "greeting",
      action: "生成招呼",
      description: `${missingGreeting} 个岗位还没有招呼语`,
    });
  }

  return todos;
}

export function formatApiError(error: unknown): string {
  const payload = error instanceof Error ? error.message : error;
  if (typeof payload === "string") return payload;
  if (!payload || typeof payload !== "object") return "操作失败";

  const detail = "detail" in payload ? (payload as { detail?: unknown }).detail : payload;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const body = detail as { message?: unknown; action?: unknown; code?: unknown };
    const message = typeof body.message === "string" && body.message ? body.message : String(body.code || "操作失败");
    const action = typeof body.action === "string" && body.action ? ` · 建议: ${body.action}` : "";
    return `${message}${action}`;
  }
  return "操作失败";
}

export type RecoveryTask = {
  id: string;
  title: string;
  message: string;
  action: string;
  retryable: boolean;
  status: "failed" | "partial_failed";
};

export function buildRecoveryTasks(tasks: WorkflowRuntimeTask[]): RecoveryTask[] {
  return tasks
    .filter(task => task.status === "failed" || task.status === "partial_failed")
    .map(task => ({
      id: task.id,
      title: task.title,
      message: task.message || "任务未完成",
      action: task.action || (task.retryable ? "检查配置后重试" : "查看详情"),
      retryable: Boolean(task.retryable),
      status: task.status,
    }));
}

function pushField(list: string[], label: string, value?: unknown) {
  if (value === undefined || value === null || value === "") return;
  list.push(`${label}: ${String(value)}`);
}

export function buildDiligenceEvidence(report: DiligenceReport): {
  business: string[];
  risk: string[];
  searchLinks: string[];
  aiSignals: string[];
} {
  const businessInfo = report.businessInfo as BusinessInfo | undefined;
  const business: string[] = [];
  const risk: string[] = [];
  const aiSignals: string[] = [];

  if (businessInfo && !businessInfo.error) {
    pushField(business, "工商名称", businessInfo.companyName || report.companyName);
    pushField(business, "统一信用代码", businessInfo.unifiedCreditCode);
    pushField(business, "法定代表人", businessInfo.legalRepresentative);
    pushField(business, "注册资本", businessInfo.registrationCapital);
    pushField(business, "成立日期", businessInfo.establishedDate);
    pushField(business, "企业状态", businessInfo.businessStatus);
    pushField(business, "所属行业", [businessInfo.industry, businessInfo.subIndustry].filter(Boolean).join(" / "));
    pushField(business, "登记机关", businessInfo.registrationAuthority);

    risk.push(...(businessInfo.abnormalInfo || []));
    risk.push(...(businessInfo.penalties || []));
    risk.push(...(businessInfo.dishonestItems || []));
    risk.push(...(businessInfo.enforcedItems || []));
  }

  if (report.sentiment?.positive?.length) {
    aiSignals.push(...report.sentiment.positive.map(item => `正面: ${item}`));
  }
  if (report.sentiment?.negative?.length) {
    aiSignals.push(...report.sentiment.negative.map(item => `负面: ${item}`));
  }

  return {
    business,
    risk,
    searchLinks: report.sentiment?.evidenceLinks || [],
    aiSignals,
  };
}
