"""Ollama LLM 封装 - 支持流式输出"""
import json
import requests
from ..utils.config import Config


class LLM:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        cfg = Config()
        self.base_url = cfg.get("llm.base_url", "http://localhost:11434")
        self.model = cfg.get("llm.model", "")
        self.temperature = cfg.get("llm.temperature", 0.7)
        self.max_tokens = cfg.get("llm.max_tokens", 2048)
        self._override_timeout = None

        # 自动选择可用模型
        if not self.model:
            self.model = self._auto_pick_model()

    def _auto_pick_model(self) -> str:
        """自动从已安装模型中选一个聊天模型"""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                # 排除 embedding 模型
                embed_keywords = ["embed", "minilm"]
                chat_models = [m for m in models if not any(k in m.lower() for k in embed_keywords)]
                if chat_models:
                    return chat_models[0]
                if models:
                    return models[0]
        except:
            pass
        return "qwen2.5"

    def chat(self, messages: list[dict], stream: bool = False) -> str:
        """同步对话"""
        url = f"{self.base_url}/api/chat"
        # 超时: (connect_timeout, read_timeout)
        if self._override_timeout:
            req_timeout = (3, self._override_timeout)
        else:
            req_timeout = (5, 120)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=req_timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except requests.exceptions.ConnectionError:
            return "⚠️ 无法连接 Ollama，请确保 Ollama 已启动并拉取了模型。"
        except requests.exceptions.Timeout:
            return "⚠️ LLM 调用超时，请稍后重试。"
        except Exception as e:
            return f"⚠️ LLM 调用失败: {e}"

    def chat_stream(self, messages: list[dict]):
        """流式对话，yield 每个token"""
        url = f"{self.base_url}/api/chat"
        # 流式连接超时短一些，读取超时用默认
        if self._override_timeout:
            req_timeout = (3, self._override_timeout)
        else:
            req_timeout = (5, 180)
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        try:
            with requests.post(url, json=payload, stream=True, timeout=req_timeout) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("done"):
                            break
        except requests.exceptions.ConnectionError:
            yield "⚠️ 无法连接 Ollama，请确保 Ollama 已启动。"
        except requests.exceptions.Timeout:
            yield "⚠️ LLM 调用超时，请稍后重试。"
        except Exception as e:
            yield f"⚠️ LLM 调用失败: {e}"

    def generate(self, prompt: str, system: str = "", timeout: int | None = None) -> str:
        """简单生成接口，timeout 覆盖默认超时"""
        saved_timeout = self.max_tokens
        try:
            if timeout is not None:
                # 临时缩短 requests 超时
                self._override_timeout = timeout
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            return self.chat(messages)
        finally:
            self._override_timeout = None

    def check_connection(self) -> bool:
        """检查 Ollama 是否可用"""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except:
            return False

    def list_models(self) -> list[str]:
        """列出可用模型"""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except:
            pass
        return []
