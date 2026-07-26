from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.routes.diligence import router as diligence_router
from app.routes.greetings import router as greetings_router
from app.routes.jobs import router as jobs_router
from app.routes.resumes import router as resumes_router
from app.routes.scoring import router as scoring_router
from app.routes.settings import router as settings_router
from app.routes.workflow import router as workflow_router

app = FastAPI(title="BOSS Workbench")

# API 路由
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(diligence_router)
app.include_router(scoring_router)
app.include_router(settings_router)
app.include_router(greetings_router)
app.include_router(workflow_router)

# ── 禁用静态文件缓存（开发阶段） ──
from starlette.middleware.base import BaseHTTPMiddleware

class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheStaticMiddleware)



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
