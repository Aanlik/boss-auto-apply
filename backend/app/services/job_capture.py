"""岗位捕获服务：手动录入与 BOSS 直聘真实抓取。"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.models.job import JobRecord, JobSource


def capture_from_boss(
    keyword: str = "Python",
    city: str = "深圳",
    max_pages: int = 3,
    headless: bool = True,
    filters: dict[str, str] | None = None,
) -> list[JobSource]:
    """从 BOSS 直聘真实抓取岗位。scrape_jobs_sync 返回 dict 列表。"""
    from app.services.boss_scraper import scrape_jobs_sync

    jobs = scrape_jobs_sync(keyword=keyword, city=city, max_pages=max_pages, headless=headless, filters=filters)
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

        source_id = hashlib.md5((src_url or f"no-url-{i}-{company}").encode()).hexdigest()[:12]
        # BOSS 重抓过滤按公司 + 岗位名判断；城市变化不应产生重复岗位。
        dedupe_key = _make_dedupe_key(company, title, "")

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
    captured_keywords = raw.get("keywords")
    if captured_keywords is None:
        captured_keywords = raw.get("tags", [])
    return JobRecord(
        id=raw.get("id", source.source_id),
        title=raw.get("title", ""),
        company=raw.get("company", ""),
        city=raw.get("city", ""),
        salary=raw.get("salary", ""),
        jd_text=raw.get("jd_text", ""),
        keywords=list(captured_keywords or []),
        source=source.source_type,
        source_url=raw.get("source_url", ""),
        capture_company_name=raw.get("company", ""),
        capture_dedupe_key=source.dedupe_key,
        fetched_at=source.fetched_at,
        dedupe_key=_make_dedupe_key(raw.get("company", ""), raw.get("title", ""), raw.get("city", "")),
    )


def jobs_from_manual_payload(payload: dict) -> JobRecord:
    """从手动录入构造 JobRecord。"""
    now = datetime.now(timezone.utc).isoformat()
    company = payload.get("company", "")
    title = payload.get("title", "")
    city = payload.get("city", "")
    dedupe_key = _make_dedupe_key(company, title, city)
    capture_dedupe_key = _make_dedupe_key(company, title, "")
    return JobRecord(
        id=payload.get("id") or f"manual-{hashlib.md5((company+title+city).encode()).hexdigest()[:8]}",
        title=title,
        company=company,
        city=city,
        salary=payload.get("salary", ""),
        jd_text=payload.get("jd_text", ""),
        source_url=payload.get("source_url", ""),
        capture_company_name=company,
        capture_dedupe_key=capture_dedupe_key,
        application_status="active",
        source="manual",
        fetched_at=now,
        dedupe_key=dedupe_key,
    )


def _make_dedupe_key(company: str, title: str, city: str) -> str:
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{city.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]
