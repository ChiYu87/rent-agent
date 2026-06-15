"""RentBuddy API 服务

FastAPI 应用入口，整合所有路由。
启动方式：uvicorn api.app:app --host 0.0.0.0 --port 8000
"""
import sys
import os

# 确保项目根目录在 sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import chat, contract, tools
from src.utils.db import Database
from src.core.llm import LLM
from src.core.embedder import Embedder

app = FastAPI(
    title="RentBuddy API",
    description="🏠 租房小白 AI 助手 - 降低信息差 · 标准化流程 · 风险预警",
    version="0.1.0",
)

# CORS：允许小程序/H5/桌面端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api")
app.include_router(contract.router, prefix="/api")
app.include_router(tools.router, prefix="/api")


@app.on_event("startup")
async def startup():
    """启动时检查依赖"""
    print("=" * 50)
    print("🏠 RentBuddy API 服务启动中...")
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

    print()
    print("📖 API 文档: http://localhost:8000/docs")
    print("📖 ReDoc: http://localhost:8000/redoc")
    print()


@app.get("/")
async def root():
    return {
        "name": "RentBuddy API",
        "version": "0.1.0",
        "description": "租房小白 AI 助手",
        "docs": "/docs",
    }


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
