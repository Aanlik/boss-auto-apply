// ============================================================
//  boss 求职助手 — 类型定义 v2
//  核心变化：从单选改为多选批次流转
// ============================================================

// ---- 简历相关 ----

export type WorkExperience = {
  company: string;
  title: string;
  duration: string;
  description: string;
};

export type Education = {
  institution: string;
  degree: string;
  major: string;
  graduation: string;
};

export type Project = {
  name: string;
  description: string;
  technologies: string[];
};

export type ResumeProfile = {
  name: string;
  title: string;
  phone: string;
  email: string;
  gender: string;
  birth: string;
  location: string;
  summary: string;
  skills: string[];
  target_titles: string[];
  target_city: string;
  salary_expectation: string;
  work_experience: WorkExperience[];
  education: Education[];
  projects: Project[];
};

export type UploadedFile = {
  id: string;
  filename: string;
  path: string;
  size: number;
  uploaded_at: string;
};

// ---- 岗位相关 ----

export type JobPosting = {
  id: string;
  title: string;
  company: string;
  city: string;
  salary: string;
  salary_min: number;
  salary_max: number;
  jd_text: string;
  jd_detail_fetched_at?: string;
  jd_detail_url?: string;
  jd_analysis?: JDAnalysis;
  keywords: string[];
  structured_summary: string;
  source: string;
  source_url: string;
  fetched_at: string;
  dedupe_key: string;
  capture_batch_id?: string;
  capture_keyword?: string;
  capture_city?: string;
  capture_filters?: BossCaptureFilters;
  captured_at?: string;
  company_key?: string;
  greeted?: boolean;
  tags?: string[];
  lifecycle_status?: "active" | "suspected_expired" | "blacklisted";
  expires_at?: string;
  stale_reason?: string;
  application_status?: JobApplicationStatus;
  application_note?: string;
  application_updated_at?: string;
  decision_status?: JobDecisionStatus;
  status_history?: Array<{
    kind: "application" | "decision" | "lifecycle";
    status: string;
    previous?: string;
    note?: string;
    at: string;
  }>;
};

export type JobApplicationStatus = "pending" | "greeted" | "applied" | "interviewing" | "rejected" | "abandoned";
export type JobDecisionStatus = "undecided" | "recommended" | "watching" | "abandoned" | "risky";

export type GreetingCandidate = {
  jobId: string;
  title: string;
  company: string;
  city: string;
  salary: string;
  decisionStatus: JobDecisionStatus;
  applicationStatus: JobApplicationStatus;
  jdReady: boolean;
  riskLevel: "normal" | "high";
};

export type GreetingSkippedCandidate = GreetingCandidate & {
  reason: string;
};

export type GreetingCandidateResponse = {
  candidates: GreetingCandidate[];
  skipped: GreetingSkippedCandidate[];
  summary: {
    total: number;
    candidateCount: number;
    skippedCount: number;
  };
};

export type GreetingValidationResult = {
  jobId: string;
  ok: boolean;
  reasons: string[];
  length: number;
};

export type GreetingRecord = {
  jobId: string;
  company: string;
  title: string;
  status: "draft" | "failed" | "sent" | "skipped" | "blocked";
  message: string;
  validationOk: boolean;
  validationReasons: string[];
  updatedAt: string;
};

export type GreetingSendResponse = {
  summary: {
    total: number;
    sent: number;
    failed: number;
    skipped: number;
    dailyLimit: number;
    batchLimit: number;
    remainingBeforeSend: number;
  };
  records: GreetingRecord[];
  skipped: GreetingSkippedCandidate[];
  taskId: string;
};


export type GreetingFrequencyProfile = {
  key: "conservative" | "standard" | "fast" | string;
  label: string;
  batchLimit: number;
  intervalSeconds: number;
  dailyLimit: number;
};

export type GreetingAutoSendSettings = {
  auto_send_enabled: boolean;
  profile: string;
  gray_mode_enabled?: boolean;
  gray_first_success_required?: boolean;
  updatedAt?: string;
};

export type GreetingSafetySummary = {
  status: "ok" | "warn" | "blocked";
  settings: GreetingAutoSendSettings;
  summary: {
    sentToday: number;
    failedStreak: number;
    totalRecords: number;
    grayMode?: {
      enabled: boolean;
      requiresFirstSuccess: boolean;
      sentToday: number;
      latestStatus: string;
      batchAllowed: boolean;
      locked: boolean;
      message: string;
    };
  };
  checks: Array<{ key: string; status: "ok" | "warn" | "error"; message: string; action: string }>;
  recommendations: string[];
};

export type GreetingFinalConfirmation = {
  status: "ok" | "blocked";
  mode: string;
  summary: {
    jobCount: number;
    validMessages: number;
    sentToday: number;
    dailyLimit: number;
    remaining: number;
    batchLimit: number;
  };
  items: Array<{ jobId: string; company: string; title: string; messageLength: number; url: string; valid: boolean; reasons: string[] }>;
  links: string[];
  riskItems: string[];
  confirmText: string;
};

export type GreetingPreflight = {
  status: "ok" | "error";
  checks: Array<{ key: string; status: "ok" | "error"; message: string; action?: string }>;
  summary: { total: number; ok: number; error: number };
  candidates: GreetingCandidateResponse;
  validation: { results: GreetingValidationResult[]; summary: { total: number; ok: number; failed: number } };
};

export type GreetingProgress = {
  control: { state: "running" | "paused" | "stopped"; updatedAt: string; reason: string };
  task: WorkflowRuntimeTask | null;
  recent: WorkflowRuntimeTask[];
};

export type GreetingStats = {
  summary: {
    totalRecords: number;
    sent: number;
    failed: number;
    replies?: number;
    positiveReplies?: number;
    replyTrackingReady: boolean;
  };
  applicationStatuses: Record<string, number>;
  recent: Array<{ jobId: string; status: string; note: string; message?: string; updatedAt: string }>;
};

export type GreetingAcceptanceRecord = {
  id: string;
  jobId: string;
  result: "passed" | "failed" | "partial" | string;
  operator: string;
  note: string;
  checks: Array<{ key: string; status: string; note?: string }>;
  createdAt: string;
};

export type GreetingReplyRecord = {
  id: string;
  jobId: string;
  replyType: "positive" | "neutral" | "negative" | string;
  content: string;
  nextAction: string;
  createdAt: string;
};

export type GreetingTemplateEffectiveness = {
  summary: { sent: number; replies: number; positiveReplies: number; replyRate: number; positiveRate: number };
  byJobType: Array<{ jobType: string; sent: number; replies: number; positiveReplies: number; replyRate: number; positiveRate: number; avgLength: number }>;
  recommendations: string[];
};

export type GreetingSelectorHealth = {
  jobId: string;
  title: string;
  company: string;
  status: "ok" | "error";
  checks: Array<{ key: string; status: "ok" | "warn" | "error"; message: string }>;
};

export type GreetingAcceptancePlan = {
  jobId: string;
  title: string;
  company: string;
  sourceUrl: string;
  steps: Array<{ key: string; label: string; description: string }>;
};

export type GreetingFollowups = {
  summary: { pendingFollowups: number };
  items: Array<{
    jobId: string;
    title: string;
    company: string;
    sentAt: string;
    windowHours: number;
    status: "pending_followup";
    suggestion: string;
  }>;
};

export type BossLoginStatus = {
  logged_in: boolean;
  reason?: string;
  message: string;
  action?: string;
};

export type BossCaptureFilters = {
  scale?: string;
  stage?: string;
  salary?: string;
  experience?: string;
  degree?: string;
  industry?: string;
};

export type BossFilterOption = {
  label: string;
  value: string;
};

export type BossFilterOptions = Record<keyof BossCaptureFilters, BossFilterOption[]>;

export type JobSearchPreset = {
  id: string;
  name: string;
  keyword: string;
  city: string;
  max_pages: number;
  filters: BossCaptureFilters;
  job_filters?: Record<string, string>;
  createdAt: string;
  updatedAt: string;
};

export type CompanyBlacklistItem = {
  name: string;
  createdAt: string;
};

export type JobDuplicateGroup = {
  key: string;
  jobIds: string[];
  title: string;
  company: string;
  city: string;
  count: number;
  withJd: number;
};

export type JobPoolQuality = {
  summary: {
    total: number;
    with_jd: number;
    missing_jd: number;
    suspected_expired: number;
    blacklisted: number;
    duplicate_groups: number;
    duplicate_jobs: number;
    batch_count?: number;
    application_statuses?: Record<JobApplicationStatus, number>;
  };
  duplicateGroups: JobDuplicateGroup[];
  batches?: Array<{
    id: string;
    keyword: string;
    city: string;
    filters: BossCaptureFilters;
    capturedAt: string;
    total: number;
    with_jd: number;
    missing_jd: number;
    blacklisted: number;
    suspected_expired: number;
    jd_completion_rate?: number;
    stale_rate?: number;
    risk_rate?: number;
  }>;
};

export type JobComparison = {
  jobs: JobPosting[];
  comparison: {
    salary: Array<{ id: string; value: string; min: number; max: number }>;
    jd_quality: Array<{ id: string; value: number }>;
    lifecycle: Array<{ id: string; value: string }>;
    application: Array<{ id: string; value: string }>;
    decision: Array<{ id: string; value: string }>;
  };
};

export type ApplicationFunnel = {
  summary: {
    total: number;
    contacted: number;
    interviewing: number;
    rejected: number;
    recommended: number;
    contactRate: number;
    interviewRate: number;
    rejectionRate: number;
  };
  statusCounts: Record<JobApplicationStatus, number>;
  batches: Array<{
    id: string;
    total: number;
    contacted: number;
    interviewing: number;
    recommended: number;
    risky: number;
    contactRate: number;
    interviewRate: number;
    recommendRate: number;
  }>;
  recommendations: string[];
};

export type ApplicationBoard = {
  summary: { total: number };
  columns: Record<JobApplicationStatus | string, {
    key: string;
    label: string;
    count: number;
    jobs: Array<{
      id: string;
      title: string;
      company: string;
      city: string;
      salary: string;
      decisionStatus: JobDecisionStatus | string;
      updatedAt: string;
      note: string;
    }>;
  }>;
  generatedAt: string;
};

export type UserPreferences = {
  stability: number;
  salary: number;
  growth: number;
  match: number;
  avoid_industries: string[];
  preferred_cities: string[];
  updatedAt?: string;
};

export type HealthCheckStatus = "ok" | "warn" | "error";

export type HealthCheckItem = {
  key: string;
  label: string;
  status: HealthCheckStatus;
  message: string;
  action?: string;
  repairAction?: {
    type: "navigate" | "command" | "manual" | "export_redacted_backup" | "refresh_endpoint" | string;
    page?: string;
    endpoint?: string;
    command?: string;
    label: string;
    description: string;
  };
};

export type WorkflowHealthCheck = {
  status: HealthCheckStatus;
  checks: HealthCheckItem[];
};

export type HelpCenter = {
  kind: "help_center";
  version: number;
  quickStart: Array<{ label: string; page: string }>;
  modules: Array<{
    key: string;
    label: string;
    purpose: string;
    whenToUse: string[];
    nextStep: string;
    steps: string[];
    goodSignals: string[];
    commonFailures: string[];
    safetyNotes: string[];
    repairActions: Array<{ label: string; page: string; type: string; endpoint?: string }>;
  }>;
  principles: string[];
  faq: Array<{ question: string; answer: string; page: string }>;
  glossary: Array<{ term: string; meaning: string }>;
};

export type DashboardSummary = {
  jobs: {
    total: number;
    missingJd: number;
    withJd: number;
    suspectedExpired: number;
    blacklisted: number;
  };
  diligence: {
    completedCompanies: number;
    pendingCompanies: number;
  };
  ranking: {
    total: number;
    recommended: number;
  };
  decisions: {
    recommended: number;
    watching: number;
    risky: number;
    abandoned: number;
  };
  readiness: {
    stage: "setup" | "complete_jd" | "diligence" | "ranking" | "decision" | "ready";
    qualityScore: number;
    nextAction: {
      label: string;
      page: "jobs" | "diligence" | "ranking" | "greeting";
      reason: string;
    };
    blockers: Array<{
      key: string;
      label: string;
      count: number;
      severity: "high" | "medium" | "low";
    }>;
  };
  generatedAt: string;
};

export type OnboardingGuide = {
  steps: Array<{ key: string; label: string; page: string; status: "done" | "todo"; reason: string; action?: string }>;
  nextStep: { key: string; label: string; page: string; status: "done" | "todo"; reason: string; action?: string };
  progress?: { done: number; total: number; percent: number };
  primaryAction?: string;
  primaryPage?: string;
  generatedAt: string;
};

export type OnboardingWizard = OnboardingGuide & {
  kind: "onboarding_wizard";
  title: string;
  primaryAction: string;
  primaryPage: string;
  steps: Array<OnboardingGuide["steps"][number] & { index: number; stateLabel: string; blockers: string[]; primary: boolean }>;
  tips: string[];
};

export type JobsImportWizard = {
  kind: "jobs_import_wizard";
  summary: { total: number; creates: number; duplicates: number; invalid: number };
  creates: JobPosting[];
  duplicates: Array<{ index: number; jobId: string; company: string; title: string; city: string }>;
  invalid: Array<{ index: number; reason: string }>;
  message: string;
};

export type ReviewCenter = {
  summary: ApplicationFunnel["summary"];
  statusCounts: Record<string, number>;
  batches: Array<Record<string, unknown>>;
  riskCompanies: Array<{ id: string; company: string; title: string }>;
  missingJdJobs: Array<{ id: string; company: string; title: string }>;
  recommendations: string[];
  generatedAt: string;
};

export type ApplicationStrategy = {
  strategy: "priority_apply" | "watch" | "hold" | "needs_more_info";
  label: string;
  confidence: number;
  reasons: string[];
  nextActions: string[];
  resumeFocus: string[];
};

export type JdQualityInsight = {
  qualityScore: number;
  noiseLevel: "low" | "medium" | "high";
  authenticity: "weak" | "medium" | "strong";
  signals: string[];
  cleaningAdvice: string[];
  missingSections: string[];
};

export type ResumeRewriteAdvice = {
  keywordEvidence: string[];
  missingKeywords: string[];
  rewriteFocus: string[];
  bulletSuggestions: string[];
  companyContext: string;
};

export type InterviewPrep = {
  companyBrief: string;
  questions: string[];
  answerAngles: string[];
  reverseQuestions: string[];
};

export type FollowupReminder = {
  jobId: string;
  title: string;
  company: string;
  status: string;
  priority: "high" | "normal";
  reason: string;
  suggestedAction: string;
};

export type RiskExplanation = {
  riskLevel: "low" | "medium" | "high" | string;
  plainLanguage: string;
  riskItems: string[];
  impact: string[];
  questionsToAsk: string[];
};

export type ResumeVersion = {
  label: string;
  profile: Partial<ResumeProfile>;
  createdAt: string;
};

export type PdfTemplateRecommendation = {
  template: "modern" | "classic" | "ats";
  reason: string;
  options: Array<"modern" | "classic" | "ats">;
};

export type WorkflowRuntimeTaskStatus = "queued" | "running" | "completed" | "partial_failed" | "failed";

export type WorkflowRuntimeTask = {
  id: string;
  type: string;
  title: string;
  status: WorkflowRuntimeTaskStatus;
  done: number;
  total: number;
  message: string;
  errorCode: string;
  action: string;
  retryable: boolean;
  payload?: Record<string, unknown>;
  sourceTaskId?: string;
  createdAt: string;
  updatedAt: string;
};

export type WorkflowRecoveryGroup = {
  category: string;
  label: string;
  count: number;
  retryable: number;
  action: string;
  taskIds: string[];
};

export type WorkflowCenter = {
  summary: {
    total: number;
    running: number;
    failed: number;
    retryable: number;
    completed: number;
  };
  running: WorkflowRuntimeTask[];
  recovery: WorkflowRuntimeTask[];
  recoveryGroups: WorkflowRecoveryGroup[];
  recoveryActions?: Array<{
    category: string;
    label: string;
    page: string;
    action: string;
    count: number;
    retryable: number;
    taskIds: string[];
    primary: boolean;
  }>;
  recent: WorkflowRuntimeTask[];
};

export type WeeklyReport = {
  windowDays: number;
  range: { from: string; to: string };
  summary: {
    capturedJobs: number;
    jdReady: number;
    diligenceDone: number;
    greetingsSent: number;
    contacted: number;
    interviewing: number;
    rejected: number;
    failedTasks: number;
  };
  conversion: {
    jdReadyRate: number;
    interviewRate: number;
    rejectionRate: number;
  };
  failureGroups: WorkflowRecoveryGroup[];
  recentEvents: Array<{ jobId: string; title: string; company: string; status: string; kind: string; at: string }>;
  recommendations: string[];
  generatedAt: string;
};

export type DashboardTrendReport = {
  windowDays: number;
  series: Array<{
    date: string;
    capturedJobs: number;
    jdReady: number;
    diligenceDone: number;
    greetingsSent: number;
    replies: number;
    positiveReplies: number;
    interviewing: number;
  }>;
  summary: {
    capturedJobs: number;
    jdReady: number;
    diligenceDone: number;
    greetingsSent: number;
    replies: number;
    positiveReplies: number;
    interviewing: number;
    jdReadyRate: number;
    replyRate: number;
    positiveReplyRate: number;
    interviewRate: number;
  };
  generatedAt: string;
};

export type DataQualityCenter = {
  summary: {
    totalJobs: number;
    issues: number;
    errors: number;
    warnings: number;
    score: number;
  };
  checks: Array<{
    key: string;
    label: string;
    count: number;
    severity: "info" | "warn" | "error";
    page: string;
    action: string;
    reason: string;
  }>;
  generatedAt: string;
};

export type DataQualityRepairResult = {
  updated: number;
  actions: string[];
  details: Array<{ jobId: string; company: string; title: string; tags: string[] }>;
  quality: DataQualityCenter;
};

export type DeepReportSections = {
  summary?: string;
  strategy?: string;
  match?: string;
  risk?: string;
  interview?: string;
  actions?: string;
};

export type AssistantPromptVersions = {
  summary: { total: number; deepReport: number };
  versions: Array<{
    id: string;
    jobId: string;
    company: string;
    title: string;
    kind: string;
    promptVersion: string;
    promptPreview: string;
    payloadSummary: {
      hasResume: boolean;
      hasDiligence: boolean;
      preferenceSignals: number;
    };
    feedbackGuidance: {
      summary?: { total?: number; useful?: number; notUseful?: number };
      recentNotes?: string[];
    };
    createdAt: string;
  }>;
};

export type AssistantPromptVersionCompare = {
  summary: { jobId: string; kind: string; totalVersions: number; comparable: boolean };
  versions: AssistantPromptVersions["versions"];
  differences: {
    samePromptVersion: boolean;
    preferenceSignalDelta: number;
    latestFeedbackNotes: string[];
    previousFeedbackNotes: string[];
  };
};

export type AiFeedbackDomain =
  | "ranking"
  | "diligence"
  | "jd_quality"
  | "greeting"
  | "deep_report"
  | "resume_pdf"
  | "report_pdf";

export type AiFeedbackRecord = {
  id: string;
  domain: AiFeedbackDomain;
  targetId: string;
  useful: boolean;
  note: string;
  context: Record<string, unknown>;
  updatedAt: string;
};

export type AiFeedbackSummary = {
  summary: { total: number; useful: number; notUseful: number };
  byDomain: Record<AiFeedbackDomain | string, { total: number; useful: number; notUseful: number }>;
  recent: AiFeedbackRecord[];
  generatedAt: string;
};

export type AiPreferenceProfile = {
  summary: { total: number; useful: number; notUseful: number };
  domains: Record<string, { total: number; useful: number; notUseful: number }>;
  weightHints: { company: number; match: number };
  dominantPreference: "balanced" | "company_risk" | "resume_match" | string;
  jobTypes: Record<string, number>;
  recentNeeds: string[];
  generatedAt: string;
};

export type ApplicationTimeline = {
  summary: Record<JobApplicationStatus, number>;
  events: Array<{
    jobId: string;
    title: string;
    company: string;
    city: string;
    status: JobApplicationStatus | string;
    previous: string;
    note: string;
    at: string;
  }>;
  total: number;
};

// ---- 尽调相关 ----

export type BusinessInfo = {
  companyName: string;
  sourceCompanyName?: string;
  companyKey?: string;
  legalRepresentative: string;
  registrationCapital: string;
  paidInCapital: string;
  establishedDate: string;
  businessStatus: string;
  unifiedCreditCode: string;
  registrationNumber: string;
  taxpayerId: string;
  businessScope: string;
  industry: string;
  subIndustry?: string;
  registeredIndustry?: string;
  registeredSubIndustry?: string;
  address: string;
  companyType?: string;
  registrationAuthority?: string;
  businessDateFrom?: string;
  businessDateTo?: string;
  issueDate?: string;
  orgCode?: string;
  isOnStock?: string;
  stockNumber?: string;
  stockType?: string;
  contactPhone?: string;
  contactEmail?: string;
  websites?: string[];
  shareholders: string[];
  executives: string[];
  branchCount: number;
  abnormalInfo: string[];
  penalties: string[];
  changeCount?: number;
  changes?: string[];
  dishonestCount?: number;
  dishonestItems?: string[];
  enforcedCount?: number;
  enforcedItems?: string[];
  pledgeCount?: number;
  pledges?: string[];
  movablePledgeCount?: number;
  movablePledges?: string[];
  originalNames?: string[];
  taxCreditLevels?: string[];
  permissions?: string[];
  spotChecks?: string[];
  permissionCount?: number;
  spotCheckCount?: number;
  apiEntries?: Array<{ path: string; label: string; value: string }>;
  annualReport: string;
  error?: string;
};

export type DiligenceReport = {
  companyName: string;
  sourceCompanyName?: string;
  companyKey?: string;
  companyScore: number;
  riskLevel: "low" | "medium" | "high";
  businessInfo?: BusinessInfo;
  basicInfo: { scale: string; funding: string; founded: string; business: string };
  sentiment: { positive: string[]; negative: string[]; evidenceLinks: string[] };
  recruitment: { activePositions: number; salaryCompetitiveness: string; jdQuality: string };
  industryOutlook: { industry?: string; trend: string; policy: string; marketSpace: string; growthRate?: string; advantages?: string[]; disadvantages?: string[]; risks: string[] };
  oneLiner: string;
  userNotes: string;
  completedAt: string;
};

// ---- 排序相关 ----

export type RankingResult = {
  jobId: string;
  jobTitle: string;
  company: string;
  companyKey?: string;
  salary: string;
  companyScore: number;
  matchScore: number;
  compositeScore: number;
  recommendation: "strong" | "recommend" | "consider" | "not_recommend";
  reason: string;
  matchHighlights: string[];
  matchGaps: string[];
  weights?: RankingWeights;
  explanation?: {
    matchReasons: string[];
    resumeGaps: string[];
    companyReason: string;
    riskSignals: string[];
    preferenceSignals?: string[];
    jdSignals?: {
      coreRequirements?: string[];
      hardRequirements?: string[];
    };
    scoreBreakdown?: {
      companyScore: number;
      matchScore: number;
      compositeScore: number;
    };
    nextStep: string;
    summary: string;
  };
};

export type RankingWeights = {
  company_weight: number;
  match_weight: number;
  feedbackAdjusted?: boolean;
  feedbackSignals?: string[];
};

export type RankingWeightTemplate = {
  name: string;
  description: string;
  weights: RankingWeights;
};

// ---- 打招呼 / 简历修订 ----

// ---- 全局工作流状态 ----

export type WorkflowState = {
  /** 多选岗位 ID 集合（用于批次流转） */
  selectedJobIds: string[];
  /** 简历解析结果 */
  resumeProfile: ResumeProfile | null;
  /** 已上传的简历文件列表 */
  uploadedFiles: UploadedFile[];
  /** 尽调结果（key = company name, 同一公司多岗位合并） */
  diligenceReports: Record<string, DiligenceReport>;
  /** 排序结果 */
  rankingResults: RankingResult[];
  /** JD AI 分析结果（key = jobId） — 切换页面不丢失 */
  jdAnalyses: Record<string, JDAnalysis>;
  /** AI 简历优化结果（key = jobId） — 切换页面不丢失 */
  optimizations: Record<string, ResumeOptimizationResult>;
  /** 打招呼文本（key = jobId） — 切换页面不丢失 */
  greetingTexts: Record<string, string>;
  /** 聊天消息（key = jobId） — 切换页面不丢失 */
  chatMessages: Record<string, Array<{ role: string; content: string }>>;
};

// ---- AI 评估 / 优化 ----

export type ResumeEvaluation = {
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
  missing_sections: string[];
  format_issues: string[];
  summary_text: string;
};

export type JDAnalysis = {
  must_have_skills: string[];
  nice_to_have_skills: string[];
  experience_requirements: string[];
  soft_skills: string[];
  domain_knowledge: string[];
  education_requirements: string;
  summary_text: string;
};

export type OptimizedExperience = {
  company: string;
  title: string;
  duration: string;
  bullets: string[];
};

export type OptimizedProject = {
  name: string;
  description: string;
  technologies: string[];
};

export type ResumeOptimizationResult = {
  summary: string;
  tailored_summary: string;
  skills_display: string[];
  optimized_bullets: string[];
  work_experience: OptimizedExperience[];
  projects: OptimizedProject[];
  matched_skills: string[];
  missing_skills: string[];
  section_advice: string[];
  gap_strategies: string[];
};

// ---- 供应商配置 ----

export type ProviderPreset = {
  name: string;
  base_url: string;
  models: string[];
};

export type ProviderConfig = {
  provider: string;
  configured: boolean;
  masked: string;
  base_url: string;
  model: string;
};
