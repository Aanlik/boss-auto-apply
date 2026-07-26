from pydantic import BaseModel, Field


class WorkExperience(BaseModel):
    company: str = ""
    title: str = ""
    duration: str = ""
    description: str = ""


class Education(BaseModel):
    institution: str = ""
    degree: str = ""
    major: str = ""
    graduation: str = ""


class Project(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class ResumeProfile(BaseModel):
    # 基本信息
    name: str = ""
    title: str = ""
    phone: str = ""
    email: str = ""
    gender: str = ""
    birth: str = ""
    location: str = ""
    # 简历内容
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    target_titles: list[str] = Field(default_factory=list)
    target_city: str = ""
    salary_expectation: str = ""
    work_experience: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)


class ResumeEvaluation(BaseModel):
    """AI 对简历本身的评估"""
    overall_score: int = Field(default=0, ge=0, le=100)  # 0-100
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    format_issues: list[str] = Field(default_factory=list)
    summary_text: str = ""


class JDAnalysis(BaseModel):
    """AI 对目标岗位 JD 的拆解"""
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    experience_requirements: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    domain_knowledge: list[str] = Field(default_factory=list)
    education_requirements: str = ""
    summary_text: str = ""


class OptimizedExperience(BaseModel):
    """优化后的单条工作经历"""
    company: str = ""
    title: str = ""
    duration: str = ""
    bullets: list[str] = Field(default_factory=list)  # 针对 JD 重写的 bullet points


class OptimizedProject(BaseModel):
    """优化后的单条项目经历"""
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class ResumeOptimizationResult(BaseModel):
    """AI 驱动的简历优化结果 — 可直接用于生成完整简历"""
    summary: str = ""                                         # 整体优化策略概述
    tailored_summary: str = ""                                # 针对 JD 的个人总结
    skills_display: list[str] = Field(default_factory=list)   # 重排后的技能列表（匹配的在前）
    optimized_bullets: list[str] = Field(default_factory=list)# 优化后的工作经历 bullet（兼容旧版）
    work_experience: list[OptimizedExperience] = Field(default_factory=list)  # 完整优化后工作经历
    projects: list[OptimizedProject] = Field(default_factory=list)            # 优化后项目经历
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    section_advice: list[str] = Field(default_factory=list)
    gap_strategies: list[str] = Field(default_factory=list)
