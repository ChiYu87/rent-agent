"""SQLite 数据库管理"""
import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from .config import Config


class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        db_path = Config().get("memory.db_path")
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        # 对话历史
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        # 长期记忆（语义存储）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                embedding BLOB,
                category TEXT DEFAULT 'general',
                importance REAL DEFAULT 0.5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                accessed_at TEXT,
                access_count INTEGER DEFAULT 0
            )
        """)
        # 看房记录
        cur.execute("""
            CREATE TABLE IF NOT EXISTS viewings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT,
                checklist_json TEXT,
                photos_json TEXT,
                notes TEXT,
                score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 合同记录
        cur.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                ocr_text TEXT,
                analysis_json TEXT,
                risk_level TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 黑名单
        cur.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                type TEXT,
                reason TEXT,
                city TEXT,
                reported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                anonymous_id TEXT
            )
        """)
        # 用户偏好
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    # --- 对话 ---
    def add_message(self, session_id: str, role: str, content: str, metadata: dict = None):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO conversations (session_id, role, content, metadata) VALUES (?, ?, ?, ?)",
            (session_id, role, content, json.dumps(metadata) if metadata else None)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_messages(self, session_id: str, limit: int = 50):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        )
        rows = cur.fetchall()
        return [dict(r) for r in reversed(rows)]

    # --- 长期记忆 ---
    def add_memory(self, content: str, embedding: list, category: str = "general", importance: float = 0.5):
        emb_bytes = json.dumps(embedding).encode("utf-8")
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO memories (content, embedding, category, importance) VALUES (?, ?, ?, ?)",
            (content, emb_bytes, category, importance)
        )
        self.conn.commit()
        return cur.lastrowid

    def search_memories(self, query_embedding: list, limit: int = 5, threshold: float = 0.6):
        """向量检索长期记忆（余弦相似度）"""
        cur = self.conn.cursor()
        cur.execute("SELECT id, content, embedding, category, importance FROM memories")
        results = []
        for row in cur.fetchall():
            emb = json.loads(row["embedding"].decode("utf-8"))
            sim = self._cosine_similarity(query_embedding, emb)
            if sim >= threshold:
                results.append({
                    "id": row["id"],
                    "content": row["content"],
                    "category": row["category"],
                    "importance": row["importance"],
                    "similarity": sim,
                })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        # 更新访问计数
        for r in results[:limit]:
            self.conn.execute(
                "UPDATE memories SET access_count = access_count + 1, accessed_at = ? WHERE id = ?",
                (datetime.now().isoformat(), r["id"])
            )
        self.conn.commit()
        return results[:limit]

    @staticmethod
    def _cosine_similarity(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # --- 用户偏好 ---
    def set_profile(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO user_profile (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_profile(self, key: str, default: str = None):
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM user_profile WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default

    # --- 看房记录 ---
    def add_viewing(self, address: str, checklist: dict, photos: list, notes: str, score: float):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO viewings (address, checklist_json, photos_json, notes, score) VALUES (?, ?, ?, ?, ?)",
            (address, json.dumps(checklist, ensure_ascii=False),
             json.dumps(photos, ensure_ascii=False), notes, score)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_viewings(self, limit: int = 20):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM viewings ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cur.fetchall()]

    # --- 合同记录 ---
    def add_contract(self, file_path: str, ocr_text: str, analysis: dict, risk_level: str):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO contracts (file_path, ocr_text, analysis_json, risk_level) VALUES (?, ?, ?, ?)",
            (file_path, ocr_text, json.dumps(analysis, ensure_ascii=False), risk_level)
        )
        self.conn.commit()
        return cur.lastrowid

    # --- 黑名单 ---
    def add_blacklist_entry(self, name: str, type_: str, reason: str, city: str, anonymous_id: str = None):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO blacklist (name, type, reason, city, anonymous_id) VALUES (?, ?, ?, ?, ?)",
            (name, type_, reason, city, anonymous_id or hashlib.md5(name.encode()).hexdigest()[:8])
        )
        self.conn.commit()

    def check_blacklist(self, name: str, city: str = None):
        cur = self.conn.cursor()
        if city:
            cur.execute("SELECT * FROM blacklist WHERE name LIKE ? AND city = ?", (f"%{name}%", city))
        else:
            cur.execute("SELECT * FROM blacklist WHERE name LIKE ?", (f"%{name}%",))
        return [dict(r) for r in cur.fetchall()]

    def close(self):
        self.conn.close()
