import type { BossCaptureFilters, BossFilterOptions, BossLoginStatus, CompanyBlacklistItem, JobApplicationStatus, JobDecisionStatus, JobPosting, JobPoolQuality, ProviderConfig, ProviderPreset, RankingWeights, WorkflowRuntimeTask } from "./types";
import { formatApiError } from "./workflowInsights";

// ---------- 简历 ----------

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

export async function listBossCities(): Promise<{ cities: Array<{ name: string; code: string }>; total: number }> {
  return fetchJson("/api/jobs/cities");
}

export async function listBossFilterOptions(): Promise<BossFilterOptions> {
  return fetchJson("/api/jobs/capture/boss/filter-options");
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

export async function enrichJdDetails(payload: { job_ids?: string[]; max_jobs?: number } = {}): Promise<{ enriched: number; message: string }> {
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

export async function getRankingWeights(): Promise<{ weights: RankingWeights }> {
  return fetchJson("/api/scoring/weights");
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

export async function getGreetingDrafts(): Promise<{ greetings: Record<string, string> }> {
  return fetchJson("/api/greetings/drafts");
}

export async function saveGreetingDrafts(greetings: Record<string, string>): Promise<{ greetings: Record<string, string> }> {
  return fetchJson("/api/greetings/drafts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ greetings }),
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

export async function analyzeJD(payload: { title: string; company: string; jd_text: string }, chatHistory?: Array<{role: string; content: string}>): Promise<import("./types").JDAnalysis> {
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
