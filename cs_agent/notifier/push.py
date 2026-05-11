"""推送层 —— 企业微信 / 钉钉 Webhook"""

import requests
from typing import Optional, List


def push_wecom(webhook_url: str, content: str) -> bool:
    """企业微信机器人 Webhook 推送 Markdown 消息。"""
    if not webhook_url:
        print("[Push] 企业微信 Webhook 未配置，跳过")
        return False
    try:
        resp = requests.post(webhook_url, json={
            "msgtype": "markdown",
            "markdown": {"content": content}
        }, timeout=10)
        data = resp.json()
        if data.get("errcode") != 0:
            print(f"[Push] 企业微信推送失败: {data}")
            return False
        return True
    except Exception as e:
        print(f"[Push] 企业微信请求异常: {e}")
        return False


def push_dingtalk(webhook_url: str, content: str, title: str = "客服报告") -> bool:
    """钉钉机器人 Webhook 推送 Markdown 消息。"""
    if not webhook_url:
        print("[Push] 钉钉 Webhook 未配置，跳过")
        return False
    try:
        resp = requests.post(webhook_url, json={
            "msgtype": "markdown",
            "markdown": {"title": title, "text": content}
        }, timeout=10)
        data = resp.json()
        if data.get("errcode") != 0:
            print(f"[Push] 钉钉推送失败: {data}")
            return False
        return True
    except Exception as e:
        print(f"[Push] 钉钉请求异常: {e}")
        return False


def format_report_message(stats: dict, period: str = "日") -> str:
    """将统计数据格式化为推送用的 Markdown 文本。"""
    ed = stats["emotion_dist"]
    lines = [
        f"## 📊 客服{period}数据概览",
        "",
        f"**工单总量**：{stats['total']} 条",
        f"**平均轮数**：{stats['avg_turns']} 轮",
        f"**知识库命中率**：{stats['kb_hit_rate']}%",
        f"**问题解决率**：{stats['resolved_rate']}%",
        f"**情绪分布**：😊 {ed.get('positive', 0)} / 😐 {ed.get('neutral', 0)} / 😠 {ed.get('negative', 0)}",
    ]

    # 异常告警
    alerts = []
    if stats["kb_hit_rate"] < 60:
        alerts.append("⚠️ 知识库命中率低于 60%")
    neg_rate = ed.get("negative", 0) / max(stats["total"], 1)
    if neg_rate > 0.3:
        alerts.append("⚠️ 负向情绪占比超过 30%")
    if stats["resolved_rate"] < 70:
        alerts.append("⚠️ 问题解决率低于 70%")

    if alerts:
        lines.extend(["", "**🚨 异常指标**"] + [f"- {a}" for a in alerts])

    return "\n".join(lines)


def push_feishu(webhook_url: str, content: str) -> bool:
    """飞书自定义机器人 Webhook 推送 text 消息。"""
    if not webhook_url:
        print("[Push] 飞书 Webhook 未配置，跳过")
        return False
    try:
        resp = requests.post(webhook_url, json={
            "msg_type": "text",
            "content": {"text": content}
        }, timeout=10)
        data = resp.json()
        if data.get("code") != 0:
            print(f"[Push] 飞书推送失败: {data}")
            return False
        return True
    except Exception as e:
        print(f"[Push] 飞书请求异常: {e}")
        return False


def format_cluster_message(clusters: List[dict], period: str = "周") -> str:
    """将聚类结果格式化为推送用的 Markdown 文本。"""
    lines = [f"## 📌 {period}高频问题聚类 Top{min(5, len(clusters))}"]
    for c in clusters[:5]:
        lines.append(
            f"\n**#{c['rank']} {c['topic']}** （{c['count']} 条）\n"
            f"> 用户在问：{c['pattern']}\n"
            f"> 建议：{c['suggestion']}"
        )
    return "\n".join(lines)
