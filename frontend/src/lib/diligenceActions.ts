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

export type CompanyDiligenceAction = {
  label: string;
  targetIds: string[];
  disabled: boolean;
};

function companyIdentity(job: JobPosting): string {
  return String(job.company_key || job.company || "").trim().toLowerCase();
}

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
    targetIds: missingCount > 0
      ? selectedJobs.filter(job => !input.jdAnalyses[job.id]).map(job => job.id)
      : targetIds,
    disabled: false,
  };
}

export function resolveCompanyDiligenceAction(input: {
  jobs: JobPosting[];
  selectedJobIds: string[];
  diligenceReports: Record<string, DiligenceReport>;
}): CompanyDiligenceAction {
  const selectedJobs = input.jobs.filter(job => input.selectedJobIds.includes(job.id));
  if (selectedJobs.length === 0) {
    return { label: "一键公司尽调", targetIds: [], disabled: true };
  }

  const missingJobs = selectedJobs.filter(job => !hasDiligence(job, input.diligenceReports));
  const missingCompanies = new Set<string>();
  const missingTargetIds = missingJobs.filter(job => {
    const key = companyIdentity(job);
    if (missingCompanies.has(key)) return false;
    missingCompanies.add(key);
    return true;
  }).map(job => job.id);
  const rerunCompanies = new Set<string>();
  const rerunTargetIds = selectedJobs.filter(job => {
    const key = companyIdentity(job);
    if (rerunCompanies.has(key)) return false;
    rerunCompanies.add(key);
    return true;
  }).map(job => job.id);
  return {
    label: missingJobs.length > 0 ? `一键公司尽调 (${missingTargetIds.length})` : `一键重新公司尽调 (${rerunTargetIds.length})`,
    targetIds: missingJobs.length > 0 ? missingTargetIds : rerunTargetIds,
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
      label: "AI 分析 JD",
      targetIds: missingAnalysis.map(job => job.id),
      disabled: false,
    };
  }

  const missingDiligence = selectedJobs.filter(job => !hasDiligence(job, input.diligenceReports));
  if (missingDiligence.length > 0) {
    return {
      kind: "diligence",
      label: "公司尽调",
      targetIds: missingDiligence.map(job => job.id),
      disabled: false,
    };
  }

  return {
    kind: "rediligence",
    label: "重新公司尽调",
    targetIds: selectedJobs.map(job => job.id),
    disabled: false,
  };
}
