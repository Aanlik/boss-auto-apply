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
    }, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    running_task = find_running_task(idempotency_key)
    if running_task:
        raise HTTPException(status_code=409, detail="相同岗位的综合排序正在进行，请稍候查看任务进度")

    task = start_task(
        "ranking",
        "综合排序",
        total=len(job_list),
        payload={"job_ids": job_ids},
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
        )
        save_rankings(rankings)
        complete_task(task["id"], done=len(rankings), message=f"综合排序完成，生成 {len(rankings)} 个结果")
        return {"rankings": rankings}
    except Exception as e:
        fail_task(task["id"], str(e), "RANKING_FAILED", "检查简历、尽调报告和 AI 配置后重试")
        raise
