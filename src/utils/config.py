"""配置管理"""
import json
import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / "src" / "data"
PROMPTS_DIR = ROOT_DIR / "prompts"

# 默认配置
DEFAULT_CONFIG = {
    "llm": {
        "model": "",  # 留空自动检测可用模型
        "base_url": "http://localhost:11434",
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "embedding": {
        "model": "",  # 留空自动检测，优先 nomic-embed-text > all-minilm
        "base_url": "http://localhost:11434",
        "dimension": 384,  # all-minilm=384, nomic-embed-text=768
    },
    "memory": {
        "db_path": str(ROOT_DIR / "rentbuddy.db"),
        "max_short_term": 20,      # 短期记忆条数
        "similarity_threshold": 0.6, # 长期记忆召回阈值
    },
    "agent": {
        "max_iterations": 5,        # ReAct 最大迭代
        "thinking_budget": 500,     # 思考token预算
    },
    "city": "北京",                  # 默认城市
}


class Config:
    """单例配置"""
    _instance = None
    _data = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._data is None:
            self._load()

    def _load(self):
        config_path = ROOT_DIR / "config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            self._data = {**DEFAULT_CONFIG, **user_config}
        else:
            self._data = DEFAULT_CONFIG.copy()

    def save(self):
        config_path = ROOT_DIR / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get(self, key, default=None):
        keys = key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
            if val is None:
                return default
        return val

    def set(self, key, value):
        keys = key.split(".")
        d = self._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        self.save()

    @property
    def all(self):
        return self._data.copy()
