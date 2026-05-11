"""统计聚合 —— 从 SQLite 拉取数据并计算核心指标"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional


DEFAULT_DB_PATH = "cs_agent.db"


def query_stats(db_path: str = None, days: int = 1) -> dict:
    """
    查询指定时间范围内的对话统计。
    :param days: 往前推多少天（1=日报，7=周报）
    :return: 统计字典
    """
    db_path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path)
    since = (datetime.now() - timedelta(days=days)).isoformat()

    rows = conn.execute(
        "SELECT * FROM conversations WHERE created_at >= ?", (since,)
    ).fetchall()
    cols = [d[0] for d in conn.execute(
        "SELECT * FROM conversations LIMIT 0").description]
    records = [dict(zip(cols, r)) for r in rows]

    if not records:
        return {"total": 0, "period_days": days}

    total = len(records)
    avg_turns = sum(r["turns"] for r in records) / total
    kb_hit_rate = sum(r["kb_hit"] for r in records) / total
    resolved_rate = sum(r["resolved"] for r in records) / total

    emotion_dist = {"positive": 0, "neutral": 0, "negative": 0}
    for r in records:
        emotion_dist[r["emotion"]] = emotion_dist.get(r["emotion"], 0) + 1

    # 意图分布
    intent_dist: Dict[str, int] = {}
    for r in records:
        intent = r["intent"] or "unknown"
        intent_dist[intent] = intent_dist.get(intent, 0) + 1

    # 产品类型分布
    product_dist: Dict[str, int] = {}
    for r in records:
        pt = r["product_type"] or "unknown"
        product_dist[pt] = product_dist.get(pt, 0) + 1

    return {
        "total": total,
        "avg_turns": round(avg_turns, 1),
        "kb_hit_rate": round(kb_hit_rate * 100, 1),
        "resolved_rate": round(resolved_rate * 100, 1),
        "emotion_dist": emotion_dist,
        "intent_dist": intent_dist,
        "product_dist": product_dist,
        "period_days": days,
    }
