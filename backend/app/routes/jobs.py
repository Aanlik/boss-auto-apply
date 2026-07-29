from __future__ import annotations
from datetime import datetime, timedelta
import csv
import hashlib
import io
import logging
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
import json
from pathlib import Path

from app.models.job import JobRecord, JobFilter
from app.services import workflow_persistence
from app.services.workflow_persistence import _read_json, write_json_atomic
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
    ingest_manual_job, ingest_from_boss, normalize_job,
)
from app.services.workflow_tasks import complete_task, fail_task, partial_fail_task, start_task
from app.services.maintenance_service import active_store, log_api_call, log_event

logger = logging.getLogger("jobs_route")


router = APIRouter(prefix="/api/jobs", tags=["jobs"])
APPLICATION_STATUSES = {"pending", "greeted", "applied", "interviewing", "rejected", "abandoned"}
DECISION_STATUSES = {"undecided", "recommended", "watching", "abandoned", "risky"}

# ---------- 持久化目录 ----------
DATA_DIR = workflow_persistence.DATA_DIR
JOBS_DIR = DATA_DIR / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
JOBS_FILE = JOBS_DIR / "jobs.json"
DELETED_JOBS_FILE = JOBS_DIR / "deleted_jobs.json"
SEARCH_PRESETS_FILE = JOBS_DIR / "search_presets.json"


# ---------- 内存存储 ----------
_job_store: dict[str, JobRecord] = {}


def _save_jobs():
    """持久化全部岗位到磁盘。写入失败时记录日志。"""
    data = {jid: job.model_dump() for jid, job in _job_store.items()}
    try:
        if JOBS_FILE.exists():
            backup = JOBS_FILE.with_suffix(".json.bak")
            backup.write_text(JOBS_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        write_json_atomic(JOBS_FILE, data)
        if active_store() == "sqlite":
            from app.services import job_sqlite_store
            job_sqlite_store.save_jobs(_job_store)
    except OSError as e:
        logger.error("保存岗位数据失败: %s", e)


def _archive_jobs(job_ids: list[str]) -> int:
    archived = _read_json(DELETED_JOBS_FILE, {})
    if not isinstance(archived, dict):
        archived = {}
    count = 0
    for job_id in job_ids:
        job = _job_store.get(job_id)
        if job is None:
            continue
        archived[job_id] = {
            "deletedAt": datetime.now().isoformat(),
            "job": job.model_dump(),
        }
        count += 1
    if count:
        write_json_atomic(DELETED_JOBS_FILE, archived)
    return count


def _restore_jobs(job_ids: list[str]) -> int:
    archived = _read_json(DELETED_JOBS_FILE, {})
    if not isinstance(archived, dict):
        return 0
    restored = 0
    remaining = dict(archived)
    for job_id in job_ids:
        item = archived.get(job_id)
        if not isinstance(item, dict) or not isinstance(item.get("job"), dict):
            continue
        _job_store[job_id] = JobRecord.model_validate(item["job"])
        remaining.pop(job_id, None)
        restored += 1
    if restored:
        write_json_atomic(DELETED_JOBS_FILE, remaining)
        _save_jobs()
    return restored


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


def _load_search_presets() -> list[dict]:
    try:
        if not SEARCH_PRESETS_FILE.exists():
            return []
        data = json.loads(SEARCH_PRESETS_FILE.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_search_presets(presets: list[dict]) -> None:
    write_json_atomic(SEARCH_PRESETS_FILE, presets[-50:])


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
    batch_index: dict[str, dict] = {}
    for job in jobs:
        status = job.application_status if job.application_status in APPLICATION_STATUSES else "pending"
        application_statuses[status] += 1
        batch_id = job.capture_batch_id or "manual"
        batch = batch_index.setdefault(
            batch_id,
            {
                "id": batch_id,
                "keyword": job.capture_keyword,
                "city": job.capture_city,
                "filters": job.capture_filters or {},
                "capturedAt": job.captured_at or job.fetched_at,
                "total": 0,
                "with_jd": 0,
                "missing_jd": 0,
                "blacklisted": 0,
                "suspected_expired": 0,
            },
        )
        batch["total"] += 1
        if (job.jd_text or "").strip():
            batch["with_jd"] += 1
        else:
            batch["missing_jd"] += 1
        if job.lifecycle_status == "blacklisted" or is_company_blacklisted(job.company):
            batch["blacklisted"] += 1
        if job.lifecycle_status == "suspected_expired":
            batch["suspected_expired"] += 1
        if job.captured_at and (not batch.get("capturedAt") or job.captured_at > batch["capturedAt"]):
            batch["capturedAt"] = job.captured_at
    batches = sorted(
        batch_index.values(),
        key=lambda item: (item.get("capturedAt") or "", item.get("id") or ""),
        reverse=True,
    )
    for batch in batches:
        total = batch["total"] or 1
        batch["jd_completion_rate"] = round(batch["with_jd"] / total * 100)
        batch["stale_rate"] = round((batch["suspected_expired"] + batch["blacklisted"]) / total * 100)
        batch["risk_rate"] = round(batch["blacklisted"] / total * 100)
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
            "batch_count": len(batch_index),
        },
        "duplicateGroups": duplicate_groups,
        "batches": batches,
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


@router.get("/export")
def export_jobs(format: str = "json"):
    jobs = [job.model_dump() for job in _all_jobs()]
    if format == "json":
        return {
            "jobs": jobs,
            "total": len(jobs),
            "quality": _job_quality_report(),
            "exportedAt": datetime.now().isoformat(),
        }
    if format == "csv":
        output = io.StringIO()
        fields = [
            "id",
            "title",
            "company",
            "city",
            "salary",
            "source",
            "source_url",
            "capture_batch_id",
            "capture_keyword",
            "capture_city",
            "captured_at",
            "application_status",
            "decision_status",
            "lifecycle_status",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="jobs.csv"'},
        )
    raise HTTPException(status_code=400, detail="导出格式必须是 json/csv")


@router.get("/cities")
def list_job_cities() -> dict:
    cities = list_city_options()
    return {"cities": cities, "total": len(cities)}


@router.get("/search-presets")
def list_search_presets() -> dict:
    presets = sorted(_load_search_presets(), key=lambda item: item.get("updatedAt", ""), reverse=True)
    return {"presets": presets, "total": len(presets)}


@router.post("/search-presets")
def save_search_preset(payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="预设名称不能为空")
    now = datetime.now().isoformat()
    preset_id = str(payload.get("id") or "").strip() or uuid4().hex
    preset = {
        "id": preset_id,
        "name": name,
        "keyword": str(payload.get("keyword") or "").strip(),
        "city": str(payload.get("city") or "").strip(),
        "max_pages": max(1, min(int(payload.get("max_pages") or 3), 10)),
        "filters": payload.get("filters") if isinstance(payload.get("filters"), dict) else {},
        "job_filters": payload.get("job_filters") if isinstance(payload.get("job_filters"), dict) else {},
        "createdAt": str(payload.get("createdAt") or now),
        "updatedAt": now,
    }
    presets = [item for item in _load_search_presets() if item.get("id") != preset_id]
    presets.append(preset)
    _save_search_presets(presets)
    return {"preset": preset, "total": len(presets)}


@router.delete("/search-presets/{preset_id}")
def delete_search_preset(preset_id: str) -> dict:
    presets = _load_search_presets()
    next_presets = [item for item in presets if item.get("id") != preset_id]
    _save_search_presets(next_presets)
    return {"deleted": preset_id, "total": len(next_presets)}


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
    force = bool(payload.get("force", False))
    
    requested_jobs = [_job_store[jid] for jid in job_ids if jid in _job_store]
    if not requested_jobs:
        requested_jobs = list(_job_store.values())
    skipped_existing_jd = 0 if force else sum(1 for job in requested_jobs if (job.jd_text or "").strip())
    jobs_to_enrich = requested_jobs if force else [job for job in requested_jobs if not (job.jd_text or "").strip()]
    task = start_task(
        "jd_enrich",
        "获取 JD 详情",
        total=min(len(jobs_to_enrich), max_jobs),
        payload={"job_ids": job_ids, "max_jobs": max_jobs, "force": force},
        idempotency_key=f"jd_enrich:{','.join(sorted(job.id for job in jobs_to_enrich))}:{max_jobs}",
    )

    if not jobs_to_enrich:
        message = "没有缺少 JD 的岗位需要抓取" if not force else "没有可重新抓取 JD 的岗位"
        result = {
            "enriched": 0,
            "removed_duplicates": 0,
            "removed_by_blacklist": 0,
            "skipped_existing_jd": skipped_existing_jd,
            "message": message,
        }
        complete_task(task["id"], done=0, message=message)
        return result
    
    try:
        start_time = datetime.now()
        enriched = enrich_jobs_with_details(jobs_to_enrich, max_jobs=max_jobs)
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        removed_duplicates = _dedupe_store()
        removed = _apply_blacklist_to_store()
        _save_jobs()
        for job in jobs_to_enrich[:max_jobs]:
            log_api_call("boss_detail", "GET", job.source_url or "https://www.zhipin.com/job_detail/", 200, duration_ms, {
                "scope": "detail",
                "jobId": job.id,
                "company": job.company,
                "title": job.title,
                "hasJd": bool((job.jd_text or "").strip()),
            })
        message = f"JD 详情补充完成，成功 {int(enriched or 0)} 个"
        if skipped_existing_jd:
            message += f"，跳过已有 JD {skipped_existing_jd} 个"
        if removed_duplicates:
            message += f"，重复过滤 {removed_duplicates} 个"
        if removed:
            message += f"，黑名单过滤 {removed} 个"
        result = {
            "enriched": int(enriched or 0),
            "removed_duplicates": removed_duplicates,
            "removed_by_blacklist": removed,
            "skipped_existing_jd": skipped_existing_jd,
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


@router.post("/enrich-jd/retry-failed/{task_id}")
def retry_failed_jd_details(task_id: str) -> dict:
    from app.services.workflow_tasks import get_task

    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    job_ids = payload.get("failed_job_ids") or payload.get("job_ids") or []
    if not isinstance(job_ids, list) or not job_ids:
        raise HTTPException(status_code=400, detail="任务中没有可重试的岗位 ID")
    result = enrich_jd_details({"job_ids": job_ids, "max_jobs": int(payload.get("max_jobs") or len(job_ids))})
    return {**result, "job_ids": [str(item) for item in job_ids]}


@router.get("/capture/boss/status")
def boss_login_status() -> dict:
    """检查 BOSS 直聘登录状态（仅检查本地标记，不触发浏览器页面）。"""
    from app.services.boss_scraper import check_login_status
    return check_login_status(probe=False)


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
    batch_id = uuid4().hex
    captured_at = datetime.now().isoformat()
    task = start_task(
        "job_capture",
        "BOSS 岗位抓取",
        total=max_pages,
        payload={"keyword": keyword, "city": city, "filters": filters, "capture_batch_id": batch_id},
        idempotency_key=f"job_capture:{keyword}:{city}:{max_pages}:{json.dumps(filters, ensure_ascii=False, sort_keys=True)}",
    )

    existing = _dedupe_keys()
    try:
        start_time = datetime.now()
        new_jobs = ingest_from_boss(
            keyword=keyword,
            city=city,
            max_pages=max_pages,
            headless=headless,
            filters=filters,
            existing_dedupe_keys=existing,
        )
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    except RuntimeError as e:
        log_api_call("boss_capture", "GET", "https://www.zhipin.com/wapi/zpgeek/search/joblist.json", 401, 0, {
            "scope": "summary",
            "keyword": keyword,
            "city": city,
            "pages": max_pages,
            "error": str(e)[:200],
        })
        fail_task(task["id"], str(e), "BOSS_CAPTURE_FAILED", "重新登录 BOSS 或稍后重试")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        log_api_call("boss_capture", "GET", "https://www.zhipin.com/wapi/zpgeek/search/joblist.json", 500, 0, {
            "scope": "summary",
            "keyword": keyword,
            "city": city,
            "pages": max_pages,
            "error": str(e)[:200],
        })
        fail_task(task["id"], str(e), "BOSS_CAPTURE_FAILED", "检查网络和 BOSS 页面状态后重试")
        raise HTTPException(status_code=500, detail=f"Boss 抓取失败: {e}")

    new_jobs, removed_duplicates = _dedupe_new_jobs(new_jobs, existing)
    new_jobs, removed_jobs = filter_blacklisted_jobs(new_jobs)
    per_page = max(1, round(len(new_jobs) / max_pages)) if max_pages else len(new_jobs)
    for page in range(1, max_pages + 1):
        page_count = len(new_jobs[(page - 1) * per_page: page * per_page]) if per_page else 0
        log_api_call("boss_capture", "GET", "https://www.zhipin.com/wapi/zpgeek/search/joblist.json", 200, duration_ms, {
            "scope": "page",
            "page": page,
            "keyword": keyword,
            "city": city,
            "filters": filters,
            "captured": page_count,
            "captureBatchId": batch_id,
        })
    for job in removed_jobs:
        job.lifecycle_status = "blacklisted"
        job.stale_reason = "企业在黑名单中，已隐藏"
    new_jobs = [*new_jobs, *removed_jobs]
    for job in new_jobs:
        job.capture_batch_id = batch_id
        job.capture_keyword = keyword
        job.capture_city = city
        job.capture_filters = filters
        job.captured_at = captured_at
        _job_store[job.id] = job
    _save_jobs()

    message = f"岗位抓取完成，新增 {len(new_jobs)} 个"
    log_api_call("boss_capture", "GET", "https://www.zhipin.com/wapi/zpgeek/search/joblist.json", 200, duration_ms, {
        "scope": "summary",
        "keyword": keyword,
        "city": city,
        "pages": max_pages,
        "captured": len(new_jobs),
        "removedDuplicates": removed_duplicates,
        "removedByBlacklist": len(removed_jobs),
        "captureBatchId": batch_id,
    })
    complete_task(task["id"], done=max_pages, message=message)
    return {
        "captured": len(new_jobs),
        "total": len(_job_store),
        "keyword": keyword,
        "city": city,
        "filters": filters,
        "capture_batch_id": batch_id,
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
    log_event("warning", "blacklist", f"企业加入黑名单: {payload.company_name}", {"company": payload.company_name, "hiddenJobs": removed})
    return {"companies": companies, "total": len(companies), "removed": removed}


@router.delete("/company-blacklist")
def delete_company_blacklist(payload: CompanyBlacklistRequest) -> dict:
    companies = remove_company_from_blacklist(payload.company_name)
    restored = _restore_unblacklisted_jobs()
    log_event("info", "blacklist", f"企业移出黑名单: {payload.company_name}", {"company": payload.company_name, "restoredJobs": restored})
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


def _parse_import_items(payload: dict) -> list[dict]:
    raw_items = payload.get("items")
    if isinstance(raw_items, list):
        return [item for item in raw_items if isinstance(item, dict)]
    text = str(payload.get("text") or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            data = json.loads(text)
            return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _import_job_from_item(item: dict, index: int) -> tuple[JobRecord | None, str]:
    title = str(item.get("title") or item.get("岗位") or item.get("职位") or "").strip()
    company = str(item.get("company") or item.get("公司") or item.get("企业") or "").strip()
    city = str(item.get("city") or item.get("城市") or "").strip()
    if not title or not company:
        return None, "缺少岗位名称或公司名称"
    seed = "|".join([
        str(item.get("id") or ""),
        title,
        company,
        city,
        str(item.get("source_url") or item.get("url") or item.get("链接") or ""),
        str(index),
    ])
    job_id = str(item.get("id") or "").strip() or f"import-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}"
    job = JobRecord(
        id=job_id,
        title=title,
        company=company,
        city=city,
        salary=str(item.get("salary") or item.get("薪资") or "").strip(),
        jd_text=str(item.get("jd_text") or item.get("jd") or item.get("JD") or item.get("岗位描述") or "").strip(),
        source=str(item.get("source") or "imported"),
        source_url=str(item.get("source_url") or item.get("url") or item.get("链接") or "").strip(),
        fetched_at=str(item.get("fetched_at") or datetime.now().isoformat()),
        tags=[str(tag).strip() for tag in (item.get("tags") if isinstance(item.get("tags"), list) else []) if str(tag).strip()],
    )
    _refresh_job_dedupe_key(job)
    return job, ""


def _import_wizard_preview(payload: dict) -> dict:
    items = _parse_import_items(payload)
    existing_keys = _dedupe_keys()
    seen_keys: set[str] = set()
    creates = []
    duplicates = []
    invalid = []
    for index, item in enumerate(items):
        job, reason = _import_job_from_item(item, index)
        if not job:
            invalid.append({"index": index, "reason": reason})
            continue
        key = job.dedupe_key
        if key in existing_keys or key in seen_keys or job.id in _job_store:
            duplicates.append({"index": index, "jobId": job.id, "company": job.company, "title": job.title, "city": job.city})
            continue
        seen_keys.add(key)
        creates.append(job)
    return {
        "kind": "jobs_import_wizard",
        "summary": {
            "total": len(items),
            "creates": len(creates),
            "duplicates": len(duplicates),
            "invalid": len(invalid),
        },
        "creates": [job.model_dump() for job in creates[:20]],
        "duplicates": duplicates[:20],
        "invalid": invalid[:20],
        "message": f"可新增 {len(creates)} 条，重复 {len(duplicates)} 条，无效 {len(invalid)} 条",
    }


@router.post("/import-wizard/preview")
def preview_jobs_import(payload: dict) -> dict:
    return _import_wizard_preview(payload)


@router.post("/import-wizard/apply")
def apply_jobs_import(payload: dict) -> dict:
    preview = _import_wizard_preview(payload)
    created = preview["creates"]
    for item in created:
        job = JobRecord.model_validate(item)
        job.source = "imported"
        _job_store[job.id] = job
    if created:
        _save_jobs()
    log_event("info", "jobs_import", f"岗位导入完成：新增 {len(created)} 条", {"preview": preview["summary"]})
    return {
        "imported": len(created),
        "skipped": int(preview["summary"]["duplicates"]) + int(preview["summary"]["invalid"]),
        "total": len(_job_store),
        "preview": preview,
    }


@router.get("/import-wizard/template")
def download_jobs_import_template() -> Response:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["title", "company", "city", "salary", "source_url", "jd_text"])
    writer.writeheader()
    writer.writerow({
        "title": "产品经理",
        "company": "示例科技有限公司",
        "city": "上海",
        "salary": "20-30K",
        "source_url": "https://www.zhipin.com/job_detail/example.html",
        "jd_text": "负责产品规划、需求分析和跨团队协作。",
    })
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="jobs-import-template.csv"'},
    )


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
    log_event("info", "job_merge", f"合并重复岗位，保留 {keeper.id}", {"kept": keeper.id, "removed": removed})
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
    log_event("warning", "job_delete", f"删除疑似过期岗位 {deleted} 个", {"jobIds": list(target_ids), "deleted": deleted})
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
    log_event("info", "job_keep", f"恢复疑似过期岗位 {updated} 个", {"jobIds": list(target_ids), "updated": updated})
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


def _append_job_history(job: JobRecord, kind: str, value: str, previous: str = "", note: str = "") -> dict:
    entry = {
        "kind": kind,
        "status": value,
        "previous": previous,
        "note": note,
        "at": datetime.now().isoformat(),
    }
    job.status_history = [*(job.status_history or []), entry][-100:]
    return entry


@router.get("/{job_id}/history")
def get_job_history(job_id: str) -> dict:
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return {"job_id": job_id, "history": _job_store[job_id].status_history or []}


@router.get("/application-timeline")
def application_timeline(limit: int = 50) -> dict:
    events: list[dict] = []
    summary = {status: 0 for status in APPLICATION_STATUSES}
    for job in _all_jobs():
        status = job.application_status if job.application_status in APPLICATION_STATUSES else "pending"
        summary[status] += 1
        for entry in job.status_history or []:
            if entry.get("kind") != "application":
                continue
            events.append({
                "jobId": job.id,
                "title": job.title,
                "company": job.company,
                "city": job.city,
                "status": entry.get("status") or "",
                "previous": entry.get("previous") or "",
                "note": entry.get("note") or "",
                "at": entry.get("at") or "",
            })
    events.sort(key=lambda item: item.get("at") or "", reverse=True)
    return {
        "summary": summary,
        "events": events[: max(1, min(int(limit or 50), 200))],
        "total": len(events),
    }


@router.get("/application-board")
def application_crm_board() -> dict:
    labels = {
        "pending": "待处理",
        "greeted": "已打招呼",
        "applied": "已投递",
        "interviewing": "面试中",
        "rejected": "已拒绝",
        "abandoned": "已放弃",
    }
    columns = {
        key: {"key": key, "label": label, "count": 0, "jobs": []}
        for key, label in labels.items()
    }
    for job in _all_jobs():
        status = job.application_status if job.application_status in columns else "pending"
        item = {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "city": job.city,
            "salary": job.salary,
            "decisionStatus": job.decision_status,
            "updatedAt": job.application_updated_at or job.fetched_at,
            "note": job.application_note,
        }
        columns[status]["jobs"].append(item)
        columns[status]["count"] += 1
    for column in columns.values():
        column["jobs"] = sorted(column["jobs"], key=lambda item: str(item.get("updatedAt") or ""), reverse=True)[:20]
    return {
        "summary": {"total": sum(column["count"] for column in columns.values())},
        "columns": columns,
        "generatedAt": datetime.now().isoformat(),
    }


@router.post("/application-board/move")
def move_application_board_job(payload: JobStatusRequest) -> dict:
    updated = update_job_status(payload)
    return {
        **updated,
        "board": application_crm_board(),
    }


@router.post("/status")
def update_job_status(payload: JobStatusRequest) -> dict:
    if payload.job_id not in _job_store:
        raise HTTPException(status_code=404, detail="岗位不存在")
    status = payload.status.strip()
    if status not in APPLICATION_STATUSES:
        raise HTTPException(status_code=400, detail="未知求职状态")
    job = _job_store[payload.job_id]
    previous = job.application_status
    job.application_status = status
    job.application_note = payload.note.strip()
    job.application_updated_at = datetime.now().isoformat()
    job.greeted = status in {"greeted", "applied", "interviewing"}
    entry = _append_job_history(job, "application", status, previous, job.application_note)
    _save_jobs()
    log_event("info", "job_status", f"岗位状态从 {previous} 变更为 {status}", {"jobId": job.id, "company": job.company, "entry": entry})
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
    previous = job.decision_status
    job.decision_status = status
    entry = _append_job_history(job, "decision", status, previous)
    _save_jobs()
    log_event("info", "job_decision", f"岗位决策从 {previous} 变更为 {status}", {"jobId": job.id, "company": job.company, "entry": entry})
    return {
        "job_id": payload.job_id,
        "decision_status": job.decision_status,
    }

# ---------- 删除 ----------

class BatchDeleteRequest(BaseModel):
    job_ids: list[str]


@router.post("/compare")
def compare_jobs(payload: BatchDeleteRequest) -> dict:
    job_ids = list(dict.fromkeys(payload.job_ids))
    if len(job_ids) < 2 or len(job_ids) > 5:
        raise HTTPException(status_code=400, detail="岗位对比需要选择 2-5 个岗位")
    jobs = [_job_store[job_id] for job_id in job_ids if job_id in _job_store]
    if len(jobs) != len(job_ids):
        raise HTTPException(status_code=404, detail="部分岗位不存在")
    comparison = {
        "salary": [{"id": job.id, "value": job.salary, "min": job.salary_min, "max": job.salary_max} for job in jobs],
        "jd_quality": [{"id": job.id, "value": 100 if (job.jd_text or "").strip() else 0} for job in jobs],
        "lifecycle": [{"id": job.id, "value": job.lifecycle_status} for job in jobs],
        "application": [{"id": job.id, "value": job.application_status} for job in jobs],
        "decision": [{"id": job.id, "value": job.decision_status} for job in jobs],
    }
    return {"jobs": [job.model_dump() for job in jobs], "comparison": comparison}


@router.get("/funnel")
def application_funnel() -> dict:
    jobs = _all_jobs()
    total = len(jobs)
    contacted_statuses = {"greeted", "applied", "interviewing", "rejected"}
    contacted = sum(1 for job in jobs if job.application_status in contacted_statuses)
    interviewed = sum(1 for job in jobs if job.application_status == "interviewing")
    rejected = sum(1 for job in jobs if job.application_status == "rejected")
    recommended = sum(1 for job in jobs if job.decision_status == "recommended")
    status_counts = {status: 0 for status in APPLICATION_STATUSES}
    batch_index: dict[str, dict] = {}
    for job in jobs:
        status = job.application_status if job.application_status in APPLICATION_STATUSES else "pending"
        status_counts[status] += 1
        batch_id = job.capture_batch_id or "manual"
        batch = batch_index.setdefault(batch_id, {
            "id": batch_id,
            "total": 0,
            "contacted": 0,
            "interviewing": 0,
            "recommended": 0,
            "risky": 0,
        })
        batch["total"] += 1
        if status in contacted_statuses:
            batch["contacted"] += 1
        if status == "interviewing":
            batch["interviewing"] += 1
        if job.decision_status == "recommended":
            batch["recommended"] += 1
        if job.decision_status == "risky" or job.lifecycle_status == "blacklisted":
            batch["risky"] += 1
    batches = []
    for batch in batch_index.values():
        base = batch["total"] or 1
        batch["contactRate"] = round(batch["contacted"] / base * 100)
        batch["interviewRate"] = round(batch["interviewing"] / base * 100)
        batch["recommendRate"] = round(batch["recommended"] / base * 100)
        batches.append(batch)
    batches.sort(key=lambda item: (item["interviewRate"], item["recommendRate"], item["total"]), reverse=True)
    recommendations = []
    if total and contacted == 0:
        recommendations.append("先完成第一批打招呼，系统才能形成真实转化复盘。")
    if total and recommended / total < 0.25:
        recommendations.append("推荐岗位占比较低，建议调整关键词、城市或筛选条件。")
    if contacted and interviewed == 0:
        recommendations.append("已触达但暂无面试，建议复查简历关键词和招呼语针对性。")
    if rejected > interviewed and rejected >= 2:
        recommendations.append("拒绝数高于面试数，建议降低风险岗位权重或收紧筛选条件。")
    return {
        "summary": {
            "total": total,
            "contacted": contacted,
            "interviewing": interviewed,
            "rejected": rejected,
            "recommended": recommended,
            "contactRate": round(contacted / total * 100) if total else 0,
            "interviewRate": round(interviewed / total * 100) if total else 0,
            "rejectionRate": round(rejected / total * 100) if total else 0,
        },
        "statusCounts": status_counts,
        "batches": batches,
        "recommendations": recommendations or ["当前求职漏斗健康，继续跟进推荐岗位。"],
    }

@router.delete("/batch")
def delete_batch_jobs(payload: BatchDeleteRequest) -> dict:
    """批量删除岗位。"""
    target_ids = [jid for jid in payload.job_ids if jid in _job_store]
    _archive_jobs(target_ids)
    deleted = 0
    for jid in payload.job_ids:
        if jid in _job_store:
            del _job_store[jid]
            deleted += 1
    _save_jobs()
    log_event("warning", "job_delete", f"批量删除岗位 {deleted} 个", {"jobIds": payload.job_ids, "deleted": deleted})
    return {"deleted": deleted, "total": len(_job_store)}


@router.delete("/{job_id}")
def delete_job(job_id: str) -> dict:
    """删除单个岗位。"""
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail=f"岗位 {job_id} 不存在")
    _archive_jobs([job_id])
    del _job_store[job_id]
    _save_jobs()
    log_event("warning", "job_delete", f"删除岗位 {job_id}", {"jobId": job_id})
    return {"deleted": job_id, "total": len(_job_store)}


@router.delete("")
def clear_all_jobs() -> dict:
    """清空全部岗位。"""
    count = len(_job_store)
    _archive_jobs(list(_job_store))
    _job_store.clear()
    _save_jobs()
    log_event("error", "job_delete", f"清空全部岗位 {count} 个", {"deleted": count})
    return {"deleted": count, "total": 0}


@router.post("/restore")
def restore_deleted_jobs(payload: JobIdsRequest) -> dict:
    restored = _restore_jobs(payload.job_ids)
    log_event("info", "job_restore", f"恢复岗位 {restored} 个", {"jobIds": payload.job_ids, "restored": restored})
    return {"restored": restored, "total": len(_job_store)}


@router.get("/deleted")
def list_deleted_jobs() -> dict:
    archived = _read_json(DELETED_JOBS_FILE, {})
    if not isinstance(archived, dict):
        archived = {}
    items = [
        {"id": job_id, "deletedAt": item.get("deletedAt", ""), "job": item.get("job", {})}
        for job_id, item in archived.items()
        if isinstance(item, dict)
    ]
    items.sort(key=lambda item: item.get("deletedAt", ""), reverse=True)
    return {"jobs": items, "total": len(items)}
