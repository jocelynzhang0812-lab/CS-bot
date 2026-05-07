from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict


class CSFollowUpSOP(BaseTool):
    def __init__(self):
        super().__init__("cs_follow_up_sop", "续跟记录规则")
        self.trigger_words = {"没解决", "无效", "还是不行", "没用", "不好使", "仍然", "依旧", "又坏了", "问题未解决", "方案无效"}

    async def execute(self, user_message: str, original_record: Dict, **kwargs) -> ToolResult:
        msg = user_message.lower()
        triggered = any(w in msg for w in self.trigger_words)

        if not triggered:
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, result={"needs_follow_up": False})

        follow_up = {
            "feedback_time": original_record.get("反馈时间", ""),
            "feedback_source": original_record.get("反馈来源", ""),
            "user_id": original_record.get("用户ID", ""),
            "session_id": original_record.get("会话ID", ""),
            "issue_type": "bug",
            "skill": original_record.get("涉及Skill", ""),
            "error_info": f"【续跟】{original_record.get('关键错误信息', '')}",
            "screenshot": "",
            "bot_id": original_record.get("Bot ID", ""),
            "deploy_method": original_record.get("部署方式", ""),
            "bot_status": original_record.get("Bot 状态", ""),
            "self_check": f"已执行前序方案：{original_record.get('修复方案', '无')}，用户反馈无效",
            "scene": original_record.get("场景分类", ""),
            "diag_detail": "",
            "platform_tag": original_record.get("平台特定标记", ""),
            "status": "待处理",
            "parent_record_id": original_record.get("#id"),
        }

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "needs_follow_up": True,
                "follow_up_fields": follow_up,
                "user_reply": "了解，我已重新为您提交，技术团队会进一步跟进。",
            },
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {"user_message": {"type": "string"}, "original_record": {"type": "object"}}