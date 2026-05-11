"""实体消歧引擎

解决"群"、"机器人"、"管理员"等歧义词在不同语境下的指向问题。
核心原则：不做破坏性字符串替换，只输出结构化消歧结果供上层决策使用。
"""
import json
import os
from typing import Dict, List

from csbot.nlp.aliases import get_disambiguation_rules


# 内置追问模板（key 与 disambiguation_rules 中的歧义词对应）
CLARIFY_TEMPLATES: Dict[str, str] = {
    "群": (
        "请问您提到的「群」是指：\n"
        "A. Claw 产品内的群聊功能\n"
        "B. 需要人工客服协助处理\n"
        "请回复 A 或 B，我来为您准确解答。"
    ),
    "机器人": (
        "请问您说的「机器人」是指：\n"
        "A. 您配置的 Claw Bot\n"
        "B. 我（客服助手）\n"
        "请回复 A 或 B。"
    ),
    "管理员": (
        "请问您提到的「管理员」是指：\n"
        "A. Bot 的配置管理员\n"
        "B. 企业微信/飞书等平台的组织管理员\n"
        "请回复 A 或 B。"
    ),
}


class DisambiguationResult:
    """消歧结果对象，便于后续代码访问。"""

    def __init__(
        self,
        resolved_entities: List[Dict],
        needs_clarify: bool = False,
        clarify_term: str = "",
        clarify_message: str = "",
    ):
        self.resolved_entities = resolved_entities
        self.needs_clarify = needs_clarify
        self.clarify_term = clarify_term
        self.clarify_message = clarify_message

    def get_resolved(self, term: str) -> Dict:
        """获取指定歧义词的消歧结果。"""
        for r in self.resolved_entities:
            if r.get("term") == term:
                return r
        return {}

    def to_dict(self) -> Dict:
        return {
            "resolved_entities": self.resolved_entities,
            "needs_clarify": self.needs_clarify,
            "clarify_term": self.clarify_term,
            "clarify_message": self.clarify_message,
        }


class Disambiguator:
    """基于规则的信号词打分消歧器。

    对文本中的每个歧义词，统计各候选实体的信号词命中数，按阈值判定置信度：
    - high  (>= 2 个信号词): 直接确定实体
    - medium(1 个信号词):   直接确定实体，但记录日志备查
    - low   (0 个信号词):   无法确定，触发追问或使用默认值
    """

    def __init__(self, rules: Dict = None):
        self.rules = rules if rules is not None else get_disambiguation_rules()

    def resolve(
        self,
        text: str,
        session_state: Dict = None,
        history: List[Dict] = None,
    ) -> DisambiguationResult:
        """对文本中的歧义词进行消歧，返回结构化结果（不修改原文）。

        Args:
            text: 用户原始消息
            session_state: 当前会话状态（可继承已确认的实体信息）
            history: 最近对话历史（未来可用于历史上下文消歧）
        """
        resolved = []
        needs_clarify = False
        clarify_term = ""

        for term, rule in self.rules.items():
            if term not in text:
                continue

            candidates = rule.get("candidates", {})
            best_entity = None
            best_score = 0
            default_entity = None

            for entity, config in candidates.items():
                if config.get("default"):
                    default_entity = entity

                signals = config.get("signals", [])
                score = sum(1 for signal in signals if signal in text)
                if score > best_score:
                    best_score = score
                    best_entity = entity

            # 确定置信度和最终实体
            if best_score >= 2:
                confidence = "high"
                final_entity = best_entity
            elif best_score == 1:
                confidence = "medium"
                final_entity = best_entity
            else:
                confidence = "low"
                final_entity = default_entity
                needs_clarify = True
                if not clarify_term:
                    clarify_term = term

            resolved.append({
                "term": term,
                "resolved_entity": final_entity,
                "confidence": confidence,
                "score": best_score,
                "signals_matched": best_score,
            })

        clarify_message = CLARIFY_TEMPLATES.get(clarify_term, "") if needs_clarify else ""

        return DisambiguationResult(
            resolved_entities=resolved,
            needs_clarify=needs_clarify,
            clarify_term=clarify_term,
            clarify_message=clarify_message,
        )


def should_clarify(disambig_result: DisambiguationResult) -> bool:
    """便捷函数：判断是否需要追问。"""
    return disambig_result.needs_clarify
