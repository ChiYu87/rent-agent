#!/usr/bin/env python3
"""
RentBuddy - 租房小白 AI 助手
启动入口
"""
import sys
import os

# 确保项目根目录在 sys.path 中
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def check_dependencies():
    """检查依赖"""
    missing = []

    # 检查 ollama 包
    try:
        import ollama
    except ImportError:
        missing.append("ollama (pip install ollama)")

    # 检查 Pillow
    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow (pip install Pillow)")

    # 检查 PyPDF2
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        missing.append("PyPDF2 (pip install PyPDF2)")

    if missing:
        print("⚠️ 缺少以下依赖，正在尝试安装...")
        for pkg in missing:
            pkg_name = pkg.split(" ")[0].lower()
            os.system(f"{sys.executable} -m pip install {pkg_name}")

    # tkinter 通常随 Python 自带
    try:
        import tkinter
    except ImportError:
        print("❌ tkinter 未安装，请通过系统包管理器安装")
        print("  Ubuntu/Debian: sudo apt-get install python3-tk")
        print("  Fedora: sudo dnf install python3-tkinter")
        print("  macOS: brew install python-tk")
        sys.exit(1)


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

    print("⚠️ Ollama 未连接。")
    print("  请确保 Ollama 已启动: https://ollama.ai")
    print("  并拉取模型: ollama pull qwen2.5")
    print("  程序仍可启动，但对话功能需 Ollama 支持。")
    return False


def main():
    print("=" * 50)
    print("🏠 RentBuddy - 租房小白 AI 助手")
    print("=" * 50)
    print()

    check_dependencies()
    check_ollama()

    from src.gui.app import RentBuddyApp
    app = RentBuddyApp()
    app.run()


if __name__ == "__main__":
    main()
