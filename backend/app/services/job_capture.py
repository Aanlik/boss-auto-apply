"""
岗位捕获服务。
提供：示例数据、手动录入、Boss 直聘真实抓取。
"""
from datetime import datetime, timezone
import hashlib
from app.models.job import JobRecord, JobSource


SAMPLE_JOBS: list[dict] = [
    {
        "id": "boss-001",
        "title": "Python 后端工程师",
        "company": "A 科技有限公司",
        "city": "深圳",
        "salary": "20-30K",
        "jd_text": (
            "负责 Python、FastAPI、SQLAlchemy 和 Redis 的后端开发。"
            "参与支付系统与订单系统建设，要求有 3 年以上后端经验，"
            "熟悉分布式系统设计，有高并发项目经验者优先。"
        ),
    },
    {
        "id": "boss-002",
        "title": "Java 后端工程师",
        "company": "B 信息技术有限公司",
        "city": "北京",
        "salary": "15-25K",
        "jd_text": (
            "负责 Java、Spring Boot、MySQL 和 Docker 的服务开发。"
            "关注接口稳定性与性能优化，熟悉微服务架构。"
        ),
    },
    {
        "id": "boss-003",
        "title": "前端工程师",
        "company": "C 互联网公司",
        "city": "深圳",
        "salary": "18-28K",
        "jd_text": (
            "负责 React、TypeScript、组件库和页面性能优化。"
            "支持招聘工作台业务，要求熟悉 Node.js 和 Webpack。"
        ),
    },
    {
        "id": "boss-004",
        "title": "数据工程师",
        "company": "D 数据科技有限公司",
        "city": "深圳",
        "salary": "25-35K",
        "jd_text": (
            "负责大数据平台建设，使用 Spark、Flink、Hadoop 处理海量数据。"
            "要求熟悉 SQL、Python，有数据仓库建模经验。"
        ),
    },
    {
        "id": "boss-005",
        "title": "全栈工程师",
        "company": "E 创业公司",
        "city": "杭州",
        "salary": "20-30K",
        "jd_text": (
            "负责前后端全栈开发，前端 React + TypeScript，后端 Python FastAPI。"
            "要求有独立项目开发能力，熟悉 Docker 部署。"
        ),
    },
]


# ---------- 示例数据 ----------

def capture_sample_jobs() -> list[JobSource]:
    """从示例数据捕获岗位（模拟 Boss 抓取）。"""
    now = datetime.now(timezone.utc).isoformat()
    sources: list[JobSource] = []
    for job in SAMPLE_JOBS:
        dedupe_key = _make_dedupe_key(job.get("company", ""), job.get("title", ""), job.get("city", ""))
        sources.append(JobSource(
            source_type="captured",
            source_id=job.get("id", ""),
            raw_payload=job,
            fetched_at=now,
            dedupe_key=dedupe_key,
        ))
    return sources


# ---------- Boss 真实抓取 ----------

def capture_from_boss(
    keyword: str = "Python",
    city: str = "深圳",
    max_pages: int = 3,
    headless: bool = True,
) -> list[JobSource]:
    """从 Boss 直聘真实抓取岗位。scrape_jobs_sync 返回 dict 列表。"""
    from app.services.boss_scraper import scrape_jobs_sync

    jobs = scrape_jobs_sync(keyword=keyword, city=city, max_pages=max_pages, headless=headless)
    now = datetime.now(timezone.utc).isoformat()
    sources: list[JobSource] = []

    for i, job in enumerate(jobs):
        src_url = job.get("source_url", "") if isinstance(job, dict) else getattr(job, "source_url", "")
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        city_val = job.get("city", "") if isinstance(job, dict) else getattr(job, "city", "")
        salary = job.get("salary", "") if isinstance(job, dict) else getattr(job, "salary", "")
        jd_text = job.get("jd_text", "") if isinstance(job, dict) else getattr(job, "jd_text", "")
        tags = job.get("keywords", []) if isinstance(job, dict) else getattr(job, "tags", [])

        source_id = hashlib.md5(src_url.encode()).hexdigest()[:12] if src_url else f"boss-captured-{i}"
        dedupe_key = _make_dedupe_key(company, title, city_val)

        sources.append(JobSource(
            source_type="captured",
            source_id=source_id,
            raw_payload={
                "id": f"boss-{source_id}",
                "title": title,
                "company": company,
                "city": city_val,
                "salary": salary,
                "jd_text": jd_text,
                "source_url": src_url,
                "tags": tags,
            },
            fetched_at=now,
            dedupe_key=dedupe_key,
        ))

    return sources


# ---------- 手动录入 ----------

def jobs_from_source(source: JobSource) -> JobRecord:
    """从 JobSource 构造 JobRecord。"""
    raw = source.raw_payload
    return JobRecord(
        id=raw.get("id", source.source_id),
        title=raw.get("title", ""),
        company=raw.get("company", ""),
        city=raw.get("city", ""),
        salary=raw.get("salary", ""),
        jd_text=raw.get("jd_text", ""),
        source=source.source_type,
        source_url=raw.get("source_url", ""),
        fetched_at=source.fetched_at,
        dedupe_key=source.dedupe_key,
    )


def jobs_from_manual_payload(payload: dict) -> JobRecord:
    """从手动录入构造 JobRecord。"""
    now = datetime.now(timezone.utc).isoformat()
    company = payload.get("company", "")
    title = payload.get("title", "")
    city = payload.get("city", "")
    dedupe_key = _make_dedupe_key(company, title, city)
    return JobRecord(
        id=payload.get("id") or f"manual-{hashlib.md5((company+title+city).encode()).hexdigest()[:8]}",
        title=title,
        company=company,
        city=city,
        salary=payload.get("salary", ""),
        jd_text=payload.get("jd_text", ""),
        source="manual",
        fetched_at=now,
        dedupe_key=dedupe_key,
    )


def _make_dedupe_key(company: str, title: str, city: str) -> str:
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{city.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]
