import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.routes.assistant import router as assistant_router
from app.routes.diligence import router as diligence_router
from app.routes.feedback import router as feedback_router
from app.routes.dashboard import router as dashboard_router
from app.routes.greetings import router as greetings_router
from app.routes.help import router as help_router
from app.routes.jobs import router as jobs_router
from app.routes.maintenance import router as maintenance_router
from app.routes.resumes import router as resumes_router
from app.routes.scoring import router as scoring_router
from app.routes.settings import router as settings_router
from app.routes.workflow import router as workflow_router
from app.services.access_control import is_allowed_host
from app.services.runtime_logging import configure_runtime_logging


configure_runtime_logging()

app = FastAPI(title="boss 求职助手")


class LocalAccessGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not is_allowed_host(request.headers.get("host", "")):
            return JSONResponse(
                {"detail": "本地服务默认只允许从本机访问。如需局域网访问，请显式设置 BOSS_WORKBENCH_ALLOW_REMOTE=true。"},
                status_code=403,
            )
        return await call_next(request)


app.add_middleware(LocalAccessGuardMiddleware)

# API 路由
app.include_router(assistant_router)
app.include_router(resumes_router)
app.include_router(dashboard_router)
app.include_router(jobs_router)
app.include_router(diligence_router)
app.include_router(feedback_router)
app.include_router(scoring_router)
app.include_router(settings_router)
app.include_router(greetings_router)
app.include_router(help_router)
app.include_router(workflow_router)
app.include_router(maintenance_router)

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


# 静态文件服务
frontend_dist = Path(os.environ.get("BOSS_WORKBENCH_FRONTEND_DIST", "")).expanduser() if os.environ.get("BOSS_WORKBENCH_FRONTEND_DIST") else Path(__file__).resolve().parents[2] / "frontend" / "dist"
STATIC_DIR = frontend_dist


@app.get("/assets/{asset_path:path}")
async def serve_asset(asset_path: str):
    asset_file = (STATIC_DIR / "assets" / asset_path).resolve()
    assets_root = (STATIC_DIR / "assets").resolve()
    if assets_root in asset_file.parents and asset_file.exists() and asset_file.is_file():
        return FileResponse(asset_file)
    return JSONResponse({"detail": "Not Found"}, status_code=404)


# SPA fallback: 非 /api 非 /assets 的路径返回 index.html
@app.get("/{full_path:path}")
async def serve_spa(full_path: str, request: Request):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return HTMLResponse("<h1>Frontend not built</h1><p>Please build the frontend first.</p>", status_code=404)
