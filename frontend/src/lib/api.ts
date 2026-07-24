import type { JobPosting, ResumeOptimization, ProviderConfig, ProviderPreset } from "./types";

export async function getHealth() {
  return fetchJson("/health");
}

// ---------- 简历 ----------

export async function parseResumeFile(file: File): Promise<{
  profile: import("./types").ResumeProfile;
  raw_text: string;
  file_id: string;
}> {
  const form = new FormData();
  form.append("file", file);
  return fetchJson("/api/resumes/parse", { method: "POST", body: form });
}

export async function optimizeResume(
  profile: unknown,
  targetJob: unknown
): Promise<ResumeOptimization> {
  return fetchJson("/api/resumes/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile, target_job: targetJob }),
  });
}

// ---------- 岗位 ----------

export async function listJobPool(): Promise<{ jobs: JobPosting[]; total: number }> {
  return fetchJson("/api/jobs/pool");
}

export async function captureJobs(): Promise<{ captured: number; total: number }> {
  return fetchJson("/api/jobs/capture", { method: "POST" });
}

export async function captureBossJobs(
  payload: { keyword?: string; city?: string; max_pages?: number } = {}
): Promise<{ captured: number; total: number }> {
  return fetchJson("/api/jobs/capture/boss", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function bossLogin(): Promise<{ status: string; message: string }> {
  return fetchJson("/api/jobs/capture/boss/login", { method: "POST" });
}

export async function addManualJob(
  payload: Partial<JobPosting>
): Promise<JobPosting> {
  return fetchJson("/api/jobs/manual", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function filterJobPool(filters: {
  keywords?: string[];
  city?: string;
  min_salary?: number;
}): Promise<{ jobs: JobPosting[]; total: number }> {
  return fetchJson("/api/jobs/filter", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filters }),
  });
}

export async function filterJobs(jobs: unknown[], filters: unknown) {
  return fetchJson("/api/jobs/filter-legacy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jobs, filters }),
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

export async function rankJobs(jobs: unknown[], resume: unknown, diligences: unknown) {
  return fetchJson("/api/scoring/rank", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jobs, resume, diligences }),
  });
}

export async function draftMessage(payload: unknown) {
  return fetchJson("/api/messages/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function reviseMessage(payload: unknown) {
  return fetchJson("/api/messages/revise", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function buildInbox(payload: unknown) {
  return fetchJson("/api/send-inbox/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function confirmSend(payload: unknown) {
  return fetchJson("/api/send-inbox/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ---------- 内部 ----------

async function fetchJson(input: RequestInfo | URL, init?: RequestInit) {
  const response = await fetch(input, init);
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const errBody = await response.json();
      if (errBody.detail) detail = errBody.detail;
    } catch {}
    throw new Error(detail);
  }
  return response.json();
}

export async function deleteJob(jobId: string): Promise<{ deleted: string; total: number }> {
  return fetchJson(`/api/jobs/${jobId}`, { method: "DELETE" });
}

export async function clearAllJobs(): Promise<{ deleted: number; total: number }> {
  return fetchJson("/api/jobs", { method: "DELETE" });
}

export async function enrichJobDetails(maxJobs = 10): Promise<{ enriched: number; total: number }> {
  return fetchJson("/api/jobs/enrich", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ max_jobs: maxJobs }),
  });
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
}> {
  return fetchJson("/api/resumes/active");
}

export async function listUploadedFiles(): Promise<{ files: import("./types").UploadedFile[] }> {
  return fetchJson("/api/resumes/files");
}

export async function deleteUploadedFile(fileId: string): Promise<{ deleted: string }> {
  return fetchJson(`/api/resumes/files/${fileId}`, { method: "DELETE" });
}

export async function updateProfile(profile: unknown): Promise<{ updated: boolean }> {
  return fetchJson("/api/resumes/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile }),
  });
}

export async function getRawText(): Promise<{ raw_text: string }> {
  return fetchJson("/api/resumes/raw-text");
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
}): Promise<void> {
  const response = await fetch("/api/resumes/export-pdf", {
    method: "POST",
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
  // 从 Content-Disposition 提取文件名
  const disposition = response.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?(.+?)"?$/);
  const filename = match?.[1] || "简历.pdf";

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
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
