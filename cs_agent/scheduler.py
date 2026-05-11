"""定时任务入口 —— 日报/周报自动推送

用法：
    python cs_agent/scheduler.py

依赖：
    pip install schedule scikit-learn
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# 把项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import schedule
except ImportError:
    print("[Scheduler] 缺少 schedule 库，请运行: pip install schedule")
    schedule = None

from csbot.agent.llm import LLMClient
from csbot.knowledge.embeddings import OpenAIEmbeddingProvider

from cs_agent.storage.db import init_db, DEFAULT_DB_PATH
from cs_agent.reporter.stats import query_stats
from cs_agent.reporter.report_generator import generate_report
from cs_agent.clustering.cluster_queries import fetch_queries, cluster_queries, name_clusters
from cs_agent.notifier.push import (
    push_wecom, push_dingtalk, push_feishu,
    format_report_message, format_cluster_message,
)

# ── 配置（从环境变量读取）──
WECOM_WEBHOOK = os.getenv("CS_WECOM_WEBHOOK", "")
DINGTALK_WEBHOOK = os.getenv("CS_DINGTALK_WEBHOOK", "")
FEISHU_WEBHOOK = os.getenv("CS_FEISHU_WEBHOOK", "")
DB_PATH = os.getenv("CS_DB_PATH", str(DEFAULT_DB_PATH))


class Scheduler:
    """定时任务调度器。"""

    def __init__(self, llm_client=None, embedding_provider=None):
        self.llm = llm_client
        self.embeddings = embedding_provider
        self.conn = init_db(DB_PATH)

    async def send_daily_report(self):
        """发送日报。"""
        stats = query_stats(DB_PATH, days=1)

        if stats["total"] == 0:
            msg = "📊 日报：今日暂无对话数据。"
        else:
            if self.llm:
                msg = await generate_report(stats, self.llm, period="日")
            else:
                msg = format_report_message(stats, period="日")

        push_wecom(WECOM_WEBHOOK, msg)
        push_dingtalk(DINGTALK_WEBHOOK, msg, title="客服日报")
        push_feishu(FEISHU_WEBHOOK, msg)
        print(f"[{datetime.now()}] 日报已发送")

    async def send_weekly_cluster(self):
        """发送聚类周报。"""
        queries = fetch_queries(DB_PATH, days=7, kb_hit_only=True)

        if len(queries) < 5:
            msg = "📊 本周知识库未命中数据不足，暂不生成聚类报告。"
            push_wecom(WECOM_WEBHOOK, msg)
            push_dingtalk(DINGTALK_WEBHOOK, msg, title="高频问题周报")
            print(f"[{datetime.now()}] 聚类周报：数据不足，已跳过")
            return

        # 数据量小用 3 个簇，大用 8 个
        n = 3 if len(queries) < 50 else (8 if len(queries) > 200 else 5)

        if self.embeddings:
            clusters = cluster_queries(
                queries,
                embeddings_fn=lambda q: self._embed(q),
                n_clusters=n,
            )
        else:
            # 无嵌入模型时，不做聚类，直接按关键词分组
            clusters = {0: queries[:10]}

        if self.llm:
            named = await name_clusters(clusters, self.llm)
        else:
            named = [{"rank": 1, "count": len(queries), "topic": "未分类", "pattern": "数据不足", "suggestion": ""}]

        msg = format_cluster_message(named, period="周")
        push_wecom(WECOM_WEBHOOK, msg)
        push_dingtalk(DINGTALK_WEBHOOK, msg, title="高频问题周报")
        push_feishu(FEISHU_WEBHOOK, msg)
        print(f"[{datetime.now()}] 聚类周报已发送，共 {len(named)} 个话题")

    def _embed(self, text: str) -> list:
        """同步调用嵌入模型（scheduler 单线程运行）。"""
        if self.embeddings:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 在已有事件循环中创建任务
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, self.embeddings.embed([text]))
                        result = future.result()
                        return result[0]
                else:
                    result = loop.run_until_complete(self.embeddings.embed([text]))
                    return result[0]
            except Exception as e:
                print(f"[Scheduler] 嵌入失败: {e}")
        return [0.0] * 1536  # fallback

    def run(self):
        """启动定时任务。"""
        if schedule is None:
            print("[Scheduler] schedule 库未安装，退出")
            return

        # 每天 18:00 发日报
        schedule.every().day.at("18:00").do(lambda: asyncio.run(self.send_daily_report()))
        # 每周一 09:00 发聚类周报
        schedule.every().monday.at("09:00").do(lambda: asyncio.run(self.send_weekly_cluster()))

        print(f"[Scheduler] 已启动，DB={DB_PATH}")
        print(f"  日报: 每天 18:00")
        print(f"  周报: 每周一 09:00")
        print(f"  飞书: {'已配置' if FEISHU_WEBHOOK else '未配置'}")
        print(f"  企微: {'已配置' if WECOM_WEBHOOK else '未配置'}")
        print(f"  钉钉: {'已配置' if DINGTALK_WEBHOOK else '未配置'}")
        print("  按 Ctrl+C 退出")

        while True:
            schedule.run_pending()
            import time
            time.sleep(60)


def main():
    # 尝试初始化 LLM 和 Embedding（可选）
    llm = None
    embeddings = None
    try:
        api_key = os.getenv("KIMI_API_KEY")
        if api_key:
            llm = LLMClient(api_key=api_key)
            print("[Scheduler] LLM 已初始化")
    except Exception as e:
        print(f"[Scheduler] LLM 初始化失败（非阻塞）: {e}")

    try:
        emb_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
        if emb_key:
            embeddings = OpenAIEmbeddingProvider()
            print("[Scheduler] Embedding 已初始化")
    except Exception as e:
        print(f"[Scheduler] Embedding 初始化失败（非阻塞）: {e}")

    scheduler = Scheduler(llm_client=llm, embedding_provider=embeddings)
    scheduler.run()


if __name__ == "__main__":
    main()
