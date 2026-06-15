"""SQLite 数据库管理 - 支持多用户隔离

MVP 阶段用 SQLite + WAL 模式，生产环境迁移 PostgreSQL + pgvector
"""
import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from ..utils.config import Config


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
        # WAL 模式：读写不互斥，并发性能好
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()

        # 用户表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                nickname TEXT,
                city TEXT DEFAULT '北京',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 对话历史（加 user_id）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, session_id)")

        # 长期记忆（加 user_id）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB,
                category TEXT DEFAULT 'general',
                importance REAL DEFAULT 0.5,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                accessed_at TEXT,
                access_count INTEGER DEFAULT 0
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mem_user ON memories(user_id, category)")

        # 看房记录（加 user_id）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS viewings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                address TEXT,
                checklist_json TEXT,
                photos_json TEXT,
                notes TEXT,
                score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 合同记录（加 user_id）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                file_path TEXT,
                ocr_text TEXT,
                analysis_json TEXT,
                risk_level TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 黑名单（全局共享，不加 user_id）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                type TEXT,
                reason TEXT,
                city TEXT,
                reported_by TEXT,
                reported_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 用户偏好（已有 user_id 作为 key 的一部分）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, key)
            )
        """)

        self.conn.commit()

    # ==================== 用户 ====================

    def ensure_user(self, user_id: str, nickname: str = "") -> dict:
        """确保用户存在，不存在则创建"""
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            self.conn.execute(
                "UPDATE users SET last_active = ? WHERE user_id = ?",
                (datetime.now().isoformat(), user_id)
            )
            self.conn.commit()
            return dict(row)
        else:
            cur.execute(
                "INSERT INTO users (user_id, nickname) VALUES (?, ?)",
                (user_id, nickname)
            )
            self.conn.commit()
            return {"user_id": user_id, "nickname": nickname, "city": "北京"}

    def get_user(self, user_id: str) -> dict | None:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    # ==================== 对话 ====================

    def add_message(self, user_id: str, session_id: str, role: str, content: str, metadata: dict = None):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO conversations (user_id, session_id, role, content, metadata) VALUES (?, ?, ?, ?, ?)",
            (user_id, session_id, role, content, json.dumps(metadata) if metadata else None)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_messages(self, user_id: str, session_id: str, limit: int = 50):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM conversations WHERE user_id = ? AND session_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, session_id, limit)
        )
        rows = cur.fetchall()
        return [dict(r) for r in reversed(rows)]

    # ==================== 长期记忆 ====================

    def add_memory(self, user_id: str, content: str, embedding: list, category: str = "general", importance: float = 0.5):
        emb_bytes = json.dumps(embedding).encode("utf-8")
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO memories (user_id, content, embedding, category, importance) VALUES (?, ?, ?, ?, ?)",
            (user_id, content, emb_bytes, category, importance)
        )
        self.conn.commit()
        return cur.lastrowid

    def search_memories(self, user_id: str, query_embedding: list, limit: int = 5, threshold: float = 0.6):
        """向量检索长期记忆（按用户隔离）"""
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, content, embedding, category, importance FROM memories WHERE user_id = ?",
            (user_id,)
        )
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

    # ==================== 用户偏好 ====================

    def set_profile(self, user_id: str, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO user_profile (user_id, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (user_id, key, value, datetime.now().isoformat())
        )
        self.conn.commit()

    def get_profile(self, user_id: str, key: str, default: str = None):
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM user_profile WHERE user_id = ? AND key = ?", (user_id, key))
        row = cur.fetchone()
        return row["value"] if row else default

    def get_all_profiles(self, user_id: str) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT key, value FROM user_profile WHERE user_id = ?", (user_id,))
        return {row["key"]: row["value"] for row in cur.fetchall()}

    # ==================== 看房记录 ====================

    def add_viewing(self, user_id: str, address: str, checklist: dict, photos: list, notes: str, score: float):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO viewings (user_id, address, checklist_json, photos_json, notes, score) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, address, json.dumps(checklist, ensure_ascii=False),
             json.dumps(photos, ensure_ascii=False), notes, score)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_viewings(self, user_id: str, limit: int = 20):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM viewings WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        return [dict(r) for r in cur.fetchall()]

    # ==================== 合同记录 ====================

    def add_contract(self, user_id: str, file_path: str, ocr_text: str, analysis: dict, risk_level: str):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO contracts (user_id, file_path, ocr_text, analysis_json, risk_level) VALUES (?, ?, ?, ?, ?)",
            (user_id, file_path, ocr_text, json.dumps(analysis, ensure_ascii=False), risk_level)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_contracts(self, user_id: str, limit: int = 10):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM contracts WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
        return [dict(r) for r in cur.fetchall()]

    # ==================== 黑名单（全局） ====================

    def add_blacklist_entry(self, name: str, type_: str, reason: str, city: str, reported_by: str = ""):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO blacklist (name, type, reason, city, reported_by) VALUES (?, ?, ?, ?, ?)",
            (name, type_, reason, city, reported_by)
        )
        self.conn.commit()

    def check_blacklist(self, name: str, city: str = None):
        cur = self.conn.cursor()
        if city:
            cur.execute("SELECT * FROM blacklist WHERE name LIKE ? AND city = ?", (f"%{name}%", city))
        else:
            cur.execute("SELECT * FROM blacklist WHERE name LIKE ?", (f"%{name}%",))
        return [dict(r) for r in cur.fetchall()]

    def get_blacklist_stats(self) -> dict:
        """黑名单统计"""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM blacklist")
        total = cur.fetchone()["total"]
        cur.execute("SELECT city, COUNT(*) as cnt FROM blacklist GROUP BY city ORDER BY cnt DESC LIMIT 10")
        by_city = [dict(r) for r in cur.fetchall()]
        return {"total": total, "by_city": by_city}

    # ==================== 系统统计 ====================

    def get_stats(self) -> dict:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT user_id) as cnt FROM users")
        users = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM conversations")
        messages = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM blacklist")
        blacklist = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) as cnt FROM viewings")
        viewings = cur.fetchone()["cnt"]
        return {
            "users": users,
            "messages": messages,
            "blacklist_entries": blacklist,
            "viewings": viewings,
        }

    def close(self):
        self.conn.close()
