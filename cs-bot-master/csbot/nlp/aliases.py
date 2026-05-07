"""用户口语化表达别名映射
处理用户真实表达与知识库/系统标准关键词之间的映射关系。
注意：此映射仅用于意图识别和产品判定，不改变原始查询文本用于知识库检索。
"""
from typing import Dict, List


# 口语化别名 → 标准术语（用于意图识别、产品判定）
USER_EXPRESSION_ALIASES: Dict[str, str] = {
    # ── 产品别名 ──
    "小龙虾": "claw",
    "小爪子": "claw",
    "小虾": "claw",
    "虾": "claw",          # 需配合上下文判断，避免误伤
    "爪子": "claw",
    "kimiclaw": "claw",
    "kimi claw": "claw",

    # ── 状态/问题别名 ──
    "卡住了": "卡顿",
    "卡死": "崩溃",
    "挂了": "离线",
    "死了": "离线",
    "没反应": "不回消息",
    "不动": "不回消息",
    "抽风": "异常",
    "bug了": "bug",
    "出bug": "bug",
    "崩了": "崩溃",
    "闪退": "崩溃",
    "连不上": "连接断开",
    "上不去": "连接断开",
    "登不上": "接入失败",
    "登不进": "接入失败",
    "装不上": "部署失败",
    "装不了": "部署失败",
    "用不了": "故障",
    "不能用了": "故障",
    "失效": "故障",
    "失灵": "故障",

    # ── 操作/功能别名 ──
    "忘掉": "失忆",
    "不记得": "失忆",
    "记不住": "记忆",
    "丢记录": "失忆",
    "清空": "重置",
    "还原": "恢复初始设置",
    "退回": "恢复初始版本",
}


# 需要上下文消歧的高歧义词（单独出现时含义不明确）
VAGUE_TERMS: List[str] = [
    "卡住了", "卡", "挂了", "死了", "不动", "没反应", "异常", "不行",
    "用不了", "崩了", "掉了", "断了",
]


def normalize_user_expression(text: str) -> str:
    """将用户口语化表达映射为标准术语，返回映射后的文本。"""
    normalized = text
    for alias, standard in USER_EXPRESSION_ALIASES.items():
        if alias in normalized:
            normalized = normalized.replace(alias, standard)
    return normalized


def expand_for_intent_detection(text: str) -> str:
    """生成用于意图检测的扩展文本（原始 + 映射后），提高召回率。
    格式: "原始文本 [别名映射: 映射后文本]"
    """
    normalized = normalize_user_expression(text)
    if normalized == text:
        return text
    return f"{text} [别名映射: {normalized}]"


def is_vague_expression(text: str) -> bool:
    """判断文本是否包含需要上下文消歧的模糊表达。"""
    return any(v in text for v in VAGUE_TERMS)


def infer_context_from_history(
    current_message: str,
    session_state: Dict,
    history: List[Dict],
) -> Dict:
    """基于 session 上下文对模糊表达进行消歧推断。

    返回结构:
    {
        "inferred_product_type": str | None,
        "inferred_module": str | None,
        "inferred_issue_type": str | None,
        "confidence": "low" | "medium" | "high",
        "reasoning": str,
        "needs_clarify": bool,  # 置信度低时建议追问
    }
    """
    result = {
        "inferred_product_type": None,
        "inferred_module": None,
        "inferred_issue_type": None,
        "confidence": "low",
        "reasoning": "",
        "needs_clarify": True,
    }

    # 如果当前消息本身不模糊，无需推断
    if not is_vague_expression(current_message):
        result["confidence"] = "high"
        result["needs_clarify"] = False
        return result

    # ── 继承已确认的 session 状态 ──
    known_product = session_state.get("product_type") if session_state else None
    known_module = session_state.get("module") if session_state else None
    known_issue = session_state.get("issue_desc") if session_state else None

    if known_product:
        result["inferred_product_type"] = known_product
        result["confidence"] = "medium"
        result["reasoning"] += f"继承已确认产品类型: {known_product}; "

    if known_module:
        result["inferred_module"] = known_module
        result["confidence"] = "medium"
        result["reasoning"] += f"继承已确认模块: {known_module}; "

    # ── 从历史对话推断 ──
    if history:
        recent_user_msgs = [
            h["content"] for h in history[-6:]
            if h.get("role") == "user"
        ]
        all_recent_text = " ".join(recent_user_msgs)
        normalized_recent = normalize_user_expression(all_recent_text)

        # ── 从历史推断产品类型 ──
        if not result["inferred_product_type"]:
            if any(w in normalized_recent for w in {"desktop", "本地", "电脑", "finder", "访达"}):
                result["inferred_product_type"] = "desktop"
                result["reasoning"] += "历史上下文涉及 Desktop; "
            elif any(w in normalized_recent for w in {"android", "安卓", "手机", "dashboard", "权限"}):
                result["inferred_product_type"] = "android"
                result["reasoning"] += "历史上下文涉及 Android; "
            elif any(w in normalized_recent for w in {"群聊", "conductor", "thread", "群规"}):
                result["inferred_product_type"] = "群聊"
                result["reasoning"] += "历史上下文涉及群聊; "
            elif any(w in normalized_recent for w in {"云端", "网页", "app", "kimi.com", "web ssh"}):
                result["inferred_product_type"] = "云端"
                result["reasoning"] += "历史上下文涉及云端; "
            elif "claw" in normalized_recent.lower():
                result["inferred_product_type"] = "claw（待确认形态）"
                result["reasoning"] += "历史上下文涉及 claw; "

        # 部署/安装上下文
        deploy_kw = {"部署", "安装", "装", "上线", "发布", "配置环境", "初始化", "搭"}
        if any(d in all_recent_text for d in deploy_kw):
            result["inferred_module"] = "故障排查"
            result["inferred_issue_type"] = "部署/安装问题"
            result["reasoning"] += "历史上下文涉及部署/安装; "

        # 对话/消息上下文
        chat_kw = {"聊天", "对话", "回复", "消息", "不回", "没反应", "@", "mention"}
        if any(d in all_recent_text for d in chat_kw):
            result["inferred_module"] = "故障排查"
            result["inferred_issue_type"] = "对话功能异常"
            result["reasoning"] += "历史上下文涉及对话/消息功能; "

        # 记忆/上下文
        memory_kw = {"记忆", "上下文", "session", "忘了", "失忆", "记不住", "凌晨"}
        if any(d in all_recent_text for d in memory_kw):
            result["inferred_module"] = "记忆上下文"
            result["reasoning"] += "历史上下文涉及记忆/上下文; "

        # 会员/额度/支付
        billing_kw = {"会员", "额度", "充值", "订阅", "钱", "付费", "退款", "开票"}
        if any(d in all_recent_text for d in billing_kw):
            result["inferred_module"] = "会员额度"
            result["reasoning"] += "历史上下文涉及会员/额度; "

        # 接入/平台
        auth_kw = {"接入", "飞书", "微信", "企微", "钉钉", "扫码", "token", "鉴权"}
        if any(d in all_recent_text for d in auth_kw):
            result["inferred_module"] = "接入鉴权"
            result["reasoning"] += "历史上下文涉及接入/鉴权; "

        # 终端/命令
        cmd_kw = {"命令", "终端", "terminal", "ssh", "/help", "/status", "/logs", "cli"}
        if any(d in all_recent_text for d in cmd_kw):
            result["inferred_module"] = "命令与终端"
            result["reasoning"] += "历史上下文涉及命令/终端; "

    # ── 根据推断完整度确定置信度和是否需要追问 ──
    has_product = result["inferred_product_type"] is not None
    has_module = result["inferred_module"] is not None

    if has_product and has_module:
        result["confidence"] = "high"
        result["needs_clarify"] = False
    elif has_product or has_module:
        result["confidence"] = "medium"
        result["needs_clarify"] = True
    else:
        result["confidence"] = "low"
        result["needs_clarify"] = True

    return result
