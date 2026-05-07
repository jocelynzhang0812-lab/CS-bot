"""统一配置加载器
从 config/submission_rules.yaml 加载入表规则、意图关键词、路由动作。
若 YAML 文件缺失或损坏，自动回退到内置默认配置，保证服务可用。
"""
import os
from typing import Any, Dict, List


# ── 内置默认配置（Fallback）─────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "submission_rules": {
        "must_submit": [
            {
                "name": "tech_bug",
                "description": "Kimi Claw 技术故障（信息收集完整）",
                "conditions": ["intent == tech_bug", "collected_complete == true"],
                "issue_type": "bug",
                "scene": "技术故障",
                "required_fields": ["product_type", "issue_desc", "time"],
                "table_write": True,
                "human_handoff": False,
            },
            {
                "name": "tech_bug_max_rounds",
                "description": "Kimi Claw 技术故障（已达最大追问轮次，强制入表）",
                "conditions": ["intent == tech_bug", "max_rounds_reached == true"],
                "issue_type": "bug",
                "scene": "技术故障（信息不完整）",
                "required_fields": [],
                "table_write": True,
                "human_handoff": False,
            },
            {
                "name": "human_request",
                "description": "用户主动要求转人工",
                "conditions": ["intent == human_request"],
                "issue_type": "human_request",
                "scene": "用户主动要求转人工",
                "required_fields": ["product_type", "issue_desc"],
                "table_write": True,
                "human_handoff": True,
            },
            {
                "name": "wrong_answer",
                "description": "用户反馈回答错误",
                "conditions": ["intent == wrong_answer"],
                "issue_type": "wrong_answer",
                "scene": "用户反馈回答错误",
                "required_fields": ["product_type", "issue_desc"],
                "table_write": True,
                "human_handoff": False,
            },
            {
                "name": "follow_up",
                "description": "续跟（问题未解决）",
                "conditions": ["is_follow_up == true"],
                "issue_type": "bug",
                "scene": "续跟",
                "required_fields": [],
                "table_write": True,
                "human_handoff": False,
            },
        ],
        "must_not_submit": [
            {
                "name": "special_request",
                "description": "退款/开票/封禁等特殊请求",
                "conditions": ["is_special == true"],
                "table_write": False,
                "human_handoff": True,
            },
            {
                "name": "kb_hit",
                "description": "知识库命中直接解决",
                "conditions": ["kb_hit == true"],
                "table_write": False,
                "human_handoff": False,
            },
            {
                "name": "self_check_resolved",
                "description": "自助检查后已解决",
                "conditions": ["self_check_resolved == true"],
                "table_write": False,
                "human_handoff": False,
            },
        ],
    },
    "intent_keywords": {
        "special": ["退款", "退钱", "退token", "退费", "开票", "发票", "报销", "封禁", "封号", "非claw", "kimi主站"],
        "human_request": ["转人工", "找人工", "要人工", "人工客服", "找真人", "找客服", "接人工", "换人", "人工"],
        "wrong_answer": [
            "回答错误", "你说错了", "不对", "错了", "答非所问", "没回答我的问题",
            "文不对题", "胡说", "乱说", "瞎说", "你搞错了", "理解错了",
            "回答不对", "说错了", "答错了", "你说得不对", "不是这样的",
        ],
        "emotion": ["太差了", "垃圾", "愤怒", "生气", "投诉", "坑爹", "废物", "破", "火大", "烦躁"],
        "version_schedule": ["版本", "排期", "上线时间", "什么时候上", "多久上线", "openclaw 版本", "更新计划"],
    },
    "router_actions": {
        "human_request": "human_handoff_with_table",
        "wrong_answer": "wrong_answer_table",
        "special_request": "human_handoff",
        "version_schedule": "human_handoff",
        "tech_bug_complete": "bug_report",
        "tech_bug_incomplete": "clarify",
        "default": "clarify",
    },
}


# ── 单例缓存 ────────────────────────────────────────────────────────────────
_config_cache: Dict[str, Any] = {}


def _load_yaml(path: str) -> Dict:
    """加载 YAML 文件，失败时返回空字典"""
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def get_config() -> Dict[str, Any]:
    """获取完整配置（带缓存）。优先读 YAML，失败回退到内置默认。"""
    global _config_cache
    if _config_cache:
        return _config_cache

    # 尝试从项目根目录的 config/submission_rules.yaml 加载
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    yaml_path = os.path.join(project_root, "config", "submission_rules.yaml")

    loaded = _load_yaml(yaml_path)

    if loaded and "submission_rules" in loaded:
        _config_cache = loaded
    else:
        # 回退到内置默认
        _config_cache = dict(DEFAULT_CONFIG)

    return _config_cache


def get_submission_rules() -> Dict[str, List[Dict]]:
    """返回入表规则 {must_submit: [...], must_not_submit: [...]}"""
    return get_config().get("submission_rules", DEFAULT_CONFIG["submission_rules"])


def get_intent_keywords() -> Dict[str, List[str]]:
    """返回意图关键词 {special: [...], human_request: [...], wrong_answer: [...], emotion: [...]}"""
    return get_config().get("intent_keywords", DEFAULT_CONFIG["intent_keywords"])


def get_router_actions() -> Dict[str, str]:
    """返回路由动作映射 {intent: action}"""
    return get_config().get("router_actions", DEFAULT_CONFIG["router_actions"])


def should_submit(intent: str, collected_complete: bool = False, **context) -> Dict:
    """
    判断给定意图是否应该入表。

    返回结构:
    {
        "should_submit": bool,
        "rule_name": str,
        "issue_type": str,
        "scene": str,
        "human_handoff": bool,
        "reason": str,
    }
    """
    rules = get_submission_rules()

    # 先检查 must_not_submit（否决规则优先）
    for rule in rules.get("must_not_submit", []):
        if _match_conditions(rule.get("conditions", []), intent, collected_complete, **context):
            return {
                "should_submit": False,
                "rule_name": rule["name"],
                "issue_type": "",
                "scene": "",
                "human_handoff": rule.get("human_handoff", False),
                "reason": f"匹配 must_not_submit 规则: {rule['description']}",
            }

    # 再检查 must_submit
    for rule in rules.get("must_submit", []):
        if _match_conditions(rule.get("conditions", []), intent, collected_complete, **context):
            return {
                "should_submit": True,
                "rule_name": rule["name"],
                "issue_type": rule.get("issue_type", ""),
                "scene": rule.get("scene", ""),
                "human_handoff": rule.get("human_handoff", False),
                "reason": f"匹配 must_submit 规则: {rule['description']}",
            }

    # 默认不入表
    return {
        "should_submit": False,
        "rule_name": "default",
        "issue_type": "",
        "scene": "",
        "human_handoff": False,
        "reason": "未匹配任何入表规则，默认不入表",
    }


def _match_conditions(conditions: List[str], intent: str, collected_complete: bool, **context) -> bool:
    """简单条件匹配器。条件列表为 AND 关系，每项内部也支持 " and "。
    支持格式:
    - ["intent == xxx", "collected_complete == true"]  → 两者必须同时满足
    - ["intent == xxx and collected_complete == true"] → 同上
    - ["is_follow_up == true"]
    """
    ctx = {
        "intent": intent,
        "collected_complete": collected_complete,
        **context,
    }

    for cond in conditions:
        parts = [p.strip() for p in cond.split(" and ")]
        for part in parts:
            if "==" not in part:
                continue
            left, right = part.split("==", 1)
            left = left.strip()
            right = right.strip().strip('"').strip("'")
            val = ctx.get(left)
            # 布尔值转换
            if right.lower() == "true":
                right = True
            elif right.lower() == "false":
                right = False
            if str(val) != str(right):
                return False
    return True
