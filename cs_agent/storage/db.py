"""SQLite 持久化层 —— 每次对话结束时写入结构化指标"""

import sqlite3
from datetime import datetime
import json
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "cs_agent.db"


def init_db(db_path: str = None) -> sqlite3.Connection:
    """初始化数据库，创建 conversations 表（如果不存在）。"""
    db_path = db_path or str(DEFAULT_DB_PATH)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          TEXT PRIMARY KEY,
            created_at  TEXT,
            intent      TEXT,          -- knowledge_query / fault_report / greeting / other
            turns       INTEGER,       -- 对话轮数
            kb_hit      INTEGER,       -- 1=知识库命中 0=未命中
            resolved    INTEGER,       -- 1=已解决 0=未解决/转人工
            emotion     TEXT,          -- positive / neutral / negative
            user_query  TEXT,          -- 用户原始问题（用于聚类）
            slot_json   TEXT,          -- 槽位提取结果 JSON
            bot_reply   TEXT,          -- Bot 最终回复摘要
            product_type TEXT          -- 识别到的产品类型
        )
    """)
    # 创建常用索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON conversations(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intent ON conversations(intent)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kb_hit ON conversations(kb_hit)")
    conn.commit()
    return conn


def save_conversation(conn: sqlite3.Connection, record: dict):
    """写入或更新一条对话记录。"""
    conn.execute("""
        INSERT OR REPLACE INTO conversations
        VALUES (:id, :created_at, :intent, :turns, :kb_hit,
                :resolved, :emotion, :user_query, :slot_json, :bot_reply, :product_type)
    """, {
        "id": record.get("id", ""),
        "created_at": record.get("created_at") or datetime.now().isoformat(),
        "intent": record.get("intent", ""),
        "turns": record.get("turns", 0),
        "kb_hit": 1 if record.get("kb_hit") else 0,
        "resolved": 1 if record.get("resolved") else 0,
        "emotion": record.get("emotion", "neutral"),
        "user_query": record.get("user_query", ""),
        "slot_json": json.dumps(record.get("slot_json", {}), ensure_ascii=False),
        "bot_reply": record.get("bot_reply", "")[:500],
        "product_type": record.get("product_type", ""),
    })
    conn.commit()
