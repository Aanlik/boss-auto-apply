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

export type ResumeOptimization = {
  summary: string;
  bullets: string[];
  matched_skills: string[];
  missing_skills: string[];
};

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
};

export type ResumeSnapshot = {
  fileName: string;
  title: string;
  summary: string;
};

export type DiligenceSnapshot = {
  companyName: string;
  summary: string;
};

export type MessageDraftSnapshot = {
  jobId: string;
  draftText: string;
};

export type WorkflowState = {
  selectedJob: JobPosting | null;
  resumeSnapshot: ResumeSnapshot | null;
  diligenceSnapshot: DiligenceSnapshot | null;
  messageDraftSnapshot: MessageDraftSnapshot | null;
};
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

