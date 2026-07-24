from fastapi import APIRouter, HTTPException

from app.models.job import JobRecord, JobFilter
from app.services.job_filters import match_job_filters, filter_jobs_by_model
from app.services.job_ingest import (
    ingest_sample_jobs, ingest_manual_job, ingest_from_boss, normalize_job,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ---------- 内存存储 ----------
_job_store: dict[str, JobRecord] = {}


def _load_sample_jobs_if_empty():
    if not _job_store:
        jobs = ingest_sample_jobs()
        for job in jobs:
            _job_store[job.id] = job


def _all_jobs() -> list[JobRecord]:
    return list(_job_store.values())


def _dedupe_keys() -> set[str]:
    return {job.dedupe_key for job in _job_store.values() if job.dedupe_key}


# ---------- 路由 ----------

@router.get("/pool")
def list_jobs() -> dict:
    """获取全部岗位池。"""
    jobs = _all_jobs()
    return {"jobs": [job.model_dump() for job in jobs], "total": len(jobs)}


@router.post("/capture")
def capture_sample() -> dict:
    """从示例数据抓取岗位。"""
    existing = _dedupe_keys()
    try:
        new_jobs = ingest_sample_jobs(existing_dedupe_keys=existing)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"抓取失败: {e}")
    for job in new_jobs:
        _job_store[job.id] = job
    return {"captured": len(new_jobs), "total": len(_job_store)}



@router.post("/capture/boss/login")
def boss_login() -> dict:
    """打开浏览器让用户登录 Boss 直聘，保存 session。"""
    from app.services.boss_scraper import login_boss_sync
    try:
        result = login_boss_sync(headless=False)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录失败: {e}")


@router.post("/capture/boss")
def capture_from_boss_endpoint(payload: dict) -> dict:
    """
    从 Boss 直聘真实抓取岗位。
    
    参数：
    - keyword: 搜索关键词，默认 "Python"
    - city: 城市名，默认 "深圳"
    - max_pages: 最多翻页数，默认 3
    - headless: 是否无头模式，默认 true
    """
    keyword = payload.get("keyword", "Python")
    city = payload.get("city", "深圳")
    max_pages = min(int(payload.get("max_pages", 3)), 10)  # 最多 10 页
    headless = payload.get("headless", True)

    existing = _dedupe_keys()
    try:
        new_jobs = ingest_from_boss(
            keyword=keyword,
            city=city,
            max_pages=max_pages,
            headless=headless,
            existing_dedupe_keys=existing,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Boss 抓取失败: {e}")

    for job in new_jobs:
        _job_store[job.id] = job
    return {
        "captured": len(new_jobs),
        "total": len(_job_store),
        "keyword": keyword,
        "city": city,
    }


@router.post("/manual")
def add_manual_job(payload: dict) -> dict:
    """手动录入岗位。"""
    existing = _dedupe_keys()
    try:
        job = ingest_manual_job(payload, existing_dedupe_keys=existing)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    _job_store[job.id] = job
    return job.model_dump()


@router.post("/filter")
def filter_jobs(payload: dict) -> dict:
    """筛选岗位池中的岗位。"""
    jobs = _all_jobs()
    filters = JobFilter.model_validate(payload.get("filters", {}))
    matched = filter_jobs_by_model(jobs, filters)
    return {"jobs": [job.model_dump() for job in matched], "total": len(matched)}


@router.post("/normalize", response_model=JobRecord)
def normalize_job_endpoint(payload: dict) -> JobRecord:
    """归一化一个原始岗位 dict。"""
    return normalize_job(payload)


# ---------- 删除 ----------

@router.delete("/{job_id}")
def delete_job(job_id: str) -> dict:
    """删除单个岗位。"""
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail=f"岗位 {job_id} 不存在")
    del _job_store[job_id]
    return {"deleted": job_id, "total": len(_job_store)}


@router.delete("")
def clear_all_jobs() -> dict:
    """清空全部岗位。"""
    count = len(_job_store)
    _job_store.clear()
    return {"deleted": count, "total": 0}


@router.post("/enrich")
def enrich_jobs_endpoint(payload: dict) -> dict:
    """为岗位池中的 Boss 岗位补充详情页 JD。

    参数：
    - max_jobs: 最多处理几个岗位，默认 10
    """
    from app.services.boss_scraper import enrich_jobs_with_details

    max_jobs = min(int(payload.get("max_jobs", 10)), 30)
    jobs = _all_jobs()

    try:
        enriched = enrich_jobs_with_details(jobs, max_jobs=max_jobs)
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD 补充失败: {e}")

    # 更新存储
    for job in enriched:
        jid = job.id if hasattr(job, 'id') else job.get('id', '')
        if jid in _job_store:
            _job_store[jid] = job

    # 统计实际补充了几个
    count = 0
    for j in enriched:
        jd = j.jd_text if hasattr(j, 'jd_text') else j.get('jd_text', '')
        if len(jd) > 100:
            count += 1
    return {"enriched": count, "total": len(_job_store)}
