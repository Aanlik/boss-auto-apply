from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException
import asyncio
import json
import os
from pathlib import Path
from datetime import datetime

from app.models.resume import ResumeProfile, ResumeEvaluation, JDAnalysis, ResumeOptimizationResult
from app.services.resume_parser import _extract_text_from_bytes, parse_resume_text, ai_enrich_resume
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




def _merge_profile(base: ResumeProfile, enriched: ResumeProfile | None) -> ResumeProfile:
    """合并用户编辑的 base 与 AI 补充的 enriched。
    标量字段优先用户值，列表字段（经历/教育/项目）优先 AI 结构化结果。"""
    if not enriched:
        return base
    
    return ResumeProfile(
        name=base.name or (enriched.name or ""),
        title=base.title or (enriched.title or ""),
        phone=(base.phone or getattr(enriched, "phone", None) or ""),
        email=(base.email or getattr(enriched, "email", None) or ""),
        gender=(base.gender or getattr(enriched, "gender", None) or ""),
        birth=(base.birth or getattr(enriched, "birth", None) or ""),
        location=(base.location or getattr(enriched, "location", None) or ""),
        summary=base.summary or (enriched.summary or ""),
        skills=(enriched.skills if enriched.skills else base.skills),
        target_titles=(enriched.target_titles if enriched.target_titles else base.target_titles),
        target_city=(base.target_city or getattr(enriched, "target_city", None) or ""),
        salary_expectation=(base.salary_expectation or getattr(enriched, "salary_expectation", None) or ""),
        work_experience=(enriched.work_experience if enriched.work_experience else base.work_experience),
        education=(enriched.education if enriched.education else base.education),
        projects=(enriched.projects if enriched.projects else base.projects),
    )

def _save_entry(file_id: str, entry: dict):
    """持久化简历数据到文件。写入失败时记录日志但不中断流程。"""
    import logging
    _logger = logging.getLogger("resumes")
    data = {}
    for k, v in entry.items():
        if hasattr(v, "model_dump"):
            data[k] = v.model_dump()
        elif k in ("eval", "jd", "optimization") and isinstance(v, dict):
            data[k] = v
        else:
            data[k] = v
    try:
        _store_path(file_id).write_text(json.dumps(data, ensure_ascii=False, default=lambda o: (o.model_dump() if hasattr(o, "model_dump") else (_logger.warning("_save_entry: 无法序列化的对象类型 %s，key=%s，已跳过", type(o).__name__, k) or None))))
    except OSError as e:
        _logger.error("保存简历数据失败 (%s): %s", file_id, e)
        pass  # 不中断调用方流程


def _load_entry(file_id: str) -> dict | None:
    """从文件加载简历数据。损坏文件自动清理。"""
    import logging
    _logger = logging.getLogger("resumes")
    p = _store_path(file_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        if "profile" in data and isinstance(data["profile"], dict):
            data["profile"] = ResumeProfile.model_validate(data["profile"])
        return data
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        _logger.warning("简历数据文件损坏，已自动清理: %s (%s)", file_id, e)
        try:
            p.unlink()
        except OSError:
            pass
        return None
    except OSError as e:
        _logger.warning("无法读取简历文件: %s (%s)", file_id, e)
        return None


def _load_all_entries():
    """从磁盘恢复所有简历数据。启动时调用，异常不影响服务启动。"""
    global _uploaded_files, _active_file_id
    _uploaded_files = []
    try:
        for f in sorted(STORE_DIR.glob("*.json"), key=os.path.getmtime, reverse=True):
            file_id = f.stem
            upload_path = UPLOAD_DIR / file_id
            if not upload_path.exists():
                upload_path_candidates = list(UPLOAD_DIR.glob(f"{file_id}*"))
                if upload_path_candidates:
                    upload_path = upload_path_candidates[0]
                else:
                    continue
            try:
                fstat = f.stat()
                ustats = upload_path.stat()
            except OSError:
                continue
            _uploaded_files.append({
                "id": file_id, "filename": (lambda parts: parts[-1] if len(parts) > 2 else file_id)(file_id.split("_", 2)),
                "path": str(upload_path), "size": ustats.st_size,
                "uploaded_at": datetime.fromtimestamp(fstat.st_mtime).isoformat(),
            })
        if _uploaded_files and not _active_file_id:
            _active_file_id = _uploaded_files[0]["id"]
    except Exception:
        import traceback
        traceback.print_exc()


try:
    _load_all_entries()
except Exception:
    import traceback
    traceback.print_exc()


def _empty_active_resume() -> dict:
    return {"profile": None, "raw_text": "", "file_id": "", "eval": None, "jd": None, "optimization": None, "parse_status": None}


def _profile_payload(entry: dict) -> dict | None:
    profile = entry.get("profile") if isinstance(entry, dict) else None
    if not profile:
        return None
    return profile.model_dump() if hasattr(profile, "model_dump") else profile


# ── 解析 ──

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

def _sanitize_filename(filename: str) -> str:
    """移除路径遍历和非法字符。"""
    import re as _re
    safe = _re.sub(r'[^\u4e00-\u9fff\w ._\-]', '_', filename)
    safe = safe.replace('..', '_').replace('/', '_').replace('\\', '_')
    if len(safe) > 100:
        name, dot, ext = safe.rpartition('.')
        name = name[:80]
        safe = f'{name}.{ext}' if dot else name
    return safe.strip() or 'resume'

@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail=f"文件过大，最大支持 {MAX_UPLOAD_SIZE // 1024 // 1024} MB")
    filename = _sanitize_filename(file.filename or "")
    if len(data) < 10:
        raise HTTPException(status_code=400, detail="文件为空或内容过少，请上传有效的简历文件")
    try:
        import asyncio as _aio
        loop = _aio.get_event_loop()
        # 同步解析放入线程池，不阻塞事件循环（其他请求可并发处理）
        raw_text = await loop.run_in_executor(None, _extract_text_from_bytes, data, filename)
        profile = await loop.run_in_executor(None, parse_resume_text, raw_text)

        import uuid as _uuid
        file_id = datetime.now().strftime("%Y%m%d%H%M%S%f") + "_" + _uuid.uuid4().hex[:6] + "_" + filename
        file_path = UPLOAD_DIR / file_id
        with open(file_path, "wb") as f:
            f.write(data)

        # 检查 AI 是否已配置，未配置则直接标记完成，避免前端轮询假死
        _ai_available = False
        try:
            from app.services.ai_client import get_client
            get_client()
            _ai_available = True
        except Exception:
            pass

        initial_status = "pending_ai" if _ai_available else "completed"

        entry = {"profile": profile, "raw_text": raw_text, "eval": None, "jd": None, "parse_status": initial_status}
        _save_entry(file_id, entry)

        global _active_file_id
        _active_file_id = file_id

        # 附件显示名：原文件名 + 时间戳
        ts_label = datetime.now().strftime("%Y%m%d%H%M%S")
        name_part, dot, ext = filename.rpartition(".")
        display_name = f"{name_part}_{ts_label}.{ext}" if dot else f"{name_part}_{ts_label}"
        _uploaded_files.insert(0, {
            "id": file_id, "filename": display_name, "path": str(file_path),
            "size": len(data), "uploaded_at": datetime.now().isoformat(),
        })
        while len(_uploaded_files) > 20:
            old = _uploaded_files.pop()
            try: os.remove(old["path"])
            except OSError: pass
            try: os.remove(_store_path(old["id"]))
            except OSError: pass

        # 后台异步 AI 补充解析（仅在 AI 已配置时启动）
        import asyncio
        import logging as _bg_log
        _bg_logger = _bg_log.getLogger("resumes")

        async def _bg_enrich():
            try:
                loop = asyncio.get_event_loop()
                enriched = await loop.run_in_executor(None, ai_enrich_resume, raw_text, ["全部字段"])
                if enriched:
                    # 读取磁盘最新数据（可能已被用户编辑过）
                    current = _load_entry(file_id) or {}
                    # 用户已手动编辑过 → 不再覆盖
                    if current.get("user_edited"):
                        _bg_logger.info("用户已编辑简历，跳过 AI 自动补充: %s", file_id)
                        current["parse_status"] = "ai_enriched"
                        _save_entry(file_id, current)
                        return
                    base = current.get("profile") or profile
                    merged_profile = _merge_profile(base, enriched)
                    current["profile"] = merged_profile
                    current["parse_status"] = "ai_enriched"
                    _save_entry(file_id, current)
                    _bg_logger.info("AI 补充解析完成: %s", file_id)
            except Exception as e:
                _bg_logger.warning("AI 补充解析失败 (%s): %s", file_id, e)
                current = _load_entry(file_id) or {}
                current["parse_status"] = f"ai_failed: {str(e)[:80]}"
                _save_entry(file_id, current)

        # 仅在 AI 可用时启动后台补充解析
        if _ai_available:
            asyncio.create_task(_bg_enrich())

        return {"profile": profile.model_dump(), "raw_text": raw_text, "file_id": file_id, "parse_status": initial_status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {e}")


# ── 加载 ──
@router.post("/load/{file_id}")
def load_resume(file_id: str):
    global _active_file_id
    if ".." in file_id or "/" in file_id or "\\" in file_id:
        raise HTTPException(status_code=400, detail="无效的文件 ID")
    entry = _load_entry(file_id)
    if not entry or not _profile_payload(entry):
        raise HTTPException(status_code=404, detail="简历不存在")
    _active_file_id = file_id
    return {
        "profile": _profile_payload(entry),
        "raw_text": entry.get("raw_text", ""),
        "file_id": file_id,
        "eval": entry.get("eval"),
        "jd": entry.get("jd"),
        "optimization": entry.get("optimization"),
        "parse_status": entry.get("parse_status", "completed"),
        "user_edited": entry.get("user_edited", False),
    }


# ── 活跃简历 ──
@router.get("/active")
def get_active():
    if not _active_file_id:
        return _empty_active_resume()
    entry = _load_entry(_active_file_id)
    profile = _profile_payload(entry or {})
    if not entry or not profile:
        return _empty_active_resume()
    return {
        "profile": profile,
        "raw_text": entry.get("raw_text", ""),
        "file_id": _active_file_id,
        "eval": entry.get("eval"),
        "jd": entry.get("jd"),
        "optimization": entry.get("optimization"),
        "parse_status": entry.get("parse_status", "completed"),
        "user_edited": entry.get("user_edited", False),
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
        loop = asyncio.get_event_loop()
        evaluation = await loop.run_in_executor(None, evaluate_resume, profile, resume_text, chat_history)
        _update_active("eval", evaluation.model_dump())
        return evaluation
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 评估失败: {e}")


def _update_active(key: str, value):
    """原子更新活跃简历的某个字段。读取-合并-写入，最多重试 3 次。"""
    if not _active_file_id:
        return
    for attempt in range(3):
        entry = _load_entry(_active_file_id) or {}
        entry[key] = value
        try:
            _save_entry(_active_file_id, entry)
            return
        except Exception:
            if attempt == 2:
                import logging
                logging.getLogger("resumes").error("_update_active 写入失败 (%s.%s)，已重试 3 次", _active_file_id, key)
            continue


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
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(None, analyze_jd, job_title, company, jd_text, chat_history)
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
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: ai_optimize(profile=profile, evaluation=evaluation, jd_analysis=jd_analysis,
                           job_title=job_title, company=company, jd_text=jd_text, chat_history=chat_history))
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
        pdf_bytes = gen_pdf(profile, optimization, company, job_title, payload.get("template", "modern"))
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
        "evaluate": f"你是资深 HR，刚评估了 {profile_name} 的简历。上下文：{_json.dumps(context, ensure_ascii=False)[:4000]} 请专业回答。中文。",
        "analyze": f"你是资深技术招聘经理，刚分析了 JD。上下文：{_json.dumps(context, ensure_ascii=False)[:4000]} 中文。",
        "optimize": f"你是顶级简历顾问，刚为 {profile_name} 生成了优化方案。上下文：{_json.dumps(context, ensure_ascii=False)[:4000]} 中文。",
    }
    system = prompts.get(step, "你是专业求职顾问。中文回答。")
    try:
        client = get_client()
        model = get_model()
        full_msgs = [{"role": "system", "content": system}]
        for m in messages[-20:]:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                full_msgs.append({"role": m["role"], "content": m["content"]})
        def _do_chat():
            resp = client.chat.completions.create(model=model, messages=full_msgs, temperature=0.7)
            return resp.choices[0].message.content
        reply = await asyncio.get_event_loop().run_in_executor(None, _do_chat)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 对话失败: {e}")



# ── 聊天持久化 ──
@router.post("/chat/save")
def save_chat(payload: dict):
    """保存活跃简历的聊天消息到磁盘。{chat_key: string, messages: [{role, content}]}"""
    if not _active_file_id:
        raise HTTPException(status_code=400, detail="没有活跃的简历文件")
    chat_key = payload.get("chat_key", "")
    messages = payload.get("messages")
    if not chat_key:
        raise HTTPException(status_code=400, detail="缺少 chat_key")
    
    entry = _load_entry(_active_file_id) or {}
    chats = entry.get("chats") or {}
    if messages is None:
        chats.pop(chat_key, None)
    else:
        chats[chat_key] = messages
    entry["chats"] = chats
    _save_entry(_active_file_id, entry)
    return {"saved": chat_key}

@router.get("/chat/load")
def load_chat(chat_key: str = ""):
    """加载活跃简历的聊天消息。?chat_key=xxx"""
    if not _active_file_id:
        return {"chats": {}, "active": {}}
    entry = _load_entry(_active_file_id) or {}
    chats = entry.get("chats") or {}
    if chat_key:
        return {"chats": chats, "active": chats.get(chat_key) or []}
    return {"chats": chats, "active": []}

# ── 附件管理 ──
@router.get("/files")
def list_files():
    return {"files": list(_uploaded_files)}


@router.delete("/files/{file_id}")
def delete_file(file_id: str):
    global _uploaded_files, _active_file_id
    if ".." in file_id or "/" in file_id or "\\" in file_id:
        raise HTTPException(status_code=400, detail="无效的文件 ID")
    for i, f in enumerate(_uploaded_files):
        if f["id"] == file_id:
            try: os.remove(f["path"])
            except OSError: pass
            try: os.remove(_store_path(file_id))
            except OSError: pass
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
    file_id = payload.get("file_id") or _active_file_id
    if not file_id:
        raise HTTPException(status_code=400, detail="没有活跃的简历文件，请先上传并解析简历")
    profile = ResumeProfile.model_validate(profile_data)
    entry = _load_entry(file_id) or {}
    entry["profile"] = profile
    entry["user_edited"] = True
    _save_entry(file_id, entry)
    return {"updated": True}


# ── 重新 AI 补充解析 ──
@router.post("/re-enrich")
async def re_enrich_resume():
    """手动触发 AI 补充解析（当自动补充不完整时）。"""
    import asyncio
    import logging
    _logger = logging.getLogger("resumes")
    global _active_file_id

    if not _active_file_id:
        raise HTTPException(status_code=400, detail="请先上传简历")

    entry = _load_entry(_active_file_id)
    if not entry:
        raise HTTPException(status_code=404, detail="简历不存在")

    raw_text = entry.get("raw_text", "")
    if not raw_text:
        raise HTTPException(status_code=400, detail="简历原文缺失，请重新上传")

    profile = entry.get("profile")
    file_id = _active_file_id

    # 先标记为解析中
    entry["parse_status"] = "pending_ai"
    _save_entry(file_id, entry)

    async def _re_enrich():
        try:
            loop = asyncio.get_event_loop()
            enriched = await loop.run_in_executor(None, ai_enrich_resume, raw_text, ["全部字段"])
            if enriched:
                current = _load_entry(file_id) or {}
                base = current.get("profile") or profile
                merged_profile = _merge_profile(base, enriched)
                current["profile"] = merged_profile
                current["parse_status"] = "ai_enriched"
                _save_entry(file_id, current)
                _logger.info("手动 AI 补充解析完成: %s", file_id)
        except Exception as e:
            _logger.warning("手动 AI 补充解析失败 (%s): %s", file_id, e)
            current = _load_entry(file_id) or {}
            current["parse_status"] = f"ai_failed: {str(e)[:80]}"
            _save_entry(file_id, current)

    asyncio.create_task(_re_enrich())
    return {"status": "ok", "message": "AI 补充解析已启动", "file_id": file_id}
