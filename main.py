#!/usr/bin/env python3
"""
RentBuddy - 租房小白 AI 助手

启动方式：
  GUI 模式:  python main.py
  API 模式:  python main.py --api
  指定端口:  python main.py --api --port 8080
"""
import sys
import os
import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def check_dependencies():
    """检查依赖"""
    missing = []
    try:
        import ollama
    except ImportError:
        missing.append("ollama")

    try:
        import fastapi
    except ImportError:
        missing.append("fastapi")

    try:
        import uvicorn
    except ImportError:
        missing.append("uvicorn")

    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")

    try:
        from PyPDF2 import PdfReader
    except ImportError:
        missing.append("PyPDF2")

    if missing:
        print(f"⚠️ 缺少依赖: {', '.join(missing)}")
        print("正在安装...")
        for pkg in missing:
            pkg_name = pkg.lower()
            os.system(f"{sys.executable} -m pip install {pkg_name}")
        print("✅ 依赖安装完成\n")


def check_ollama():
    """检查 Ollama 连接"""
    import requests
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            print(f"✅ Ollama 已连接，可用模型: {', '.join(models)}")
            return True
    except:
        pass
    print("⚠️ Ollama 未连接。对话功能需要 Ollama 支持。")
    print("  安装: https://ollama.ai")
    print("  拉取模型: ollama pull qwen2.5")
    return False


def run_api(host: str = "0.0.0.0", port: int = 8000):
    """启动 API 服务"""
    import uvicorn
    print(f"\n🚀 启动 API 服务: http://{host}:{port}")
    print(f"📖 API 文档: http://{host}:{port}/docs\n")
    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )


def run_gui():
    """启动 GUI 模式"""
    try:
        import tkinter
    except ImportError:
        print("❌ tkinter 未安装")
        sys.exit(1)

    from src.gui.app import RentBuddyApp
    app = RentBuddyApp()
    app.run()


def main():
    parser = argparse.ArgumentParser(description="🏠 RentBuddy - 租房小白 AI 助手")
    parser.add_argument("--api", action="store_true", help="以 API 服务模式启动")
    parser.add_argument("--host", default="0.0.0.0", help="API 服务监听地址")
    parser.add_argument("--port", type=int, default=8000, help="API 服务端口")
    parser.add_argument("--gui", action="store_true", help="以 GUI 模式启动（默认）")
    args = parser.parse_args()

    print("=" * 50)
    print("🏠 RentBuddy - 租房小白 AI 助手")
    print("=" * 50)
    print()

    check_dependencies()
    check_ollama()

    if args.api:
        run_api(args.host, args.port)
    else:
        run_gui()


if __name__ == "__main__":
    main()
