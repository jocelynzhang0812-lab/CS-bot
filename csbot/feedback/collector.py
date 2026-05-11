"""通用反馈收集器 —— 每条用户消息自动入表

用 JSON Schema 约束输出结构，避免模型自由发挥：
{
  "feedback_type": "功能异常 | 配置问题 | 使用咨询 | 其他",
  "user_description": "原文摘录",
  "affected_feature": "模型识别的功能模块，不确定填null",
  "resolution_status": "已解答 | 知识库未收录 | 需人工跟进"
}

扩展字段（代码层自动填充）：
  "product_type", "detected_intent", "kb_hit", "session_id", "user_id", "bot_reply", "created_at"
"""

from datetime import datetime
from typing import Any, Dict

from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from csbot.sops.bitable import BitableClient


FEEDBACK_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["feedback_type", "user_description", "resolution_status"],
    "properties": {
        "feedback_type": {
            "type": "string",
            "enum": ["功能异常", "配置问题", "使用咨询", "其他"],
            "description": "反馈类型分类",
        },
        "user_description": {
            "type": "string",
            "description": "用户原话摘录",
        },
        "affected_feature": {
            "type": ["string", "null"],
            "description": "影响的功能模块，不确定填 null",
        },
        "resolution_status": {
            "type": "string",
            "enum": ["已解答", "知识库未收录", "需人工跟进"],
            "description": "当前问题的处理状态",
        },
        "product_type": {
            "type": "string",
            "description": "识别到的产品类型",
        },
        "detected_intent": {
            "type": "string",
            "description": "意图识别结果",
        },
        "kb_hit": {
            "type": "boolean",
            "description": "是否命中知识库",
        },
        "session_id": {"type": "string"},
        "user_id": {"type": "string"},
        "bot_reply": {
            "type": "string",
            "description": "Bot 最终回复摘要（前200字）",
        },
        "created_at": {
            "type": "string",
            "description": "收录时间 ISO 格式",
        },
    },
}


class CSFeedbackCollectorSkill(BaseTool):
    """通用反馈收集器：将每条用户交互结构化写入飞书多维表格。"""

    VALID_FEEDBACK_TYPES = {"功能异常", "配置问题", "使用咨询", "其他"}
    VALID_RESOLUTION_STATUS = {"已解答", "知识库未收录", "需人工跟进"}

    def __init__(self, bitable: BitableClient):
        super().__init__(
            "cs_feedback_collector",
            "收集用户反馈并写入通用反馈表格。每条消息自动调用一次。",
        )
        self.bitable = bitable

    def _validate(self, data: Dict) -> Dict:
        """强制校验并修复字段，确保符合 JSON Schema。"""
        ft = data.get("feedback_type", "其他")
        if ft not in self.VALID_FEEDBACK_TYPES:
            ft = "其他"

        rs = data.get("resolution_status", "需人工跟进")
        if rs not in self.VALID_RESOLUTION_STATUS:
            rs = "需人工跟进"

        return {
            "feedback_type": ft,
            "user_description": str(data.get("user_description", ""))[:2000],
            "affected_feature": data.get("affected_feature") or "未识别",
            "resolution_status": rs,
            "product_type": str(data.get("product_type", ""))[:100] or "未识别",
            "detected_intent": str(data.get("detected_intent", ""))[:100],
            "kb_hit": bool(data.get("kb_hit", False)),
            "session_id": str(data.get("session_id", ""))[:200],
            "user_id": str(data.get("user_id", ""))[:200],
            "bot_reply": str(data.get("bot_reply", ""))[:500],
            "created_at": data.get("created_at") or datetime.now().isoformat(),
        }

    async def execute(
        self,
        feedback_type: str = "其他",
        user_description: str = "",
        affected_feature: str = "",
        resolution_status: str = "需人工跟进",
        product_type: str = "",
        detected_intent: str = "",
        kb_hit: bool = False,
        session_id: str = "",
        user_id: str = "",
        bot_reply: str = "",
        **kwargs,
    ) -> ToolResult:
        """执行反馈收集并写入表格。

        参数经过 JSON Schema 严格约束（enum + type），
        代码层再次硬校验，防止 LLM 输出自由格式。
        """
        raw = {
            "feedback_type": feedback_type,
            "user_description": user_description,
            "affected_feature": affected_feature,
            "resolution_status": resolution_status,
            "product_type": product_type,
            "detected_intent": detected_intent,
            "kb_hit": kb_hit,
            "session_id": session_id,
            "user_id": user_id,
            "bot_reply": bot_reply,
            "created_at": datetime.now().isoformat(),
        }

        # 硬校验：确保输出严格符合 JSON Schema
        validated = self._validate(raw)

        # 构建飞书多维表格字段（中文列名，与表格结构对齐）
        fields = {
            "反馈类型": validated["feedback_type"],
            "用户描述": validated["user_description"],
            "影响功能": validated["affected_feature"],
            "处理状态": validated["resolution_status"],
            "产品类型": validated["product_type"],
            "识别意图": validated["detected_intent"],
            "知识库命中": "是" if validated["kb_hit"] else "否",
            "会话ID": validated["session_id"],
            "用户ID": validated["user_id"],
            "Bot回复摘要": validated["bot_reply"],
            "收录时间": validated["created_at"],
        }

        try:
            result = await self.bitable.upsert_raw(fields=fields)
            if result.get("code") == 0:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    result={
                        "submitted": True,
                        "record_id": result.get("data", {}).get("record", {}).get("record_id", ""),
                        "fields": validated,
                    },
                )
            else:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.FAILED,
                    result={"submitted": False, "error": result.get("msg", "写入失败"), "code": result.get("code")},
                    error_message=result.get("msg", "写入反馈表格失败"),
                )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.FAILED,
                result={"submitted": False, "error": str(e)},
                error_message=f"反馈收集异常: {e}",
            )

    def _get_parameters(self) -> Dict[str, Any]:
        """返回 OpenAI Function Calling Schema —— 用 enum 约束 LLM 输出。"""
        return {
            "feedback_type": {
                "type": "string",
                "enum": ["功能异常", "配置问题", "使用咨询", "其他"],
                "description": "反馈类型：功能异常 / 配置问题 / 使用咨询 / 其他",
            },
            "user_description": {
                "type": "string",
                "description": "用户原话摘录（原文）",
            },
            "affected_feature": {
                "type": ["string", "null"],
                "description": "影响的功能模块，不确定填 null",
            },
            "resolution_status": {
                "type": "string",
                "enum": ["已解答", "知识库未收录", "需人工跟进"],
                "description": "处理状态：已解答 / 知识库未收录 / 需人工跟进",
            },
            "product_type": {"type": "string", "optional": True},
            "detected_intent": {"type": "string", "optional": True},
            "kb_hit": {"type": "boolean", "optional": True},
            "session_id": {"type": "string", "optional": True},
            "user_id": {"type": "string", "optional": True},
            "bot_reply": {"type": "string", "optional": True},
        }
