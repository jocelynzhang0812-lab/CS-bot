"""高频问题聚类 —— KMeans + LLM 命名

优先聚类 kb_hit=0 的对话：这些是知识库盲区，对产品优化价值最高。
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize

DEFAULT_DB_PATH = "cs_agent.db"


def fetch_queries(db_path: str = None, days: int = 7, kb_hit_only: bool = False) -> List[str]:
    """
    从数据库拉取用户问题文本。
    :param kb_hit_only: True=只拉 kb_hit=0（知识盲区），False=拉全部
    """
    db_path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(db_path)
    since = (datetime.now() - timedelta(days=days)).isoformat()

    if kb_hit_only:
        rows = conn.execute(
            "SELECT user_query FROM conversations WHERE created_at >= ? AND kb_hit = 0",
            (since,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT user_query FROM conversations WHERE created_at >= ?",
            (since,)
        ).fetchall()

    return [r[0] for r in rows if r[0] and len(r[0].strip()) > 3]


def cluster_queries(
    queries: List[str],
    embeddings_fn,
    n_clusters: int = 5,
) -> Dict[int, List[str]]:
    """
    对用户问题进行向量聚类。
    :param embeddings_fn: function(text) -> embedding_vector
    :param n_clusters: 聚类数
    :return: {cluster_id: [query1, query2, ...]}
    """
    if len(queries) < 2:
        return {0: queries}

    if len(queries) < n_clusters:
        n_clusters = max(2, len(queries) // 2)

    vectors = np.array([embeddings_fn(q) for q in queries])
    vectors = normalize(vectors)

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(vectors)

    clusters = {}
    for query, label in zip(queries, labels):
        clusters.setdefault(int(label), []).append(query)

    # 按簇大小排序，高频在前
    return dict(sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True))


CLUSTER_NAMING_PROMPT = """你是客服数据分析师，请为以下用户提问聚类命名。

该聚类共 {count} 条相似问题：
{samples}

请输出纯 JSON，不要 markdown 代码块：
{{
  "topic": "该类问题的核心主题（10字以内）",
  "pattern": "用户在问什么（20字以内）",
  "suggestion": "建议知识库补充或产品改进方向（30字以内）"
}}
"""


async def name_clusters(clusters: Dict[int, List[str]], llm_client) -> List[dict]:
    """
    用 LLM 为每个聚类命名并给出建议。
    :return: [{rank, count, topic, pattern, suggestion, samples}, ...]
    """
    results = []
    for label, queries in clusters.items():
        samples = "\n".join(f"- {q}" for q in queries[:5])
        prompt = CLUSTER_NAMING_PROMPT.format(
            count=len(queries),
            samples=samples,
        )
        try:
            response = await llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                top_p=0.5,
            )
            raw = response.get("content", "").strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            info = json.loads(raw)
        except Exception as e:
            print(f"[ClusterNaming] 解析失败: {e}")
            info = {"topic": f"话题{label}", "pattern": "解析失败", "suggestion": ""}

        results.append({
            "rank": len(results) + 1,
            "count": len(queries),
            "topic": info.get("topic", ""),
            "pattern": info.get("pattern", ""),
            "suggestion": info.get("suggestion", ""),
            "samples": queries[:3],
        })
    return results
