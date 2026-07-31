import type { DiligenceReport, JDAnalysis, JobPosting } from "./types";

export type DiligencePrimaryActionKind = "analyze_jd" | "diligence" | "rediligence" | "idle";

export type DiligencePrimaryAction = {
  kind: DiligencePrimaryActionKind;
  label: string;
  targetIds: string[];
  disabled: boolean;
};

export type JdAnalysisAction = {
  label: string;
  targetIds: string[];
  disabled: boolean;
};

type ResolveDiligencePrimaryActionInput = {
  jobs: JobPosting[];
  selectedJobIds: string[];
  jdAnalyses: Record<string, JDAnalysis>;
  diligenceReports: Record<string, DiligenceReport>;
};

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

export function resolveJdAnalysisAction(input: {
  jobs: JobPosting[];
  selectedJobIds: string[];
  jdAnalyses: Record<string, JDAnalysis>;
}): JdAnalysisAction {
  const selectedJobs = input.jobs.filter(job => input.selectedJobIds.includes(job.id));
  if (selectedJobs.length === 0) {
    return { label: "一键 JD 分析", targetIds: [], disabled: true };
  }

  const targetIds = selectedJobs.map(job => job.id);
  const missingCount = selectedJobs.filter(job => !input.jdAnalyses[job.id]).length;
  return {
    label: missingCount > 0 ? `一键 JD 分析 (${missingCount})` : `一键重新分析 JD (${selectedJobs.length})`,
    targetIds,
    disabled: false,
  };
}

export function resolveDiligencePrimaryAction(input: ResolveDiligencePrimaryActionInput): DiligencePrimaryAction {
  const selectedJobs = input.jobs.filter(job => input.selectedJobIds.includes(job.id));
  if (selectedJobs.length === 0) {
    return { kind: "idle", label: "选择岗位后开始", targetIds: [], disabled: true };
  }

  const missingAnalysis = selectedJobs.filter(job => !input.jdAnalyses[job.id]);
  if (missingAnalysis.length > 0) {
    return {
      kind: "analyze_jd",
      label: `一键 JD 分析 (${missingAnalysis.length})`,
      targetIds: missingAnalysis.map(job => job.id),
      disabled: false,
    };
  }

  const missingDiligence = selectedJobs.filter(job => !hasDiligence(job, input.diligenceReports));
  if (missingDiligence.length > 0) {
    return {
      kind: "diligence",
      label: `一键尽调 (${missingDiligence.length})`,
      targetIds: missingDiligence.map(job => job.id),
      disabled: false,
    };
  }

  return {
    kind: "rediligence",
    label: `一键重新公司尽调 (${selectedJobs.length})`,
    targetIds: selectedJobs.map(job => job.id),
    disabled: false,
  };
}
