// ============================================================
//  BOSS 直聘 AI 求职工作台 — 类型定义 v2
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
  keywords: string[];
  structured_summary: string;
  source: string;
  source_url: string;
  fetched_at: string;
  dedupe_key: string;
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
};

export type JobApplicationStatus = "pending" | "greeted" | "applied" | "interviewing" | "rejected" | "abandoned";
export type JobDecisionStatus = "undecided" | "recommended" | "watching" | "abandoned" | "risky";

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
    application_statuses?: Record<JobApplicationStatus, number>;
  };
  duplicateGroups: JobDuplicateGroup[];
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
  createdAt: string;
  updatedAt: string;
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
};

export type RankingWeights = {
  company_weight: number;
  match_weight: number;
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
