"""岗位接入服务：捕获、识别、去重、输出。"""
from __future__ import annotations

from app.models.job import JobRecord
from app.services.job_capture import (
    jobs_from_source, jobs_from_manual_payload,
    capture_from_boss,
)
from app.services.job_recognition import recognize_job


def ingest_from_boss(
    keyword: str = "Python",
    city: str = "深圳",
    max_pages: int = 3,
    headless: bool = True,
    filters: dict[str, str] | None = None,
    existing_dedupe_keys: set[str] | None = None,
    existing_source_urls: set[str] | None = None,
) -> list[JobRecord]:
    """从 Boss 直聘真实抓取并接入。"""
    existing = existing_dedupe_keys or set()
    existing_urls = existing_source_urls or set()
    sources = capture_from_boss(keyword=keyword, city=city, max_pages=max_pages, headless=headless, filters=filters)
    jobs: list[JobRecord] = []
    for source in sources:
        source_url = str(source.raw_payload.get("source_url") or "").strip()
        if source.dedupe_key in existing or (source_url and source_url in existing_urls):
            continue
        job = jobs_from_source(source)
        job = recognize_job(job)
        jobs.append(job)
    return jobs


def ingest_manual_job(payload: dict, existing_dedupe_keys: set[str] | None = None) -> JobRecord:
    """手动录入一个岗位。"""
    existing = existing_dedupe_keys or set()
    job = jobs_from_manual_payload(payload)
    if job.dedupe_key in existing:
        raise ValueError(f"岗位已存在：{job.company} {job.title}（{job.city}）")
    job = recognize_job(job)
    return job


def normalize_job(raw: dict) -> JobRecord:
    """兼容旧接口：直接归一化一个 dict。"""
    job = JobRecord(**{k: v for k, v in raw.items() if k in JobRecord.model_fields})
    return recognize_job(job)
