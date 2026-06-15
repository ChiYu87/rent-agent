"""长期记忆系统 - 短期对话 + 长期语义检索"""
from datetime import datetime
from .embedder import Embedder
from ..utils.db import Database
from ..utils.config import Config


class Memory:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.db = Database()
        self.embedder = Embedder()
        self.max_short_term = Config().get("memory.max_short_term", 20)
        self.similarity_threshold = Config().get("memory.similarity_threshold", 0.6)

    def save_interaction(self, session_id: str, user_msg: str, assistant_msg: str):
        """保存一轮对话"""
        self.db.add_message(session_id, "user", user_msg)
        self.db.add_message(session_id, "assistant", assistant_msg)

        # 判断是否值得存入长期记忆
        if self._is_memorable(user_msg, assistant_msg):
            self._save_long_term(assistant_msg, category="conversation")

    def get_context(self, session_id: str, current_query: str = "") -> list[dict]:
        """构建上下文：短期对话历史 + 相关长期记忆"""
        context = []

        # 1. 相关长期记忆
        if current_query:
            relevant = self.recall(current_query, limit=3)
            if relevant:
                memory_text = "\n".join([f"- {m['content']}" for m in relevant])
                context.append({
                    "role": "system",
                    "content": f"📖 相关记忆:\n{memory_text}"
                })

        # 2. 短期对话历史
        messages = self.db.get_messages(session_id, limit=self.max_short_term)
        for msg in messages:
            context.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        return context

    def recall(self, query: str, limit: int = 5) -> list[dict]:
        """语义检索长期记忆"""
        query_emb = self.embedder.embed(query)
        if all(v == 0.0 for v in query_emb):
            return []
        return self.db.search_memories(query_emb, limit=limit, threshold=self.similarity_threshold)

    def remember(self, content: str, category: str = "general", importance: float = 0.5):
        """主动记住一条信息"""
        self._save_long_term(content, category, importance)

    def _save_long_term(self, content: str, category: str = "general", importance: float = 0.5):
        embedding = self.embedder.embed(content)
        self.db.add_memory(content, embedding, category, importance)

    def _is_memorable(self, user_msg: str, assistant_msg: str) -> bool:
        """判断对话是否值得长期记忆"""
        # 包含关键决策/偏好/事实的才存
        memorable_keywords = [
            "预算", "偏好", "决定", "选择", "要求", "习惯",
            "养宠", "合租", "整租", "通勤", "公司", "地铁站",
            "押金", "中介", "房东", "签约", "退租",
        ]
        combined = user_msg + assistant_msg
        return any(kw in combined for kw in memorable_keywords)

    def save_user_profile(self, key: str, value: str):
        """保存用户偏好"""
        self.db.set_profile(key, value)
        # 同时记入长期记忆
        self._save_long_term(f"用户{key}: {value}", category="profile", importance=0.8)

    def get_user_profile(self, key: str, default: str = None) -> str:
        return self.db.get_profile(key, default)
