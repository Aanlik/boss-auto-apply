from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.routes.diligence import router as diligence_router
from app.routes.jobs import router as jobs_router
from app.routes.messages import router as messages_router
from app.routes.send_inbox import router as send_inbox_router
from app.routes.resumes import router as resumes_router
from app.routes.scoring import router as scoring_router
from app.routes.settings import router as settings_router

app = FastAPI(title="BOSS Workbench")

# API 路由
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(diligence_router)
app.include_router(scoring_router)
app.include_router(messages_router)
app.include_router(send_inbox_router)
app.include_router(settings_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# 静态文件服务 — 挂在 /assets 下
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
STATIC_DIR = frontend_dist

if STATIC_DIR.exists():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # SPA fallback: 非 /api 非 /assets 的路径返回 index.html
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str, request: Request):
        # 如果请求的是 API 路径但没匹配到，返回 404
        if full_path.startswith("api/"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return HTMLResponse("<h1>Frontend not built</h1>", status_code=404)
