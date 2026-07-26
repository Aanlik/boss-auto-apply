from pydantic import BaseModel, Field


class JobRecord(BaseModel):
    id: str = ""
    title: str = ""
    company: str = ""
    city: str = ""
    salary: str = ""
    salary_min: int = 0          # 薪资下限，自动解析
    salary_max: int = 0          # 薪资上限，自动解析
    jd_text: str = ""
    keywords: list[str] = Field(default_factory=list)
    structured_summary: str = ""  # AI 或规则生成的 JD 摘要
    source: str = "manual"       # manual / captured / imported
    source_url: str = ""
    fetched_at: str = ""         # ISO 时间戳
    dedupe_key: str = ""         # 去重键：company+title+city 的小写哈希
    greeted: bool = False        # 是否已打招呼
    tags: list[str] = Field(default_factory=list)  # 自定义标签
    lifecycle_status: str = "active"  # active / suspected_expired / blacklisted
    expires_at: str = ""              # 疑似过期时间点
    stale_reason: str = ""            # 疑似过期原因
    application_status: str = "pending"  # pending / greeted / applied / interviewing / rejected / abandoned
    application_note: str = ""
    application_updated_at: str = ""
    decision_status: str = "undecided"  # undecided / recommended / watching / abandoned / risky


class JobSource(BaseModel):
    source_type: str = "manual"  # manual / captured / imported
    source_id: str = ""          # 来源内的唯一标识
    raw_payload: dict = Field(default_factory=dict)
    fetched_at: str = ""         # ISO 时间戳
    normalized_job_id: str = ""  # 归一化后的岗位 id
    dedupe_key: str = ""         # 去重键


class JobFilter(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    city: str = ""
    min_salary: int = 0
