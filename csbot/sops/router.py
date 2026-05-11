from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from csbot.config.loader import get_router_actions, should_submit
from typing import Any, Dict


class CSSOPRouterSkill(BaseTool):
    """SOP 流程路由器：根据意图和状态决定下一步动作。
    路由规则从 config/submission_rules.yaml 加载，支持外部配置化。"""

    def __init__(self):
        super().__init__("cs_sop_router", "SOP 流程路由")
        self.actions = get_router_actions()

    async def execute(
        self,
        intent: str,
        kb_hit: bool = False,
        collected_complete: bool = False,
        is_special: bool = False,
        is_human_request: bool = False,
        is_wrong_answer: bool = False,
        max_rounds_reached: bool = False,
        **kwargs,
    ) -> ToolResult:
        # 从 intent 自动推断标志（兼容只传 intent 的调用方式）
        is_special = is_special or intent == "special_request"
        is_human_request = is_human_request or intent == "human_request"
        is_wrong_answer = is_wrong_answer or intent == "wrong_answer"
        is_product_feedback = kwargs.get("is_product_feedback", False) or intent == "product_feedback"
        is_version_schedule = kwargs.get("is_version_schedule", False) or intent == "version_schedule"
        is_follow_up = kwargs.get("is_follow_up", False) or intent == "follow_up"

        # 使用配置化的入表决策器
        submit_decision = should_submit(
            intent=intent,
            collected_complete=collected_complete,
            is_special=is_special,
            is_human_request=is_human_request,
            is_wrong_answer=is_wrong_answer,
            is_product_feedback=is_product_feedback,
            is_follow_up=is_follow_up,
            max_rounds_reached=max_rounds_reached,
            kb_hit=kb_hit,
        )

        # 确定 next_step
        next_step = "reply"
        if is_special:
            next_step = self.actions.get("special_request", "human_handoff")
        elif is_human_request:
            next_step = self.actions.get("human_request", "human_handoff_with_table")
        elif is_wrong_answer:
            next_step = self.actions.get("wrong_answer", "wrong_answer_table")
        elif is_product_feedback:
            next_step = self.actions.get("product_feedback", "product_feedback_table")
        elif is_version_schedule:
            next_step = self.actions.get("version_schedule", "human_handoff")
        elif is_follow_up:
            next_step = self.actions.get("follow_up", "bug_report")
        elif intent == "tech_bug" and (collected_complete or max_rounds_reached):
            next_step = self.actions.get("tech_bug_complete", "bug_report")
        elif intent == "tech_bug" and not collected_complete:
            next_step = self.actions.get("tech_bug_incomplete", "clarify")
        elif intent in ("faq", "feedback"):
            next_step = "kb_search"
        else:
            next_step = self.actions.get("default", "clarify")

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "next_step": next_step,
                "should_submit": submit_decision["should_submit"],
                "issue_type": submit_decision["issue_type"],
                "scene": submit_decision["scene"],
                "human_handoff": submit_decision["human_handoff"],
                "submit_reason": submit_decision["reason"],
            },
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "intent": {"type": "string"},
            "kb_hit": {"type": "boolean", "optional": True},
            "collected_complete": {"type": "boolean", "optional": True},
            "is_special": {"type": "boolean", "optional": True},
            "is_human_request": {"type": "boolean", "optional": True},
            "is_wrong_answer": {"type": "boolean", "optional": True},
            "max_rounds_reached": {"type": "boolean", "optional": True},
        }
