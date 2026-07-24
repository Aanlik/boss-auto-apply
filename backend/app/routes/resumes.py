from fastapi import APIRouter, UploadFile, File, HTTPException
import json
import os
from pathlib import Path
from datetime import datetime

from app.models.resume import ResumeProfile, ResumeEvaluation, JDAnalysis, ResumeOptimizationResult
from app.services.resume_parser import parse_resume_bytes, _extract_text_from_bytes, parse_resume_text
from app.services.resume_evaluator import evaluate_resume
from app.services.jd_analyzer import analyze_jd
from app.services.resume_optimizer import optimize_resume as ai_optimize

router = APIRouter(prefix="/api/resumes", tags=["resumes"])

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
STORE_DIR = DATA_DIR / "resumes"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STORE_DIR.mkdir(parents=True, exist_ok=True)

_uploaded_files: list[dict] = []
_active_file_id: str = ""


def _store_path(file_id: str) -> Path:
    return STORE_DIR / f"{file_id}.json"


def _save_entry(file_id: str, entry: dict):
    """持久化简历数据到文件。"""
    data = {}
    for k, v in entry.items():
        if k == "profile" and hasattr(v, "model_dump"):
            data[k] = v.model_dump()
        elif k in ("eval", "jd") and isinstance(v, dict):
            data[k] = v
        else:
            data[k] = v
    _store_path(file_id).write_text(json.dumps(data, ensure_ascii=False, default=str))


def _load_entry(file_id: str) -> dict | None:
    """从文件加载简历数据。"""
    p = _store_path(file_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        if "profile" in data and isinstance(data["profile"], dict):
            data["profile"] = ResumeProfile.model_validate(data["profile"])
        return data
    except Exception:
        return None


def _load_all_entries():
    """从磁盘恢复所有简历数据。"""
    global _uploaded_files, _active_file_id
    _uploaded_files = []
    for f in sorted(STORE_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
        file_id = f.stem
        # 对应的上传文件是否存在
        upload_path = UPLOAD_DIR / file_id
        if not upload_path.exists():
            upload_path_candidates = list(UPLOAD_DIR.glob(f"{file_id}*"))
            if upload_path_candidates:
                upload_path = upload_path_candidates[0]
            else:
                continue
        _uploaded_files.append({
            "id": file_id, "filename": file_id.split("_", 1)[-1] if "_" in file_id else file_id,
            "path": str(upload_path), "size": upload_path.stat().st_size,
            "uploaded_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    if _uploaded_files and not _active_file_id:
        _active_file_id = _uploaded_files[0]["id"]


# 启动时恢复数据
_load_all_entries()


# ── 解析 ──
@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    data = await file.read()
    filename = file.filename or ""
    try:
        raw_text = _extract_text_from_bytes(data, filename)
        profile = parse_resume_text(raw_text)

        file_id = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + filename
        file_path = UPLOAD_DIR / file_id
        with open(file_path, "wb") as f:
            f.write(data)

        entry = {"profile": profile, "raw_text": raw_text, "eval": None, "jd": None}
        _save_entry(file_id, entry)

        global _active_file_id
        _active_file_id = file_id

        _uploaded_files.insert(0, {
            "id": file_id, "filename": filename, "path": str(file_path),
            "size": len(data), "uploaded_at": datetime.now().isoformat(),
        })
        while len(_uploaded_files) > 20:
            old = _uploaded_files.pop()
            try: os.remove(old["path"])
            except: pass
            try: os.remove(_store_path(old["id"]))
            except: pass

        return {"profile": profile.model_dump(), "raw_text": raw_text, "file_id": file_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {e}")


# ── 加载 ──
@router.post("/load/{file_id}")
def load_resume(file_id: str):
    global _active_file_id
    entry = _load_entry(file_id)
    if not entry:
        raise HTTPException(status_code=404, detail="简历不存在")
    _active_file_id = file_id
    return {
        "profile": entry["profile"].model_dump() if hasattr(entry["profile"], "model_dump") else entry["profile"],
        "raw_text": entry.get("raw_text", ""),
        "file_id": file_id,
        "eval": entry.get("eval"),
        "jd": entry.get("jd"),
        "optimization": entry.get("optimization"),
    }


# ── 活跃简历 ──
@router.get("/active")
def get_active():
    if not _active_file_id:
        return {"profile": None, "raw_text": "", "file_id": "", "eval": None, "jd": None, "optimization": None}
    entry = _load_entry(_active_file_id)
    if not entry:
        return {"profile": None, "raw_text": "", "file_id": "", "eval": None, "jd": None, "optimization": None}
    return {
        "profile": entry["profile"].model_dump() if hasattr(entry["profile"], "model_dump") else entry["profile"],
        "raw_text": entry.get("raw_text", ""),
        "file_id": _active_file_id,
        "eval": entry.get("eval"),
        "jd": entry.get("jd"),
        "optimization": entry.get("optimization"),
        "optimization": entry.get("optimization"),
    }


# ── 评估 ──
@router.post("/evaluate", response_model=ResumeEvaluation)
async def evaluate_resume_endpoint(payload: dict) -> ResumeEvaluation:
    profile_data = payload.get("profile")
    if not profile_data and _active_file_id:
        entry = _load_entry(_active_file_id)
        if entry:
            profile_data = entry.get("profile")
    if not profile_data:
        raise HTTPException(status_code=400, detail="请先上传并解析简历")

    profile = ResumeProfile.model_validate(profile_data) if isinstance(profile_data, dict) else profile_data
    resume_text = payload.get("resume_text", "")
    chat_history = payload.get("chat_history") or []

    try:
        evaluation = evaluate_resume(profile, resume_text, chat_history)
        if _active_file_id:
            entry = _load_entry(_active_file_id) or {}
            entry["eval"] = evaluation.model_dump()
            _save_entry(_active_file_id, {"profile": profile, **{k: v for k, v in entry.items() if k != "profile"}})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 评估失败: {e}")
    # Re-save with eval
    _update_active("eval", evaluation.model_dump())
    return evaluation


def _update_active(key: str, value):
    if not _active_file_id:
        return
    entry = _load_entry(_active_file_id) or {}
    entry[key] = value
    _save_entry(_active_file_id, entry)


# ── JD 分析 ──
@router.post("/analyze-jd", response_model=JDAnalysis)
async def analyze_jd_endpoint(payload: dict) -> JDAnalysis:
    job_title = payload.get("title", "")
    company = payload.get("company", "")
    jd_text = payload.get("jd_text", "")
    if not jd_text:
        raise HTTPException(status_code=400, detail="请先选择目标岗位")
    chat_history = payload.get("chat_history") or []
    try:
        analysis = analyze_jd(job_title, company, jd_text, chat_history)
        _update_active("jd", analysis.model_dump())
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {e}")


# ── 优化 ──
@router.post("/optimize", response_model=ResumeOptimizationResult)
async def optimize_resume_endpoint(payload: dict) -> ResumeOptimizationResult:
    entry = _load_entry(_active_file_id) if _active_file_id else {}
    profile_data = payload.get("profile") or entry.get("profile")
    eval_data = payload.get("evaluation") or entry.get("eval")
    jd_data = payload.get("jd_analysis") or entry.get("jd")
    target_job = payload.get("target_job", {})
    if not profile_data:
        raise HTTPException(status_code=400, detail="请先上传并解析简历")

    profile = ResumeProfile.model_validate(profile_data) if isinstance(profile_data, dict) else profile_data
    evaluation = ResumeEvaluation.model_validate(eval_data) if eval_data else None
    jd_analysis = JDAnalysis.model_validate(jd_data) if jd_data else None

    job_title = target_job.get("title", "") if isinstance(target_job, dict) else getattr(target_job, "title", "")
    company = target_job.get("company", "") if isinstance(target_job, dict) else getattr(target_job, "company", "")
    jd_text = target_job.get("jd_text", "") if isinstance(target_job, dict) else getattr(target_job, "jd_text", "")
    chat_history = payload.get("chat_history") or []

    try:
        result = ai_optimize(profile=profile, evaluation=evaluation, jd_analysis=jd_analysis,
                           job_title=job_title, company=company, jd_text=jd_text, chat_history=chat_history)
        _update_active("optimization", result.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 优化失败: {e}")


# ── PDF 导出 ──
@router.post("/export-pdf")
async def export_resume_pdf(payload: dict):
    from fastapi.responses import Response
    from urllib.parse import quote
    from app.services.resume_pdf_exporter import export_resume_pdf as gen_pdf

    entry = _load_entry(_active_file_id) if _active_file_id else {}
    profile_data = payload.get("profile") or entry.get("profile")
    optimization = payload.get("optimization", {})
    company = payload.get("company", "公司")
    job_title = payload.get("job_title", "岗位")
    if not profile_data:
        raise HTTPException(status_code=400, detail="请先上传并解析简历")

    profile = ResumeProfile.model_validate(profile_data) if isinstance(profile_data, dict) else profile_data
    try:
        pdf_bytes = gen_pdf(profile, optimization, company, job_title)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {e}")

    safe_name = f"{company}-{job_title}".replace("/", "-").replace("\\", "-").replace(":", "-")
    encoded = quote(f"{safe_name}.pdf")
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"})


# ── AI 对话 ──
@router.post("/chat")
async def chat_with_ai(payload: dict):
    from app.services.ai_client import get_client, get_model
    import json as _json
    step = payload.get("step", "")
    context = payload.get("context", {})
    messages = payload.get("messages", [])
    profile_name = payload.get("profile_name", "求职者")
    if not step or not messages:
        raise HTTPException(status_code=400, detail="缺少 step 或 messages")
    prompts = {
        "evaluate": f"你是资深 HR，刚评估了 {profile_name} 的简历。上下文：{_json.dumps(context, ensure_ascii=False)[:2000]} 请专业回答。中文。",
        "analyze": f"你是资深技术招聘经理，刚分析了 JD。上下文：{_json.dumps(context, ensure_ascii=False)[:2000]} 中文。",
        "optimize": f"你是顶级简历顾问，刚为 {profile_name} 生成了优化方案。上下文：{_json.dumps(context, ensure_ascii=False)[:2000]} 中文。",
    }
    system = prompts.get(step, "你是专业求职顾问。中文回答。")
    try:
        client = get_client()
        full_msgs = [{"role": "system", "content": system}]
        for m in messages[-20:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                full_msgs.append({"role": m["role"], "content": m["content"]})
        resp = client.chat.completions.create(model=get_model(), messages=full_msgs, temperature=0.7)
        return {"reply": resp.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 对话失败: {e}")


# ── 附件管理 ──
@router.get("/files")
def list_files():
    return {"files": list(_uploaded_files)}


@router.delete("/files/{file_id}")
def delete_file(file_id: str):
    global _uploaded_files, _active_file_id
    for i, f in enumerate(_uploaded_files):
        if f["id"] == file_id:
            try: os.remove(f["path"])
            except: pass
            try: os.remove(_store_path(file_id))
            except: pass
            _uploaded_files.pop(i)
            if _active_file_id == file_id:
                _active_file_id = _uploaded_files[0]["id"] if _uploaded_files else ""
            return {"deleted": file_id}
    raise HTTPException(status_code=404, detail="文件不存在")


# ── 更新简历 ──
@router.put("/profile")
def update_profile(payload: dict):
    profile_data = payload.get("profile")
    if not profile_data:
        raise HTTPException(status_code=400, detail="缺少 profile 数据")
    profile = ResumeProfile.model_validate(profile_data)
    if _active_file_id:
        entry = _load_entry(_active_file_id) or {}
        entry["profile"] = profile
        _save_entry(_active_file_id, entry)
    return {"updated": True}
