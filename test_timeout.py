"""测试 LLM 超时是否正常工作"""
import sys
import time

# 先测试 Ollama 是否在线
import requests
try:
    r = requests.get("http://localhost:11434/api/tags", timeout=3)
    print("Ollama online, models:", [m["name"] for m in r.json().get("models", [])])
except Exception as e:
    print(f"Ollama offline: {e}")
    sys.exit(0)

from src.core.llm import LLM
llm = LLM()
print(f"Model: {llm.model}")

# 测试短超时
start = time.time()
result = llm.generate("Hello", timeout=3)
elapsed = time.time() - start
print(f"Generate took {elapsed:.1f}s, result: {result[:80]}")

print("Done")
