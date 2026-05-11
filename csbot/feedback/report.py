from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict


class CSBugReportSkill(BaseTool):
    """Bug 结构化上报，生成飞书卡片并准备多维表格字段。
    支持多种 issue_type：bug / human_request / wrong_answer / follow_up"""

    def __init__(self):
        super().__init__("cs_bug_report", "提交 Bug 记录")

    async def execute(self, collected: Dict, issue_type: str = "bug", **kwargs) -> ToolResult:
        title_map = {
            "bug": "新 Bug 上报",
            "human_request": "用户要求转人工",
            "wrong_answer": "用户反馈回答错误",
            "follow_up": "续跟记录",
        }
        title = title_map.get(issue_type, "新记录上报")

        card_markdown = (
            f"**{title}**\n"
            f"- 产品类型: {collected.get('product_type', '未填写')}\n"
            f"- Bot ID: {collected.get('bot_id', '未填写')}\n"
            f"- 问题描述: {collected.get('issue_desc', '未填写')}\n"
            f"- 发生时间: {collected.get('time', '未填写')}\n"
            f"- 自助检查: {collected.get('self_check', '无')}\n"
            f"- 复现步骤: {collected.get('repro_steps', '无')}\n"
        )
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "card_markdown": card_markdown,
                "fields": collected,
                "issue_type": issue_type,
                "submitted": True,
            },
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "collected": {"type": "object", "description": "已收集的 Bug 信息字段"},
            "issue_type": {"type": "string", "default": "bug", "description": "记录类型：bug / human_request / wrong_answer / follow_up"},
        }
