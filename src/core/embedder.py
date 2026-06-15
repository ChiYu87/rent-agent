"""本地 Embedding - 基于 Ollama

兼容新旧版 Ollama API:
- 新版 (>=0.5): POST /api/embed  body={model, input}
- 旧版 (<0.5):  POST /api/embeddings body={model, prompt}
自动检测并回退。
"""
import json
import requests
from ..utils.config import Config


class Embedder:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        cfg = Config()
        self.base_url = cfg.get("embedding.base_url", "http://localhost:11434")
        self.model = cfg.get("embedding.model", "")
        self.dimension = cfg.get("embedding.dimension", 384)
        self._use_new_api = None  # None=未检测, True=新版, False=旧版

        # 自动选择可用的 embedding 模型
        if not self.model:
            self.model = self._auto_pick_model()

    def _auto_pick_model(self) -> str:
        """自动从已安装模型中选一个 embedding 模型"""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                # 优先选常见 embedding 模型
                preferred = ["nomic-embed-text", "all-minilm", "mxbai-embed-large", "snowflake-arctic-embed"]
                for p in preferred:
                    for m in models:
                        if p in m:
                            return m
                # 没有专门的 embedding 模型，尝试用任意模型
                if models:
                    return models[0]
        except:
            pass
        return "all-minilm"

    def _detect_api_version(self) -> bool:
        """检测 Ollama API 版本，返回 True=新版 /api/embed"""
        # 先试新版
        try:
            resp = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": "test"},
                timeout=10
            )
            if resp.status_code == 200:
                return True
        except:
            pass

        # 回退旧版
        try:
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": "test"},
                timeout=10
            )
            if resp.status_code == 200:
                return False
        except:
            pass

        # 默认假设旧版
        return False

    def embed(self, text: str) -> list[float]:
        """获取文本的向量表示"""
        # 首次调用时检测 API 版本
        if self._use_new_api is None:
            self._use_new_api = self._detect_api_version()
            print(f"Embedding API: {'新版 /api/embed' if self._use_new_api else '旧版 /api/embeddings'}")

        try:
            if self._use_new_api:
                resp = requests.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": text},
                    timeout=30
                )
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings", [])
                if embeddings:
                    vec = embeddings[0]
                    self.dimension = len(vec)
                    return vec
            else:
                resp = requests.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=30
                )
                resp.raise_for_status()
                data = resp.json()
                vec = data.get("embedding", [])
                if vec:
                    self.dimension = len(vec)
                    return vec
        except Exception as e:
            print(f"Embedding 失败: {e}")

        return [0.0] * self.dimension

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量获取向量"""
        results = []
        for text in texts:
            results.append(self.embed(text))
        return results
