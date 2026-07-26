from __future__ import annotations
from datetime import datetime, timedelta
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import json
from pathlib import Path

from app.models.job import JobRecord, JobFilter
from app.services.workflow_persistence import write_json_atomic
from app.services.city_codes import list_city_options
from app.services.boss_filter_options import list_filter_options, normalize_capture_filters
from app.services.company_blacklist import (
    add_company_to_blacklist,
    filter_blacklisted_jobs,
    is_company_blacklisted,
    load_company_blacklist,
    remove_company_from_blacklist,
)
from app.services.job_capture import _make_dedupe_key
from app.services.job_filters import filter_jobs_by_model
from app.services.job_ingest import (
    ingest_sample_jobs, ingest_manual_job, ingest_from_boss, normalize_job,
)
from app.services.workflow_tasks import complete_task, fail_task, partial_fail_task, start_task

logger = logging.getLogger("jobs_route")


router = APIRouter(prefix="/api/jobs", tags=["jobs"])
APPLICATION_STATUSES = {"pending", "greeted", "applied", "interviewing", "rejected", "abandoned"}
DECISION_STATUSES = {"undecided", "recommended", "watching", "abandoned", "risky"}

# ---------- 持久化目录 ----------
DATA_DIR = Path(__file__).resolve().parents[3] / "data"
JOBS_DIR = DATA_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
JOBS_FILE = JOBS_DIR / "jobs.json"


# ---------- 内存存储 ----------
_job_store: dict[str, JobRecord] = {}


def _save_jobs():
    """持久化全部岗位到磁盘。写入失败时记录日志。"""
    data = {jid: job.model_dump() for jid, job in _job_store.items()}
    try:
        write_json_atomic(JOBS_FILE, data)
    except OSError as e:
        logger.error("保存岗位数据失败: %s", e)


def _load_jobs():
    """从磁盘恢复全部岗位。90 天前的岗位先标记为疑似过期，由用户决定是否清理。"""
    if not JOBS_FILE.exists():
        return
    cutoff = (datetime.now() - timedelta(days=90)).isoformat()
    try:
        data = json.loads(JOBS_FILE.read_text())
        marked = 0
        skipped = 0
        for jid, job_data in data.items():
            try:
                job = JobRecord.model_validate(job_data)
                fetched = job.fetched_at
                if fetched and fetched < cutoff and job.lifecycle_status not in ("suspected_expired", "blacklisted"):
                    job.lifecycle_status = "suspected_expired"
                    job.expires_at = cutoff
                    job.stale_reason = "抓取时间超过 90 天"
                    marked += 1
                _job_store[jid] = job
            except Exception as e:
                skipped += 1
                logger.warning("跳过损坏的岗位记录 %s: %s", jid, e)
        if marked or skipped:
            _save_jobs()
            logger.info("岗位恢复: %d 条, 标记疑似过期: %d, 跳过损坏: %d", len(_job_store), marked, skipped)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("岗位数据文件损坏，已清空岗位池: %s", e)
        # 备份损坏文件
        try:
            backup = JOBS_FILE.with_suffix(".json.bak")
            JOBS_FILE.rename(backup)
        except OSError:
            pass


# 模块加载时恢复数据
_load_jobs()


def _all_jobs() -> list[JobRecord]:
    return list(_job_store.values())


def _visible_jobs() -> list[JobRecord]:
    return [job for job in _job_store.values() if job.lifecycle_status != "blacklisted"]


def _dedupe_keys() -> set[str]:
    return {job.dedupe_key for job in _job_store.values() if job.dedupe_key}


def _apply_blacklist_to_store() -> int:
    hidden = 0
    for job in _job_store.values():
        if is_company_blacklisted(job.company) and job.lifecycle_status != "blacklisted":
            job.lifecycle_status = "blacklisted"
            job.stale_reason = "企业在黑名单中，已隐藏"
            hidden += 1
    if hidden:
        _save_jobs()
    return hidden


def _restore_unblacklisted_jobs() -> int:
    restored = 0
    for job in _job_store.values():
        if job.lifecycle_status == "blacklisted" and not is_company_blacklisted(job.company):
            job.lifecycle_status = "active"
            job.stale_reason = ""
            restored += 1
    if restored:
        _save_jobs()
    return restored


def _refresh_job_dedupe_key(job: JobRecord) -> str:
    job.dedupe_key = _make_dedupe_key(job.company, job.title, job.city)
    return job.dedupe_key


def _dedupe_new_jobs(jobs: list[JobRecord], existing_keys: set[str]) -> tuple[list[JobRecord], int]:
    kept = []
    seen = set(existing_keys)
    removed = 0
    for job in jobs:
        key = _refresh_job_dedupe_key(job)
        if key and key in seen:
            removed += 1
            continue
        if key:
            seen.add(key)
        kept.append(job)
    return kept, removed


def _dedupe_store() -> int:
    seen: set[str] = set()
    removed = 0
    for jid, job in list(_job_store.items()):
        key = _refresh_job_dedupe_key(job)
        if key and key in seen:
            del _job_store[jid]
            removed += 1
            continue
        if key:
            seen.add(key)
    if removed:
        _save_jobs()
    return removed


def _job_quality_report() -> dict:
    jobs = _all_jobs()
    duplicate_index: dict[str, list[JobRecord]] = {}
    for job in jobs:
        key = job.dedupe_key or _make_dedupe_key(job.company, job.title, job.city)
        if not key:
            continue
        duplicate_index.setdefault(key, []).append(job)

    duplicate_groups = [
        {
            "key": key,
            "jobIds": [job.id for job in group],
            "title": group[0].title,
            "company": group[0].company,
            "city": group[0].city,
            "count": len(group),
            "withJd": sum(1 for job in group if bool((job.jd_text or "").strip())),
        }
        for key, group in duplicate_index.items()
        if len(group) > 1
    ]
    duplicate_groups.sort(key=lambda item: (-item["count"], item["company"], item["title"]))

    with_jd = sum(1 for job in jobs if bool((job.jd_text or "").strip()))
    suspected_expired = sum(1 for job in jobs if job.lifecycle_status == "suspected_expired")
    blacklisted = sum(1 for job in jobs if job.lifecycle_status == "blacklisted" or is_company_blacklisted(job.company))
    duplicate_jobs = sum(group["count"] for group in duplicate_groups)
    application_statuses = {status: 0 for status in APPLICATION_STATUSES}
    for job in jobs:
        status = job.application_status if job.application_status in APPLICATION_STATUSES else "pending"
        application_statuses[status] += 1
    return {
        "summary": {
            "total": len(jobs),
            "with_jd": with_jd,
            "missing_jd": len(jobs) - with_jd,
            "suspected_expired": suspected_expired,
            "blacklisted": blacklisted,
            "duplicate_groups": len(duplicate_groups),
            "duplicate_jobs": duplicate_jobs,
            "application_statuses": application_statuses,
        },
        "duplicateGroups": duplicate_groups,
    }


# ---------- 路由 ----------

@router.get("/pool")
def list_jobs(include_hidden: bool = False) -> dict:
    """获取全部岗位池。"""
    jobs = _all_jobs() if include_hidden else _visible_jobs()
    expired = [job for job in jobs if job.lifecycle_status == "suspected_expired"]
    hidden = [job for job in jobs if job.lifecycle_status == "blacklisted"]
    return {
        "jobs": [job.model_dump() for job in jobs],
        "total": len(jobs),
        "suspected_expired": len(expired),
        "hidden": len(hidden),
    }


@router.get("/pool/quality")
def job_pool_quality() -> dict:
    """岗位池质量摘要，用于前端展示 JD 完整度、过期和重复风险。"""
    return _job_quality_report()


@router.get("/cities")
def list_job_cities() -> dict:
    cities = list_city_options()
    return {"cities": cities, "total": len(cities)}


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
    _save_jobs()
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


@router.post("/enrich-jd")
def enrich_jd_details(payload: dict) -> dict:
    """为已有岗位补充详情页 JD。"""
    from app.services.boss_scraper import enrich_jobs_with_details
    job_ids = payload.get("job_ids", [])
    max_jobs = min(int(payload.get("max_jobs", 20)), 50)
    
    jobs_to_enrich = [_job_store[jid] for jid in job_ids if jid in _job_store]
    if not jobs_to_enrich:
        jobs_to_enrich = list(_job_store.values())
    task = start_task("jd_enrich", "获取 JD 详情", total=min(len(jobs_to_enrich), max_jobs), payload={"job_ids": job_ids, "max_jobs": max_jobs})
    
    try:
        enriched = enrich_jobs_with_details(jobs_to_enrich, max_jobs=max_jobs)
        removed_duplicates = _dedupe_store()
        removed = _apply_blacklist_to_store()
        _save_jobs()
        message = f"JD 详情补充完成，成功 {int(enriched or 0)} 个"
        if removed_duplicates:
            message += f"，重复过滤 {removed_duplicates} 个"
        if removed:
            message += f"，黑名单过滤 {removed} 个"
        result = {
            "enriched": int(enriched or 0),
            "removed_duplicates": removed_duplicates,
            "removed_by_blacklist": removed,
            "message": message,
        }
        total = min(len(jobs_to_enrich), max_jobs)
        if total and int(enriched or 0) < total:
            fail_message = f"JD 详情部分完成，成功 {int(enriched or 0)}/{total}"
            partial_fail_task(task["id"], int(enriched or 0), total, fail_message, "JD_PARTIAL", "检查 BOSS 登录状态后重试未完成岗位")
        else:
            complete_task(task["id"], done=int(enriched or 0), message=message)
        return result
    except Exception as e:
        fail_task(task["id"], str(e), "JD_ENRICH_FAILED", "重新检测 BOSS 登录状态后重试")
        raise HTTPException(status_code=500, detail=f"JD 补充失败: {e}")


@router.get("/capture/boss/status")
def boss_login_status() -> dict:
    """检查 BOSS 直聘登录状态。"""
    from app.services.boss_scraper import check_login_status
    return check_login_status()


@router.get("/capture/boss/filter-options")
def boss_capture_filter_options() -> dict:
    return list_filter_options()


@router.post("/capture/boss")
def capture_from_boss_endpoint(payload: dict) -> dict:
    """从 Boss 直聘真实抓取岗位。"""
    keyword = payload.get("keyword", "Python")
    city = payload.get("city") or ""  # 空字符串 = 全国
    max_pages = min(int(payload.get("max_pages", 3)), 10)
    headless = payload.get("headless", True)
    filters = normalize_capture_filters(payload.get("filters"))
    task = start_task("job_capture", "BOSS 岗位抓取", total=max_pages, payload={"keyword": keyword, "city": city, "filters": filters})

    existing = _dedupe_keys()
    try:
        new_jobs = ingest_from_boss(
            keyword=keyword,
            city=city,
            max_pages=max_pages,
            headless=headless,
            filters=filters,
            existing_dedupe_keys=existing,
        )
    except RuntimeError as e:
        fail_task(task["id"], str(e), "BOSS_CAPTURE_FAILED", "重新登录 BOSS 或稍后重试")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        fail_task(task["id"], str(e), "BOSS_CAPTURE_FAILED", "检查网络和 BOSS 页面状态后重试")
        raise HTTPException(status_code=500, detail=f"Boss 抓取失败: {e}")

    new_jobs, removed_duplicates = _dedupe_new_jobs(new_jobs, existing)
    new_jobs, removed_jobs = filter_blacklisted_jobs(new_jobs)
    for job in removed_jobs:
        job.lifecycle_status = "blacklisted"
        job.stale_reason = "企业在黑名单中，已隐藏"
    new_jobs = [*new_jobs, *removed_jobs]
    for job in new_jobs:
        _job_store[job.id] = job
    _save_jobs()

    message = f"岗位抓取完成，新增 {len(new_jobs)} 个"
    complete_task(task["id"], done=max_pages, message=message)
    return {
        "captured": len(new_jobs),
        "total": len(_job_store),
        "keyword": keyword,
        "city": city,
        "filters": filters,
        "removed_duplicates": removed_duplicates,
        "removed_by_blacklist": len(removed_jobs),
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
    _save_jobs()
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


# ---------- 企业黑名单 ----------

class CompanyBlacklistRequest(BaseModel):
    company_name: str


@router.get("/company-blacklist")
def list_company_blacklist() -> dict:
    companies = load_company_blacklist()
    return {"companies": companies, "total": len(companies)}


@router.post("/company-blacklist")
def add_company_blacklist(payload: CompanyBlacklistRequest) -> dict:
    try:
        companies = add_company_to_blacklist(payload.company_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="缺少公司名称")
    removed = _apply_blacklist_to_store()
    return {"companies": companies, "total": len(companies), "removed": removed}


@router.delete("/company-blacklist")
def delete_company_blacklist(payload: CompanyBlacklistRequest) -> dict:
    companies = remove_company_from_blacklist(payload.company_name)
    restored = _restore_unblacklisted_jobs()
    return {"companies": companies, "total": len(companies), "restored": restored}


@router.get("/company-blacklist/export")
def export_company_blacklist() -> dict:
    companies = load_company_blacklist()
    return {
        "kind": "company_blacklist",
        "version": 1,
        "exportedAt": datetime.now().isoformat(),
        "companies": companies,
        "total": len(companies),
    }


@router.post("/company-blacklist/import")
def import_company_blacklist(payload: dict) -> dict:
    companies = payload.get("companies", [])
    if not isinstance(companies, list):
        raise HTTPException(status_code=400, detail="companies 必须是数组")
    imported = []
    for item in companies:
        name = item.get("name") if isinstance(item, dict) else str(item)
        if str(name or "").strip():
            imported = add_company_to_blacklist(str(name).strip())
    removed = _apply_blacklist_to_store()
    companies = imported or load_company_blacklist()
    return {"companies": companies, "total": len(companies), "removed": removed}


# ---------- 岗位生命周期 ----------

class JobIdsRequest(BaseModel):
    job_ids: list[str] = Field(default_factory=list)


def _status_rank(status: str) -> int:
    order = ["pending", "greeted", "applied", "interviewing", "rejected", "abandoned"]
    return order.index(status) if status in order else 0


@router.post("/duplicates/merge")
def merge_duplicate_jobs(payload: JobIdsRequest) -> dict:
    job_ids = [jid for jid in payload.job_ids if jid in _job_store]
    if len(job_ids) < 2:
        raise HTTPException(status_code=400, detail="至少选择 2 个重复岗位")

    jobs = [_job_store[jid] for jid in job_ids]
    keeper = max(jobs, key=lambda job: (len((job.jd_text or "").strip()), len(job.keywords or []), job.fetched_at or ""))
    removed: list[str] = []

    merged_tags: list[str] = list(keeper.tags or [])
    merged_keywords: list[str] = list(keeper.keywords or [])
    for job in [keeper, *[job for job in jobs if job.id != keeper.id]]:
        for tag in job.tags or []:
            if tag not in merged_tags:
                merged_tags.append(tag)
        for keyword in job.keywords or []:
            if keyword not in merged_keywords:
                merged_keywords.append(keyword)
        if job.greeted:
            keeper.greeted = True
        if _status_rank(job.application_status) > _status_rank(keeper.application_status):
            keeper.application_status = job.application_status
            keeper.application_note = job.application_note
            keeper.application_updated_at = job.application_updated_at
        if not keeper.structured_summary and job.structured_summary:
            keeper.structured_summary = job.structured_summary
        if not keeper.source_url and job.source_url:
            keeper.source_url = job.source_url

    keeper.tags = merged_tags
    keeper.keywords = merged_keywords
    if keeper.greeted and keeper.application_status == "pending":
        keeper.application_status = "greeted"
        keeper.application_updated_at = datetime.now().isoformat()

    for jid in job_ids:
        if jid == keeper.id:
            continue
        del _job_store[jid]
        removed.append(jid)
    _save_jobs()
    return {"kept": keeper.id, "removed": removed, "job": keeper.model_dump(), "total": len(_job_store)}


@router.post("/expired/cleanup")
def cleanup_expired_jobs(payload: JobIdsRequest | None = None) -> dict:
    target_ids = set((payload.job_ids if payload else []) or [])
    deleted = 0
    for jid, job in list(_job_store.items()):
        if job.lifecycle_status != "suspected_expired":
            continue
        if target_ids and jid not in target_ids:
            continue
        del _job_store[jid]
        deleted += 1
    _save_jobs()
    return {"deleted": deleted, "total": len(_job_store)}


@router.post("/expired/keep")
def keep_expired_jobs(payload: JobIdsRequest | None = None) -> dict:
    target_ids = set((payload.job_ids if payload else []) or [])
    updated = 0
    for jid, job in _job_store.items():
        if job.lifecycle_status != "suspected_expired":
            continue
        if target_ids and jid not in target_ids:
            continue
        job.lifecycle_status = "active"
        job.expires_at = ""
        job.stale_reason = ""
        updated += 1
    _save_jobs()
    return {"updated": updated, "total": len(_job_store)}




# ---------- 标签 ----------

class TagJobRequest(BaseModel):
    job_id: str
    greeted: bool | None = None
    tags: list[str] | None = None

@router.post("/tag")
def tag_job(payload: TagJobRequest) -> dict:
    if payload.job_id not in _job_store:
        raise HTTPException(status_code=404, detail="岗位不存在")
    job = _job_store[payload.job_id]
    if payload.greeted is not None:
        job.greeted = payload.greeted
        if payload.greeted and job.application_status == "pending":
            job.application_status = "greeted"
            job.application_updated_at = datetime.now().isoformat()
    if payload.tags is not None:
        job.tags = payload.tags
    _save_jobs()
    return {
        "job_id": payload.job_id,
        "greeted": job.greeted,
        "tags": job.tags,
    }


class JobStatusRequest(BaseModel):
    job_id: str
    status: str
    note: str = ""


class JobDecisionRequest(BaseModel):
    job_id: str
    status: str


@router.post("/status")
def update_job_status(payload: JobStatusRequest) -> dict:
    if payload.job_id not in _job_store:
        raise HTTPException(status_code=404, detail="岗位不存在")
    status = payload.status.strip()
    if status not in APPLICATION_STATUSES:
        raise HTTPException(status_code=400, detail="未知求职状态")
    job = _job_store[payload.job_id]
    job.application_status = status
    job.application_note = payload.note.strip()
    job.application_updated_at = datetime.now().isoformat()
    job.greeted = status in {"greeted", "applied", "interviewing"}
    _save_jobs()
    return {
        "job_id": payload.job_id,
        "application_status": job.application_status,
        "application_note": job.application_note,
        "application_updated_at": job.application_updated_at,
        "greeted": job.greeted,
    }


@router.post("/decision")
def update_job_decision(payload: JobDecisionRequest) -> dict:
    if payload.job_id not in _job_store:
        raise HTTPException(status_code=404, detail="岗位不存在")
    status = payload.status.strip()
    if status not in DECISION_STATUSES:
        raise HTTPException(status_code=400, detail="未知决策标签")
    job = _job_store[payload.job_id]
    job.decision_status = status
    _save_jobs()
    return {
        "job_id": payload.job_id,
        "decision_status": job.decision_status,
    }

# ---------- 删除 ----------

class BatchDeleteRequest(BaseModel):
    job_ids: list[str]

@router.delete("/batch")
def delete_batch_jobs(payload: BatchDeleteRequest) -> dict:
    """批量删除岗位。"""
    deleted = 0
    for jid in payload.job_ids:
        if jid in _job_store:
            del _job_store[jid]
            deleted += 1
    _save_jobs()
    return {"deleted": deleted, "total": len(_job_store)}


@router.delete("/{job_id}")
def delete_job(job_id: str) -> dict:
    """删除单个岗位。"""
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail=f"岗位 {job_id} 不存在")
    del _job_store[job_id]
    _save_jobs()
    return {"deleted": job_id, "total": len(_job_store)}


@router.delete("")
def clear_all_jobs() -> dict:
    """清空全部岗位。"""
    count = len(_job_store)
    _job_store.clear()
    _save_jobs()
    return {"deleted": count, "total": 0}
