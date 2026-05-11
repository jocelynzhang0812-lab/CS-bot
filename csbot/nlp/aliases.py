"""用户口语化表达别名映射
处理用户真实表达与知识库/系统标准关键词之间的映射关系。
注意：此映射仅用于意图识别和产品判定，不改变原始查询文本用于知识库检索。
"""
import json
import os
from typing import Dict, List

# 同义词表文件路径（相对于本文件所在目录）
_SYNONYM_PATH = os.path.join(os.path.dirname(__file__), "synonyms.json")


def _load_synonyms() -> Dict:
    """从 JSON 加载同义词表，失败时返回空结构。"""
    try:
        with open(_SYNONYM_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"intent_aliases": {}, "query_expansions": {}, "disambiguation_rules": {}}


# ── 运行时加载 ──
_SYNONYM_DATA = _load_synonyms()


# 构建扁平化的 别名→标准术语 映射表（兼容旧接口）
def _build_alias_map(synonym_data: Dict) -> Dict[str, str]:
    alias_map = {}
    for standard, aliases in synonym_data.get("intent_aliases", {}).items():
        for alias in aliases:
            alias_map[alias] = standard
    return alias_map


USER_EXPRESSION_ALIASES: Dict[str, str] = _build_alias_map(_SYNONYM_DATA)

# 需要上下文消歧的高歧义词（手动补充 + 从 disambiguation_rules 动态收集）
VAGUE_TERMS: List[str] = [
    "卡住了", "卡", "挂了", "死了", "不动", "没反应", "异常", "不行",
    "用不了", "崩了", "掉了", "断了",
]


def _safe_replace(text: str, alias: str, standard: str) -> str:
    """安全替换：单字中文别名仅在非词中位置替换，避免子串误伤（如"虾仁"→"claw仁"）。"""
    if len(alias) == 1 and "\u4e00" <= alias <= "\u9fff":
        result = []
        i = 0
        while i < len(text):
            idx = text.find(alias, i)
            if idx == -1:
                result.append(text[i:])
                break
            prev_char = text[idx - 1] if idx > 0 else ""
            # 如果前一个字符也是中文字符，视为词中字符，跳过不替换
            if idx > 0 and "\u4e00" <= prev_char <= "\u9fff":
                result.append(text[i : idx + 1])
                i = idx + 1
            else:
                result.append(text[i:idx])
                result.append(standard)
                i = idx + len(alias)
        return "".join(result)
    # 多字别名直接全局替换（调用方已按长度降序保证长词优先）
    return text.replace(alias, standard)


def normalize_user_expression(text: str) -> str:
    """将用户口语化表达映射为标准术语，返回映射后的文本。

    安全策略：
    - 长度 >= 2 的别名直接替换
    - 单字中文别名仅在词边界替换（避免"虾仁"被误替换为"claw仁"）
    - 按别名长度降序排列，优先匹配长词（"小龙虾"先于"虾"）
    """
    normalized = text
    sorted_aliases = sorted(
        USER_EXPRESSION_ALIASES.items(), key=lambda x: len(x[0]), reverse=True
    )
    for alias, standard in sorted_aliases:
        normalized = _safe_replace(normalized, alias, standard)
    return normalized


def expand_for_intent_detection(text: str) -> str:
    """生成用于意图检测的扩展文本（原始 + 映射后），提高召回率。
    格式: "原始文本 [别名映射: 映射后文本]"

    单字别名（如"虾"）不会直接破坏原文，但会在附加文本中体现。
    """
    normalized = normalize_user_expression(text)
    if normalized == text:
        return text
    return f"{text} [别名映射: {normalized}]"


def expand_for_kb_search(text: str) -> str:
    """为知识库检索扩展查询，把 query_expansions 中的同义词追加到查询中。

    不改变原文语义，只是让检索系统同时命中"价格"和"会员套餐"等关联词。
    返回扩展后的查询字符串（原始查询 + 同义词，空格分隔）。
    """
    expansions = _SYNONYM_DATA.get("query_expansions", {})
    extra_terms = []
    # 按长度降序，优先匹配长词，避免短词在长词子串上误匹配（如"99"匹配"199"）
    sorted_expansions = sorted(expansions.items(), key=lambda x: len(x[0]), reverse=True)
    matched_positions = set()
    for alias, standards in sorted_expansions:
        start = 0
        while True:
            idx = text.find(alias, start)
            if idx == -1:
                break
            end = idx + len(alias)
            # 检查是否与已匹配区间重叠
            if not any(i in matched_positions for i in range(idx, end)):
                for std in standards:
                    if std not in text and std not in extra_terms:
                        extra_terms.append(std)
                matched_positions.update(range(idx, end))
            start = end
    if not extra_terms:
        return text
    return f"{text} {' '.join(extra_terms)}"


def get_disambiguation_rules() -> Dict:
    """获取消歧规则（供 Disambiguator 使用）。"""
    return _SYNONYM_DATA.get("disambiguation_rules", {})


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
            h["content"] for h in history[-6:] if h.get("role") == "user"
        ]
        all_recent_text = " ".join(recent_user_msgs)
        normalized_recent = normalize_user_expression(all_recent_text)

        # ── 从历史推断产品类型 ──
        if not result["inferred_product_type"]:
            if any(
                w in normalized_recent for w in {"desktop", "本地", "电脑", "finder", "访达"}
            ):
                result["inferred_product_type"] = "desktop"
                result["reasoning"] += "历史上下文涉及 Desktop; "
            elif any(
                w in normalized_recent for w in {"android", "安卓", "手机", "dashboard", "权限"}
            ):
                result["inferred_product_type"] = "android"
                result["reasoning"] += "历史上下文涉及 Android; "
            elif any(
                w in normalized_recent for w in {"群聊", "conductor", "thread", "群规"}
            ):
                result["inferred_product_type"] = "群聊"
                result["reasoning"] += "历史上下文涉及群聊; "
            elif any(
                w in normalized_recent for w in {"云端", "网页", "app", "kimi.com", "web ssh"}
            ):
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
