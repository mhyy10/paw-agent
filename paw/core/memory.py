"""记忆系统 - SQLite 持久化对话历史 + 会话管理"""

import json
import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Optional


class Memory:
    """基于 SQLite 的对话记忆"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                tool_calls TEXT,
                tool_call_id TEXT,
                tool_name TEXT,
                timestamp REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_session
            ON conversations(session_id)
        """)
        # 会话元数据表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_meta (
                session_id TEXT PRIMARY KEY,
                title TEXT,
                persona TEXT,
                model TEXT,
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.commit()
        conn.close()

    def add_message(self, session_id: str, role: str, content: str = None,
                    tool_calls: list = None, tool_call_id: str = None,
                    tool_name: str = None):
        """添加一条消息"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO conversations
               (session_id, role, content, tool_calls, tool_call_id, tool_name, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                role,
                content,
                json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                tool_call_id,
                tool_name,
                time.time(),
            ),
        )
        conn.commit()
        conn.close()

    def get_messages(self, session_id: str, limit: int = 50) -> List[Dict]:
        """获取会话的消息历史"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT role, content, tool_calls, tool_call_id, tool_name
               FROM conversations
               WHERE session_id = ?
               ORDER BY id DESC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
        conn.close()

        messages = []
        for row in reversed(rows):
            msg = {"role": row["role"]}
            if row["content"]:
                msg["content"] = row["content"]
            if row["tool_calls"]:
                msg["tool_calls"] = json.loads(row["tool_calls"])
            if row["tool_call_id"]:
                msg["tool_call_id"] = row["tool_call_id"]
            if row["tool_name"]:
                msg["name"] = row["tool_name"]
            messages.append(msg)

        return messages

    def get_sessions(self, limit: int = 20) -> List[Dict]:
        """获取最近的会话列表"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT c.session_id,
                      COALESCE(m.title, '') as title,
                      COALESCE(m.persona, 'default') as persona,
                      COALESCE(m.model, '') as model,
                      MIN(c.timestamp) as started,
                      MAX(c.timestamp) as last_active,
                      COUNT(*) as message_count
               FROM conversations c
               LEFT JOIN session_meta m ON c.session_id = m.session_id
               GROUP BY c.session_id
               ORDER BY last_active DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()

        sessions = []
        for r in rows:
            s = dict(r)
            # 自动生成标题：取第一条用户消息的前50字
            if not s["title"]:
                first_msg = self._get_first_user_message(s["session_id"])
                s["title"] = first_msg[:50] + "..." if len(first_msg) > 50 else first_msg
            sessions.append(s)
        return sessions

    def _get_first_user_message(self, session_id: str) -> str:
        """获取会话的第一条用户消息"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            """SELECT content FROM conversations
               WHERE session_id = ? AND role = 'user'
               ORDER BY id ASC LIMIT 1""",
            (session_id,),
        ).fetchone()
        conn.close()
        return row[0] if row else "(空会话)"

    def set_session_meta(self, session_id: str, title: str = None,
                         persona: str = None, model: str = None):
        """设置会话元数据"""
        conn = sqlite3.connect(self.db_path)
        now = time.time()
        conn.execute(
            """INSERT INTO session_meta (session_id, title, persona, model, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 title = COALESCE(excluded.title, session_meta.title),
                 persona = COALESCE(excluded.persona, session_meta.persona),
                 model = COALESCE(excluded.model, session_meta.model),
                 updated_at = excluded.updated_at""",
            (session_id, title, persona, model, now, now),
        )
        conn.commit()
        conn.close()

    def get_session_count(self) -> int:
        """获取会话总数"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT COUNT(DISTINCT session_id) FROM conversations"
        ).fetchone()
        conn.close()
        return row[0] if row else 0

    def clear_session(self, session_id: str):
        """清空会话历史"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_meta WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    def delete_session(self, session_id: str):
        """删除会话（与 clear 相同，但语义更明确）"""
        self.clear_session(session_id)

    def get_last_user_message(self, session_id: str) -> Optional[str]:
        """获取最后一条用户消息"""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            """SELECT content FROM conversations
               WHERE session_id = ? AND role = 'user'
               ORDER BY id DESC LIMIT 1""",
            (session_id,),
        ).fetchone()
        conn.close()
        return row[0] if row else None
