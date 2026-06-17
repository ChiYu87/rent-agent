"""RentBuddy API 服务

FastAPI 应用入口，整合所有路由，同时 serve 前端静态文件。
启动方式：uvicorn api.app:app --host 0.0.0.0 --port 8000
"""
import sys
import os
import io

# Windows GBK 终端兼容：强制 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 确保项目根目录在 sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import chat, contract, tools
from src.utils.db import Database
from src.core.llm import LLM
from src.core.embedder import Embedder

app = FastAPI(
    title="RentBuddy API",
    description="🏠 租房小白 AI 助手 - 降低信息差 · 标准化流程 · 风险预警",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由（优先匹配）
app.include_router(chat.router, prefix="/api")
app.include_router(contract.router, prefix="/api")
app.include_router(tools.router, prefix="/api")


@app.get("/api/health")
async def health():
    """健康检查"""
    llm = LLM()
    db = Database()
    embedder = Embedder()
    return {
        "status": "ok",
        "ollama": llm.check_connection(),
        "llm_model": llm.model,
        "embed_model": embedder.model,
        "db_stats": db.get_stats(),
    }


# ==================== 前端静态文件 ====================
# 必须放在 API 路由之后，避免 /api 路径被静态文件拦截

FRONTEND_DIST = os.path.join(ROOT, "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    # 静态资源（JS/CSS/图片）
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    # favicon 等
    for static_file in ["vite.svg", "favicon.ico"]:
        fp = os.path.join(FRONTEND_DIST, static_file)
        if os.path.isfile(fp):
            app.mount(f"/{static_file}", StaticFiles(directory=FRONTEND_DIST, html=True), name=static_file)
            break

    # SPA fallback：所有未匹配路径返回 index.html
    @app.get("/{path:path}")
    async def serve_spa(request: Request, path: str):
        """SPA 路由：未匹配的路径返回 index.html，交给前端 router 处理"""
        file_path = os.path.join(FRONTEND_DIST, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))


@app.on_event("startup")
async def startup():
    """启动时检查依赖"""
    print("=" * 50)
    print("🏠 RentBuddy 服务启动中...")
    print("=" * 50)

    # 检查 Ollama
    llm = LLM()
    if llm.check_connection():
        models = llm.list_models()
        print(f"✅ Ollama 已连接 | 模型: {', '.join(models)}")
    else:
        print("⚠️ Ollama 未连接，对话功能不可用")

    # 检查 Embedding
    embedder = Embedder()
    print(f"✅ Embedding 模型: {embedder.model}")

    # 检查数据库
    db = Database()
    stats = db.get_stats()
    print(f"✅ 数据库就绪 | 用户: {stats['users']} | 消息: {stats['messages']}")

    # 检查前端
    if os.path.isdir(FRONTEND_DIST):
        print(f"✅ 前端静态文件就绪")
    else:
        print("⚠️ 前端未构建，请运行: cd frontend && npm run build")

    print()
    print("  H5 界面: http://localhost:8080")
    print("  API 文档: http://localhost:8080/docs")
    print("  ReDoc:    http://localhost:8080/redoc")
    print()
