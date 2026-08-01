from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Response
from app.services.scoring import (
    RANKING_SETTINGS_FILE,
    get_ranking_weight_templates,
    load_ranking_weights,
    rank_jobs_ai,
    save_ranking_weights,
)
from app.services.workflow_persistence import load_rankings, save_rankings
from app.services.workflow_tasks import complete_task, fail_task, find_running_task, start_task, update_task

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.get("/rankings")
def get_rankings() -> dict:
    return {"rankings": load_rankings()}


@router.get("/rankings/export")
def export_rankings(format: str = "json"):
    rankings = load_rankings()
    if format == "json":
        return {"rankings": rankings, "total": len(rankings), "exportedAt": datetime.now().isoformat()}
    if format == "csv":
        output = io.StringIO()
        fields = [
            "jobId",
            "jobTitle",
            "company",
            "salary",
            "companyScore",
            "matchScore",
            "compositeScore",
            "recommendation",
            "reason",
        ]
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rankings)
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="rankings.csv"'},
        )
    raise HTTPException(status_code=400, detail="导出格式必须是 json/csv")


@router.get("/weights")
def get_ranking_weights() -> dict:
    return {"weights": load_ranking_weights()}


@router.get("/weights/templates")
def get_weight_templates() -> dict:
    return {"templates": get_ranking_weight_templates()}


@router.post("/weights")
def set_ranking_weights(payload: dict) -> dict:
    return {"weights": save_ranking_weights(payload)}


@router.post("/rank")
async def rank_jobs_endpoint(payload: dict) -> dict:
    """
    综合排序
    输入: { job_ids, resume, diligence_reports }
    输出: { rankings: [...] }
    """
    job_ids = payload.get("job_ids", [])
    resume = payload.get("resume", {})
    diligence_reports = payload.get("diligence_reports", {})
    continue_existing = bool(payload.get("continue_existing"))
    refresh_ai_matches = bool(payload.get("refresh_ai_matches"))

    if not job_ids:
        raise HTTPException(status_code=400, detail="没有岗位 ID")

    if not resume:
        raise HTTPException(status_code=400, detail="缺少简历数据")

    # 从岗位池中获取岗位详情
    from app.routes.jobs import _all_jobs
    all_jobs = _all_jobs()
    jobs_map = {j.id: j.model_dump() for j in all_jobs if hasattr(j, 'id')}
    
    # 兼容 dict 和 Pydantic model
    if not jobs_map:
        # 回退：尝试直接使用 id 列表从 _all_jobs 的简化版
        job_list = []
        for j in all_jobs:
            try:
                d = j.model_dump() if hasattr(j, 'model_dump') else j
                if d.get("id") in job_ids:
                    job_list.append(d)
            except Exception:
                if isinstance(j, dict) and j.get("id") in job_ids:
                    job_list.append(j)
    else:
        job_list = [jobs_map[jid] for jid in job_ids if jid in jobs_map]

    if not job_list:
        # 回退: 使用 payload 中的 simplified 数据
        raise HTTPException(status_code=404, detail="无法找到岗位详情")

    idempotency_key = hashlib.sha256(json.dumps({
        "job_ids": sorted(str(item) for item in job_ids),
        "resume": resume,
        "diligence_reports": diligence_reports,
        "weights": payload.get("weights") or {},
        "continue_existing": continue_existing,
        "refresh_ai_matches": refresh_ai_matches,
    }, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    running_task = find_running_task(idempotency_key)
    if running_task:
        raise HTTPException(status_code=409, detail="相同岗位的综合排序正在进行，请稍候查看任务进度")

    task = start_task(
        "ranking",
        "继续综合排序" if continue_existing else "综合排序",
        total=len(job_list),
        payload={"job_ids": job_ids, "continue_existing": continue_existing, "refresh_ai_matches": refresh_ai_matches},
        idempotency_key=idempotency_key,
    )
    try:
        async def on_progress(done: int, total: int, result: dict) -> None:
            update_task(
                task["id"],
                done=done,
                message=f"正在分析 {done}/{total}: {result.get('company', '')} · {result.get('jobTitle', '')}",
            )

        rankings = await rank_jobs_ai(
            job_list,
            resume,
            diligence_reports,
            payload.get("weights"),
            progress_callback=on_progress,
            refresh_ai_matches=refresh_ai_matches,
        )
        failed_rankings = [
            {
                "jobId": str(item.get("jobId") or ""),
                "reason": str(item.get("failureReason") or "unknown"),
            }
            for item in rankings
            if isinstance(item, dict) and item.get("matchStatus") == "failed"
        ]
        completed_rankings = [
            item for item in rankings
            if isinstance(item, dict) and item.get("matchStatus") != "failed"
        ]
        if continue_existing:
            # 继续排序只更新本次成功生成的岗位，保留此前已完成的结果。
            # 这样 AI 配置或网络恢复后，用户无需把全部岗位再跑一遍。
            merged_by_job_id = {
                str(item.get("jobId")): item
                for item in load_rankings()
                if isinstance(item, dict) and item.get("jobId") and item.get("matchStatus") != "failed" and "匹配度分析待AI配置后更新" not in str(item.get("reason") or "")
            }
            merged_by_job_id.update({
                str(item.get("jobId")): item
                for item in completed_rankings
                if isinstance(item, dict) and item.get("jobId")
            })
            persisted_rankings = sorted(
                merged_by_job_id.values(),
                key=lambda item: float(item.get("compositeScore") or 0),
                reverse=True,
            )
        else:
            persisted_rankings = completed_rankings

        save_rankings(persisted_rankings)
        successful_count = len(completed_rankings)
        if continue_existing:
            message = f"继续排序完成，新增 {successful_count} 个结果，累计 {len(persisted_rankings)} 个"
        else:
            message = f"综合排序完成，生成 {successful_count} 个结果"
        if failed_rankings:
            message += f"；{len(failed_rankings)} 个岗位待重试"
        complete_task(task["id"], done=successful_count, message=message)
        return {
            "rankings": persisted_rankings,
            "continued": continue_existing,
            "newlyRanked": successful_count,
            "failedCount": len(failed_rankings),
            "failedRankings": failed_rankings,
        }
    except Exception as e:
        fail_task(task["id"], str(e), "RANKING_FAILED", "检查简历、尽调报告和 AI 配置后重试")
        raise
