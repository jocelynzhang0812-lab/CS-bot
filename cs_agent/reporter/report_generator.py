"""报告生成器 —— LLM 润色统计数据为可读 Markdown 报告"""

from typing import Optional


REPORT_PROMPT = """你是客服数据分析师，根据以下统计数据生成一份简洁的{period}报告。

数据：
- 工单总量：{total} 条
- 平均解决轮数：{avg_turns} 轮
- 知识库命中率：{kb_hit_rate}%
- 问题解决率：{resolved_rate}%
- 情绪分布：正向 {pos} 条，中性 {neu} 条，负向 {neg} 条
- 意图分布：{intent_dist}
- 产品分布：{product_dist}

要求：
1. 用 3-5 句话总结整体情况
2. 指出最值得关注的 1-2 个异常指标（如命中率低于 60% 则重点提示，负向情绪超过 30% 则告警）
3. 给出 1 条改进建议
4. 语言简洁，适合运营人员阅读
5. 输出 Markdown 格式，带 emoji

只输出报告内容，不要说"以下是"之类的开头。
"""


async def generate_report(stats: dict, llm_client, period: str = "日") -> str:
    """
    根据统计数据生成 LLM 润色报告。
    :param stats: query_stats() 返回的统计字典
    :param llm_client: LLMClient 实例
    :param period: "日" / "周"
    :return: Markdown 格式报告文本
    """
    if stats["total"] == 0:
        return f"📊 {period}报告：暂无对话数据。"

    ed = stats["emotion_dist"]
    intent_str = ", ".join(f"{k} {v}条" for k, v in stats.get("intent_dist", {}).items())
    product_str = ", ".join(f"{k} {v}条" for k, v in stats.get("product_dist", {}).items())

    prompt = REPORT_PROMPT.format(
        period=period,
        total=stats["total"],
        avg_turns=stats["avg_turns"],
        kb_hit_rate=stats["kb_hit_rate"],
        resolved_rate=stats["resolved_rate"],
        pos=ed.get("positive", 0),
        neu=ed.get("neutral", 0),
        neg=ed.get("negative", 0),
        intent_dist=intent_str,
        product_dist=product_str,
    )

    try:
        response = await llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            top_p=0.5,
        )
        return response.get("content", _fallback_report(stats, period)).strip()
    except Exception as e:
        print(f"[ReportGenerator] LLM 失败，回退到模板: {e}")
        return _fallback_report(stats, period)


def _fallback_report(stats: dict, period: str) -> str:
    """LLM 失败时的兜底模板报告。"""
    ed = stats["emotion_dist"]
    lines = [
        f"## 📊 客服{period}报告",
        "",
        f"- 工单总量：**{stats['total']}** 条",
        f"- 平均解决轮数：**{stats['avg_turns']}** 轮",
        f"- 知识库命中率：**{stats['kb_hit_rate']}%**",
        f"- 问题解决率：**{stats['resolved_rate']}%**",
        f"- 情绪分布：😊 {ed.get('positive', 0)} / 😐 {ed.get('neutral', 0)} / 😠 {ed.get('negative', 0)}",
    ]

    # 异常告警
    alerts = []
    if stats["kb_hit_rate"] < 60:
        alerts.append("⚠️ 知识库命中率低于 60%，建议补充知识库内容。")
    if stats.get("emotion_dist", {}).get("negative", 0) / max(stats["total"], 1) > 0.3:
        alerts.append("⚠️ 负向情绪占比超过 30%，建议排查服务质量。")
    if stats["resolved_rate"] < 70:
        alerts.append("⚠️ 问题解决率低于 70%，建议优化自助排查流程。")

    if alerts:
        lines.extend(["", "### 🚨 异常指标"] + alerts)
    else:
        lines.append("\n✅ 今日各项指标正常。")

    lines.append("\n---\n*本报告由 CS Bot 自动生成*")
    return "\n".join(lines)
