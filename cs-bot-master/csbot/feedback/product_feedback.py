"""产品建议收集与写入飞书多维表格"""
from datetime import datetime
from typing import Any, Dict

from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from csbot.sops.bitable import BitableClient


class CSProductFeedbackSkill(BaseTool):
    """收集用户产品建议并写入 Kimi Claw 产品建议多维表格。

    目标表格字段：
    - 建议内容 (Text, 主键)
    - 建议类型 (SingleSelect: 功能建议 / Bug反馈 / 体验优化 / 其他)
    - 优先级   (SingleSelect: P0-紧急 / P1-高 / P2-中 / P3-低)
    - 处理状态 (SingleSelect: 待评估 / 已采纳 / 已排期 / 已实现 / 已拒绝)
    - 提交时间 (DateTime)
    """

    def __init__(self, bitable: BitableClient, app_token: str, table_id: str):
        super().__init__("submit_product_feedback", "提交产品建议")
        self.bitable = bitable
        self.app_token = app_token
        self.table_id = table_id

    async def execute(
        self,
        content: str,
        feedback_type: str = "其他",
        priority: str = "P2 - 中",
        user_id: str = "",
        session_id: str = "",
        **kwargs,
    ) -> ToolResult:
        # 校验建议类型
        valid_types = {"功能建议", "Bug 反馈", "体验优化", "其他"}
        if feedback_type not in valid_types:
            feedback_type = "其他"

        # 校验优先级
        valid_priority = {"P0 - 紧急", "P1 - 高", "P2 - 中", "P3 - 低"}
        if priority not in valid_priority:
            priority = "P2 - 中"

        # 构建日期时间戳（飞书 DateTime 字段要求毫秒时间戳）
        submit_timestamp = int(datetime.now().timestamp() * 1000)

        fields = {
            "建议内容": content,
            "建议类型": feedback_type,
            "优先级": priority,
            "处理状态": "待评估",
            "提交时间": submit_timestamp,
        }

        result = await self.bitable.create_raw(
            fields=fields,
            app_token=self.app_token,
            table_id=self.table_id,
        )

        if result.get("code") == 0:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "submitted": True,
                    "record_id": result.get("data", {}).get("record", {}).get("record_id", ""),
                    "fields": fields,
                    "reply": "感谢您的宝贵建议！我已记录下来并同步给产品团队，有进展会第一时间通知您。",
                },
            )
        else:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                result={"submitted": False, "error": result.get("msg", "未知错误")},
                error_message=result.get("msg", "写入产品建议表格失败"),
            )

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "content": {"type": "string", "description": "用户的建议内容"},
            "feedback_type": {
                "type": "string",
                "default": "其他",
                "description": "建议类型：功能建议 / Bug 反馈 / 体验优化 / 其他",
            },
            "priority": {
                "type": "string",
                "default": "P2 - 中",
                "description": "优先级：P0 - 紧急 / P1 - 高 / P2 - 中 / P3 - 低",
            },
            "user_id": {"type": "string", "optional": True},
            "session_id": {"type": "string", "optional": True},
        }
