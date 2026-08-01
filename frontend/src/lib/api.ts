import type { AiFeedbackDomain, AiFeedbackRecord, AiFeedbackSummary, AiPreferenceProfile, ApplicationBoard, ApplicationFunnel, ApplicationStrategy, ApplicationTimeline, AssistantPromptVersionCompare, AssistantPromptVersions, BossCaptureFilters, BossFilterOptions, BossLoginStatus, CompanyBlacklistItem, DashboardSummary, DashboardTrendReport, DataQualityCenter, DataQualityRepairResult, DeepReportSections, FollowupReminder, GreetingAcceptancePlan, GreetingAcceptanceRecord, GreetingAutoSendSettings, GreetingCandidateResponse, GreetingFinalConfirmation, GreetingFollowups, GreetingFrequencyProfile, GreetingPreflight, GreetingProgress, GreetingReplyRecord, GreetingSafetySummary, GreetingSelectorHealth, GreetingSendResponse, GreetingStats, GreetingTemplateEffectiveness, GreetingValidationResult, HelpCenter, InterviewPrep, JdQualityInsight, JobApplicationStatus, JobComparison, JobDecisionStatus, JobPosting, JobPoolQuality, JobSearchPreset, JobsImportWizard, OnboardingWizard, PdfTemplateRecommendation, ProviderConfig, ProviderPreset, RankingWeightTemplate, RankingWeights, ResumeRewriteAdvice, ResumeVersion, RiskExplanation, UserPreferences, WeeklyReport, WorkflowCenter, WorkflowHealthCheck, WorkflowRuntimeTask } from "./types";
import { formatApiError } from "./workflowInsights";

// ---------- 简历 ----------

export async function getHelpCenter(): Promise<HelpCenter> {
  return fetchJson("/api/help/center");
}

export async function parseResumeFile(file: File): Promise<{
  profile: import("./types").ResumeProfile;
  raw_text: string;
  file_id: string;
  parse_status?: string;
}> {
  const form = new FormData();
  form.append("file", file);
  return fetchJson("/api/resumes/parse", { method: "POST", body: form });
}

// ---------- 岗位 ----------

export async function listJobPool(includeHidden = false): Promise<{ jobs: JobPosting[]; total: number; hidden?: number }> {
  return fetchJson(`/api/jobs/pool${includeHidden ? "?include_hidden=true" : ""}`);
}

export async function getJobPoolQuality(): Promise<JobPoolQuality> {
  return fetchJson("/api/jobs/pool/quality");
}

export function exportJobsUrl(format: "json" | "csv" = "json"): string {
  return `/api/jobs/export?format=${format}`;
}

export function jobsImportTemplateUrl(): string {
  return "/api/jobs/import-wizard/template";
}

export async function previewJobsImport(payload: { text?: string; items?: Array<Record<string, unknown>> }): Promise<JobsImportWizard> {
  return fetchJson("/api/jobs/import-wizard/preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function applyJobsImport(payload: { text?: string; items?: Array<Record<string, unknown>> }): Promise<{ imported: number; skipped: number; total: number; preview: JobsImportWizard }> {
  return fetchJson("/api/jobs/import-wizard/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listBossCities(): Promise<{ cities: Array<{ name: string; code: string }>; total: number }> {
  return fetchJson("/api/jobs/cities");
}

export async function listBossFilterOptions(): Promise<BossFilterOptions> {
  return fetchJson("/api/jobs/capture/boss/filter-options");
}

export async function listJobSearchPresets(): Promise<{ presets: JobSearchPreset[]; total: number }> {
  return fetchJson("/api/jobs/search-presets");
}

export async function saveJobSearchPreset(payload: Partial<JobSearchPreset>): Promise<{ preset: JobSearchPreset; total: number }> {
  return fetchJson("/api/jobs/search-presets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteJobSearchPreset(presetId: string): Promise<{ deleted: string; total: number }> {
  return fetchJson(`/api/jobs/search-presets/${presetId}`, { method: "DELETE" });
}

export async function listDeletedJobs(): Promise<{ jobs: Array<{ id: string; deletedAt: string; job: JobPosting }>; total: number }> {
  return fetchJson("/api/jobs/deleted");
}

export async function restoreDeletedJobs(jobIds: string[]): Promise<{ restored: number; total: number }> {
  return fetchJson("/api/jobs/restore", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export async function captureBossJobs(
  payload: { keyword?: string; city?: string; max_pages?: number; filters?: BossCaptureFilters } = {}
): Promise<{ captured: number; total: number }> {
  return fetchJson("/api/jobs/capture/boss", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function bossLoginStatus(): Promise<BossLoginStatus> {
  return fetchJson("/api/jobs/capture/boss/status");
}

export async function bossLogin(): Promise<{ status: string; message: string }> {
  return fetchJson("/api/jobs/capture/boss/login", { method: "POST" });
}

export async function enrichJdDetails(payload: { job_ids?: string[]; max_jobs?: number; force?: boolean } = {}): Promise<{ enriched: number; skipped_existing_jd?: number; message: string }> {
  return fetchJson("/api/jobs/enrich-jd", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listCompanyBlacklist(): Promise<{ companies: CompanyBlacklistItem[]; total: number }> {
  return fetchJson("/api/jobs/company-blacklist");
}

export async function addCompanyBlacklist(companyName: string): Promise<{ companies: CompanyBlacklistItem[]; total: number; removed: number }> {
  return fetchJson("/api/jobs/company-blacklist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company_name: companyName }),
  });
}

export async function deleteCompanyBlacklist(companyName: string): Promise<{ companies: CompanyBlacklistItem[]; total: number; restored: number }> {
  return fetchJson("/api/jobs/company-blacklist", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company_name: companyName }),
  });
}

export async function exportCompanyBlacklist(): Promise<{ kind: string; companies: CompanyBlacklistItem[]; total: number }> {
  return fetchJson("/api/jobs/company-blacklist/export");
}

export async function importCompanyBlacklist(payload: unknown): Promise<{ companies: CompanyBlacklistItem[]; total: number; removed: number }> {
  return fetchJson("/api/jobs/company-blacklist/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function cleanupExpiredJobs(jobIds?: string[]): Promise<{ deleted: number; total: number }> {
  return fetchJson("/api/jobs/expired/cleanup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds || [] }),
  });
}

export async function keepExpiredJobs(jobIds?: string[]): Promise<{ updated: number; total: number }> {
  return fetchJson("/api/jobs/expired/keep", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds || [] }),
  });
}

export async function mergeDuplicateJobs(jobIds: string[]): Promise<{ kept: string; removed: string[]; job: JobPosting; total: number }> {
  return fetchJson("/api/jobs/duplicates/merge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export async function compareJobs(jobIds: string[]): Promise<JobComparison> {
  return fetchJson("/api/jobs/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export async function getApplicationFunnel(): Promise<ApplicationFunnel> {
  return fetchJson("/api/jobs/funnel");
}

export async function getApplicationTimeline(): Promise<ApplicationTimeline> {
  return fetchJson("/api/jobs/application-timeline");
}

export async function getApplicationBoard(): Promise<ApplicationBoard> {
  return fetchJson("/api/jobs/application-board");
}

export async function updateJobApplicationStatus(
  jobId: string,
  status: JobApplicationStatus,
  note = ""
): Promise<{ job_id: string; application_status: JobApplicationStatus; application_note: string; application_updated_at: string; greeted: boolean }> {
  return fetchJson("/api/jobs/status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, status, note }),
  });
}

export async function moveApplicationBoardJob(
  jobId: string,
  status: JobApplicationStatus,
  note = ""
): Promise<{ job_id: string; application_status: JobApplicationStatus; application_note: string; application_updated_at: string; greeted: boolean; board: ApplicationBoard }> {
  return fetchJson("/api/jobs/application-board/move", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, status, note }),
  });
}

export async function updateJobDecisionStatus(
  jobId: string,
  status: JobDecisionStatus
): Promise<{ job_id: string; decision_status: JobDecisionStatus }> {
  return fetchJson("/api/jobs/decision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, status }),
  });
}

// ---------- 其余 ----------

export async function evaluateCompany(payload: unknown) {
  return fetchJson("/api/diligence/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function refreshDiligence(payload: {
  company_name: string;
  mode: "full" | "business" | "search";
  job_title?: string;
  jd_text?: string;
  jd_analysis?: unknown;
}) {
  return fetchJson("/api/diligence/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getDiligenceReports(): Promise<{ reports: Record<string, import("./types").DiligenceReport> }> {
  return fetchJson("/api/diligence/reports");
}

export function exportDiligenceUrl(format: "json" | "csv" = "json"): string {
  return `/api/diligence/export?format=${format}`;
}

export async function saveDiligenceNote(companyName: string, note: string): Promise<import("./types").DiligenceReport | { error: string }> {
  return fetchJson("/api/diligence/note", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company_name: companyName, note }),
  });
}

export async function rankJobs(jobIds: string[], resume: unknown, diligenceReports: Record<string, unknown>, weights?: RankingWeights) {
  return fetchJson("/api/scoring/rank", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds, resume, diligence_reports: diligenceReports, weights }),
  });
}

export async function getRankingResults(): Promise<{ rankings: import("./types").RankingResult[] }> {
  return fetchJson("/api/scoring/rankings");
}

export function exportRankingsUrl(format: "json" | "csv" = "json"): string {
  return `/api/scoring/rankings/export?format=${format}`;
}

export async function getRankingWeights(): Promise<{ weights: RankingWeights }> {
  return fetchJson("/api/scoring/weights");
}

export async function getRankingWeightTemplates(): Promise<{ templates: Record<string, RankingWeightTemplate> }> {
  return fetchJson("/api/scoring/weights/templates");
}

export async function saveRankingWeights(weights: RankingWeights): Promise<{ weights: RankingWeights }> {
  return fetchJson("/api/scoring/weights", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(weights),
  });
}

export async function listWorkflowTasks(): Promise<{ tasks: WorkflowRuntimeTask[] }> {
  return fetchJson("/api/workflow/tasks");
}

export async function getWorkflowCenter(): Promise<WorkflowCenter> {
  return fetchJson("/api/workflow/center");
}

export async function getWorkflowHealthCheck(): Promise<WorkflowHealthCheck> {
  return fetchJson("/api/workflow/health-check");
}

export async function retryWorkflowTask(taskId: string): Promise<{ task: WorkflowRuntimeTask; sourceTask: WorkflowRuntimeTask }> {
  return fetchJson(`/api/workflow/tasks/${taskId}/retry`, { method: "POST" });
}

export async function clearFailedWorkflowTasks(): Promise<{ removed: number; remaining: number }> {
  return fetchJson("/api/workflow/tasks/failed", { method: "DELETE" });
}

export async function deleteWorkflowTask(taskId: string): Promise<{ deleted: boolean; task: WorkflowRuntimeTask; remaining: number }> {
  return fetchJson(`/api/workflow/tasks/${taskId}`, { method: "DELETE" });
}

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return fetchJson("/api/dashboard/summary");
}

export async function getOnboardingGuide(): Promise<import("./types").OnboardingGuide> {
  return fetchJson("/api/dashboard/onboarding");
}

export async function getOnboardingWizard(): Promise<import("./types").OnboardingWizard> {
  return fetchJson("/api/dashboard/onboarding/wizard");
}

export async function getReviewCenter(): Promise<import("./types").ReviewCenter> {
  return fetchJson("/api/dashboard/review-center");
}

export async function getWeeklyReport(days = 7): Promise<WeeklyReport> {
  return fetchJson(`/api/dashboard/weekly-report?days=${Math.max(1, Math.min(30, days))}`);
}

export async function getDashboardTrends(days = 30): Promise<DashboardTrendReport> {
  return fetchJson(`/api/dashboard/trends?days=${Math.max(1, Math.min(90, days))}`);
}

export async function getDataQualityCenter(): Promise<DataQualityCenter> {
  return fetchJson("/api/dashboard/data-quality");
}

export async function repairDataQuality(actions: string[] = []): Promise<DataQualityRepairResult> {
  return fetchJson("/api/dashboard/data-quality/repair", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actions }),
  });
}

export async function getApplicationStrategy(payload: {
  job_id?: string;
  job?: unknown;
  resume?: unknown;
  diligence?: unknown;
  ranking?: unknown;
}): Promise<ApplicationStrategy> {
  return fetchJson("/api/assistant/application-strategy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getJdQuality(payload: { job: unknown }): Promise<JdQualityInsight> {
  return fetchJson("/api/assistant/jd-quality", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getResumeRewriteAdvice(payload: { job: unknown; resume?: unknown; diligence?: unknown }): Promise<ResumeRewriteAdvice> {
  return fetchJson("/api/assistant/resume-rewrite-advice", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getInterviewPrep(payload: { job: unknown; resume?: unknown; diligence?: unknown }): Promise<InterviewPrep> {
  return fetchJson("/api/assistant/interview-prep", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getFollowups(): Promise<{ reminders: FollowupReminder[]; generatedAt: string }> {
  return fetchJson("/api/assistant/followups");
}

export async function getRiskExplanation(payload: { diligence: unknown }): Promise<RiskExplanation> {
  return fetchJson("/api/assistant/risk-explanation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getAssistantDeepReport(payload: { job: unknown; resume?: unknown; diligence?: unknown; ranking?: unknown }): Promise<unknown> {
  return fetchJson("/api/assistant/deep-report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getAssistantPromptVersions(kind = ""): Promise<AssistantPromptVersions> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return fetchJson(`/api/assistant/prompt-versions${query}`);
}

export async function compareAssistantPromptVersions(jobId = "", kind = "deep_report"): Promise<AssistantPromptVersionCompare> {
  const qs = new URLSearchParams();
  if (jobId) qs.set("job_id", jobId);
  if (kind) qs.set("kind", kind);
  return fetchJson(`/api/assistant/prompt-versions/compare?${qs.toString()}`);
}

export async function clearAssistantPromptVersions(kind = ""): Promise<{ deleted: number; remaining: number }> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return fetchJson(`/api/assistant/prompt-versions${query}`, { method: "DELETE" });
}

export async function deleteAssistantPromptVersion(recordId: string): Promise<{ deleted: boolean; remaining: number }> {
  return fetchJson(`/api/assistant/prompt-versions/${encodeURIComponent(recordId)}`, { method: "DELETE" });
}

export function exportAssistantDeepReportUrl(jobId = "", format: "md" | "json" | "pdf" = "md"): string {
  const qs = new URLSearchParams();
  if (jobId) qs.set("job_id", jobId);
  qs.set("format", format);
  return `/api/assistant/deep-report/export?${qs.toString()}`;
}

export async function editAssistantDeepReport(payload: { job_id: string; summary: string; sections?: DeepReportSections; notes?: string[] }): Promise<{ record: unknown }> {
  return fetchJson("/api/assistant/deep-report/edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function saveAiFeedback(payload: {
  domain: AiFeedbackDomain;
  targetId: string;
  useful: boolean;
  note?: string;
  context?: Record<string, unknown>;
}): Promise<{ record: AiFeedbackRecord }> {
  return fetchJson("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getAiFeedbackSummary(): Promise<AiFeedbackSummary> {
  return fetchJson("/api/feedback/summary");
}

export async function getAiPreferenceProfile(): Promise<AiPreferenceProfile> {
  return fetchJson("/api/feedback/preference-profile");
}

export async function getGreetingDrafts(): Promise<{ greetings: Record<string, string> }> {
  return fetchJson("/api/greetings/drafts");
}

export async function getGreetingAutoSendSettings(): Promise<{ settings: GreetingAutoSendSettings; profiles: GreetingFrequencyProfile[] }> {
  return fetchJson("/api/greetings/auto-send-settings");
}

export async function getGreetingSafetySummary(): Promise<GreetingSafetySummary> {
  return fetchJson("/api/greetings/safety-summary");
}

export async function getGreetingFinalConfirmation(payload: {
  job_ids: string[];
  messages: Record<string, string>;
  mode?: "manual_confirm" | "browser_auto";
  daily_limit?: number;
  batch_limit?: number;
}): Promise<GreetingFinalConfirmation> {
  return fetchJson("/api/greetings/final-confirmation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function saveGreetingAutoSendSettings(payload: Partial<GreetingAutoSendSettings>): Promise<{ settings: GreetingAutoSendSettings; profiles: GreetingFrequencyProfile[] }> {
  return fetchJson("/api/greetings/auto-send-settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getGreetingFrequencyProfiles(): Promise<{ profiles: GreetingFrequencyProfile[] }> {
  return fetchJson("/api/greetings/frequency-profiles");
}

export async function preflightGreetings(payload: { job_ids: string[]; messages: Record<string, string>; mode?: "manual_confirm" | "browser_auto" }): Promise<GreetingPreflight> {
  return fetchJson("/api/greetings/preflight", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getGreetingProgress(): Promise<GreetingProgress> {
  return fetchJson("/api/greetings/progress");
}

export async function controlGreetingSend(action: "pause" | "resume" | "stop"): Promise<{ control: GreetingProgress["control"] }> {
  return fetchJson("/api/greetings/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
}

export async function getGreetingStats(): Promise<GreetingStats> {
  return fetchJson("/api/greetings/stats");
}

export async function checkGreetingSelectorHealth(jobId: string): Promise<GreetingSelectorHealth> {
  return fetchJson("/api/greetings/selector-health", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId }),
  });
}

export async function getGreetingAcceptancePlan(jobId: string): Promise<GreetingAcceptancePlan> {
  return fetchJson("/api/greetings/acceptance-plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId }),
  });
}

export async function getGreetingFollowups(): Promise<GreetingFollowups> {
  return fetchJson("/api/greetings/followups");
}

export async function getGreetingAcceptanceRecords(): Promise<{ summary: { total: number }; records: GreetingAcceptanceRecord[] }> {
  return fetchJson("/api/greetings/acceptance-records");
}

export async function saveGreetingAcceptanceRecord(payload: {
  job_id: string;
  result: "passed" | "failed" | "partial";
  operator?: string;
  note?: string;
  checks?: Array<{ key: string; status: string; note?: string }>;
}): Promise<{ record: GreetingAcceptanceRecord }> {
  return fetchJson("/api/greetings/acceptance-records", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getGreetingReplies(): Promise<{ summary: { total: number; positive: number; neutral: number; negative: number }; records: GreetingReplyRecord[] }> {
  return fetchJson("/api/greetings/replies");
}

export async function getGreetingTemplateEffectiveness(): Promise<GreetingTemplateEffectiveness> {
  return fetchJson("/api/greetings/template-effectiveness");
}

export async function saveGreetingReply(payload: {
  job_id: string;
  reply_type: "positive" | "neutral" | "negative";
  content?: string;
  next_action?: string;
}): Promise<{ record: GreetingReplyRecord }> {
  return fetchJson("/api/greetings/replies", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getGreetingCandidates(jobIds: string[]): Promise<GreetingCandidateResponse> {
  return fetchJson("/api/greetings/candidates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export async function validateGreetingMessages(items: Array<{ job_id: string; message: string }>): Promise<{ results: GreetingValidationResult[]; summary: { total: number; ok: number; failed: number } }> {
  return fetchJson("/api/greetings/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
}

export async function sendGreetingConfirmations(payload: {
  job_ids: string[];
  messages: Record<string, string>;
  confirm: boolean;
  mode?: "manual_confirm" | "browser_auto";
  batch_limit?: number;
  daily_limit?: number;
  send_interval_seconds?: number;
  stop_on_blocked?: boolean;
}): Promise<GreetingSendResponse> {
  return fetchJson("/api/greetings/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function saveGreetingDrafts(greetings: Record<string, string>): Promise<{ greetings: Record<string, string> }> {
  return fetchJson("/api/greetings/drafts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ greetings }),
  });
}

export async function generateGreeting(payload: {
  job_id: string;
  resume: import("./types").ResumeProfile;
  jd_analysis?: import("./types").JDAnalysis | null;
  style?: string;
}): Promise<{ jobId: string; message: string; source: string }> {
  return fetchJson("/api/greetings/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getSendRecords(): Promise<{ records: Array<{ jobId: string; status: string; note: string; updatedAt: string }> }> {
  return fetchJson("/api/greetings/send-records");
}

export async function confirmSendRecord(jobId: string, note = "人工确认已打招呼"): Promise<{ record: { jobId: string; status: string; note: string; updatedAt: string } }> {
  return fetchJson("/api/greetings/send-records", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, status: "sent", note }),
  });
}

export async function updateSendRecord(jobId: string, status: "sent" | "pending", note = ""): Promise<{ record: { jobId: string; status: string; note: string; updatedAt: string } }> {
  return fetchJson("/api/greetings/send-records", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, status, note }),
  });
}

// ---------- 内部 ----------

let activeControllers: Set<AbortController> = new Set();

function getSignal(): { signal: AbortSignal; done: () => void } {
  const ctrl = new AbortController();
  activeControllers.add(ctrl);
  return { signal: ctrl.signal, done: () => activeControllers.delete(ctrl) };
}

async function fetchJson(input: RequestInfo | URL, init?: RequestInit) {
  const { signal, done } = getSignal();
  try {
    const response = await fetch(input, { ...init, signal });
    if (!response.ok) {
      let detail = `Request failed: ${response.status}`;
      try {
        const errBody = await response.json();
        if (errBody.detail) detail = formatApiError(errBody);
      } catch {}
      throw new Error(detail);
    }
    const data = await response.json();
    if (data && typeof data === "object" && "error" in data && data.error) {
      throw new Error(String(data.error));
    }
    return data;
  } finally {
    done();
  }
}

export async function deleteJob(jobId: string): Promise<{ deleted: string; total: number }> {
  return fetchJson(`/api/jobs/${jobId}`, { method: "DELETE" });
}

export async function tagJob(jobId: string, payload: { greeted?: boolean; tags?: string[] }): Promise<{ job_id: string; greeted: boolean; tags: string[] }> {
  return fetchJson("/api/jobs/tag", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_id: jobId, ...payload }),
  });
}

export async function deleteBatchJobs(jobIds: string[]): Promise<{ deleted: number; total: number }> {
  return fetchJson("/api/jobs/batch", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ job_ids: jobIds }),
  });
}

export async function clearAllJobs(): Promise<{ deleted: number; total: number }> {
  return fetchJson("/api/jobs", { method: "DELETE" });
}

export async function evaluateResume(profile: unknown, resumeText = "", chatHistory?: Array<{role: string; content: string}>): Promise<import("./types").ResumeEvaluation> {
  return fetchJson("/api/resumes/evaluate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile, resume_text: resumeText, chat_history: chatHistory || [] }),
  });
}

export async function analyzeJD(payload: { job_id?: string; title: string; company: string; jd_text: string }, chatHistory?: Array<{role: string; content: string}>): Promise<import("./types").JDAnalysis> {
  return fetchJson("/api/resumes/analyze-jd", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload, chat_history: chatHistory || [] }),
  });
}

export async function aiOptimizeResume(
  profile: unknown,
  targetJob: unknown,
  evaluation?: unknown,
  jdAnalysis?: unknown,
  chatHistory?: Array<{role: string; content: string}>,
): Promise<import("./types").ResumeOptimizationResult> {
  return fetchJson("/api/resumes/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile,
      target_job: targetJob,
      evaluation,
      jd_analysis: jdAnalysis,
      chat_history: chatHistory || [],
    }),
  });
}

export async function listResumeOptimizations(): Promise<{ optimizations: Record<string, import("./types").ResumeOptimizationResult>; total: number }> {
  return fetchJson("/api/resumes/optimizations");
}

// === 附件管理 ===
export async function loadResume(fileId: string): Promise<{
  profile: import("./types").ResumeProfile;
  raw_text: string;
  file_id: string;
  eval: unknown;
  jd: unknown;
  optimization: unknown;
  parse_status?: string;
}> {
  return fetchJson(`/api/resumes/load/${fileId}`, { method: "POST" });
}

export async function getActiveResume(): Promise<{
  profile: import("./types").ResumeProfile | null;
  raw_text: string;
  file_id: string;
  eval: unknown;
  jd: unknown;
  optimization: unknown;
  parse_status?: string;
}> {
  return fetchJson("/api/resumes/active");
}

export async function listUploadedFiles(): Promise<{ files: import("./types").UploadedFile[] }> {
  return fetchJson("/api/resumes/files");
}

export async function deleteUploadedFile(fileId: string): Promise<{ deleted: string }> {
  return fetchJson(`/api/resumes/files/${fileId}`, { method: "DELETE" });
}

export async function reEnrichResume(): Promise<{ status: string; message: string }> {
  return fetchJson("/api/resumes/re-enrich", { method: "POST" });
}

export async function updateProfile(profile: unknown, fileId?: string): Promise<{ updated: boolean }> {
  return fetchJson("/api/resumes/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile, file_id: fileId || "" }),
  });
}

// === 设置 ===
export async function getProviderConfig(): Promise<ProviderConfig> {
  return fetchJson("/api/settings/provider");
}

export async function getProviderPresets(): Promise<{ presets: Record<string, ProviderPreset> }> {
  return fetchJson("/api/settings/provider/presets");
}

export async function saveProviderConfig(
  provider: string,
  apiKey: string,
  baseUrl: string = "",
  model: string = ""
): Promise<{ configured: boolean; message: string }> {
  return fetchJson("/api/settings/provider", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider, api_key: apiKey, base_url: baseUrl, model }),
  });
}

export async function clearProviderConfig(): Promise<{ configured: boolean; message: string }> {
  return fetchJson("/api/settings/provider", { method: "DELETE" });
}

export async function testProviderConnection(): Promise<{ ok: boolean; message: string }> {
  return fetchJson("/api/settings/provider/test", { method: "POST" });
}

export async function exportResumePdf(payload: {
  profile: unknown;
  optimization: unknown;
  company: string;
  job_title: string;
  template?: "modern" | "classic" | "ats";
  density?: string;
}): Promise<void> {
  const { signal, done } = getSignal();
  try {
    const response = await fetch("/api/resumes/export-pdf", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      let detail = `导出失败: ${response.status}`;
      try {
        const errBody = await response.json();
        if (errBody.detail) detail = errBody.detail;
      } catch {}
      throw new Error(detail);
    }
    // 从 Content-Disposition 提取文件名（RFC 5987 优先）
    const disposition = response.headers.get("Content-Disposition") || "";
    let filename = "简历.pdf";
    const rfc5987 = disposition.match(/filename\*=UTF-8''(.+)/i);
    if (rfc5987) {
      try { filename = decodeURIComponent(rfc5987[1]); } catch {}
    } else {
      const simple = disposition.match(/filename="?([^";\s]+)/);
      if (simple?.[1]) filename = simple[1];
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } finally {
    done();
  }
}

export async function previewResumePdf(payload: {
  profile: unknown;
  optimization: unknown;
  company: string;
  job_title: string;
  template?: "modern" | "classic" | "ats";
  density?: string;
}): Promise<string> {
  const response = await fetch("/api/resumes/preview-pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let detail = `预览失败: ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
  return URL.createObjectURL(await response.blob());
}

export async function recommendPdfTemplate(payload: { job_title?: string; title?: string; profile?: unknown }): Promise<PdfTemplateRecommendation> {
  return fetchJson("/api/resumes/pdf-template/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listPdfTemplates(): Promise<{ templates: Record<string, { name: string; description: string; font: string; density: string; bestFor: string[]; layout: string }>; default: string }> {
  return fetchJson("/api/resumes/pdf-templates");
}

export async function getPdfPreviewOptions(): Promise<{
  templates: Record<string, { name: string; description: string; font: string; density: string; bestFor: string[]; layout: string }>;
  defaultTemplate: "modern" | "classic" | "ats";
  densityOptions: Array<{ key: string; label: string; description: string }>;
  defaultDensity: string;
}> {
  return fetchJson("/api/resumes/pdf-preview-options");
}

export async function listResumeVersions(): Promise<{ versions: ResumeVersion[] }> {
  return fetchJson("/api/resumes/versions");
}

export async function saveResumeVersion(payload: { label: string; profile?: unknown }): Promise<{ versions: ResumeVersion[] }> {
  return fetchJson("/api/resumes/versions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function compareResumeVersions(payload: { from_index: number; to_index: number }): Promise<{ changedFields: string[]; summary: string[]; from: ResumeVersion; to: ResumeVersion }> {
  return fetchJson("/api/resumes/versions/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function chatWithAI(payload: {
  step: string;
  context: unknown;
  messages: Array<{ role: string; content: string }>;
  profile_name?: string;
}): Promise<{ reply: string }> {
  return fetchJson("/api/resumes/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// === 腾讯云工商 API 配置 ===
export async function getBusinessConfig(): Promise<{ configured: boolean; masked: string; endpoint: string }> {
  return fetchJson("/api/settings/business");
}

export async function saveBusinessConfig(secretId: string, secretKey: string, endpoint?: string): Promise<{ configured: boolean; masked: string; message: string }> {
  return fetchJson("/api/settings/business", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ secret_id: secretId, secret_key: secretKey, endpoint: endpoint || "" }),
  });
}

export async function deleteBusinessConfig(): Promise<{ configured: boolean; message: string }> {
  return fetchJson("/api/settings/business", { method: "DELETE" });
}

export async function testBusinessConnection(): Promise<{ ok: boolean; message: string }> {
  return fetchJson("/api/settings/business/test", { method: "POST" });
}

export async function exportSettings(includeSecret = false): Promise<unknown> {
  let headers: Record<string, string> | undefined;
  if (includeSecret) {
    const tokenResponse = await fetchJson("/api/settings/export/authorize", { method: "POST" }) as { token: string };
    headers = { "X-Settings-Export-Token": tokenResponse.token };
  }
  return fetchJson(`/api/settings/export${includeSecret ? "?include_secret=true" : ""}`, { headers });
}

export async function importSettings(payload: unknown): Promise<{ imported: string[]; message: string }> {
  return fetchJson("/api/settings/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function clearLocalDataPackage(): Promise<{
  cleared: boolean;
  deleted: string[];
  count: number;
  dataDir: string;
  message: string;
}> {
  return fetchJson("/api/settings/local-data", { method: "DELETE" });
}

export async function getUserPreferences(): Promise<{ preferences: UserPreferences }> {
  return fetchJson("/api/settings/preferences");
}

export async function saveUserPreferences(preferences: UserPreferences): Promise<{ preferences: UserPreferences }> {
  return fetchJson("/api/settings/preferences", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(preferences),
  });
}

// === 百度搜索 API 配置 ===
export async function getBaiduConfig(): Promise<{ configured: boolean; masked: string }> {
  return fetchJson("/api/settings/baidu");
}

export async function saveBaiduConfig(apiKey: string): Promise<{ configured: boolean; masked: string; message: string }> {
  return fetchJson("/api/settings/baidu", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function deleteBaiduConfig(): Promise<{ configured: boolean; message: string }> {
  return fetchJson("/api/settings/baidu", { method: "DELETE" });
}

export async function testBaiduConnection(): Promise<{ ok: boolean; message: string }> {
  return fetchJson("/api/settings/baidu/test", { method: "POST" });
}

// === 聊天持久化 ===
export async function saveChatMessages(chatKey: string, messages: Array<{role: string; content: string}> | null): Promise<{saved: string}> {
  return fetchJson("/api/resumes/chat/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_key: chatKey, messages }),
  });
}

export async function loadChatMessages(chatKey?: string): Promise<{chats: Record<string, Array<{role: string; content: string}>>; active: Array<{role: string; content: string}>}> {
  const qs = chatKey ? `?chat_key=${encodeURIComponent(chatKey)}` : "";
  return fetchJson(`/api/resumes/chat/load${qs}`);
}
