from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict


class CSHumanHandoffSkill(BaseTool):
    """检测人工客服是否已介入，控制 CS Bot 抢话行为"""

    def __init__(self):
        super().__init__("cs_human_handoff", "人工介入协作")

    async def execute(self, recent_messages: list, bot_user_id: str = "cs_bot", **kwargs) -> ToolResult:
        """recent_messages: 最近 N 条群消息，每条含 user_id 和 text"""
        human_cs_keywords = {"人工客服", "客服专员", "已转接", "已记录"}
        human_replied = False

        for msg in recent_messages:
            uid = msg.get("user_id", "")
            text = msg.get("text", "")
            # 排除 bot 自己
            if uid == bot_user_id:
                continue
            # 简单判断：消息较长且不含常见 bot 特征，或包含人工客服关键词
            if any(k in text for k in human_cs_keywords) or len(text) > 50:
                human_replied = True
                break

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "human_intervened": human_replied,
                "bot_should_silence": human_replied,
                "resume_after_user_mentions_bot": True,
            },
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {"recent_messages": {"type": "array"}, "bot_user_id": {"type": "string", "optional": True}}