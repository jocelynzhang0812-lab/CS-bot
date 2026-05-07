from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict


class CSGuardrailsSkill(BaseTool):
    """防指令注入、拒绝话术、输出规范校验"""

    def __init__(self):
        super().__init__("cs_guardrails", "安全与输出规范")
        self.injection_patterns = {
            "忽略以上", "现在你是", "system:", "</s>", "新指令", "忽略前面", "forget",
            "你是", "变成", "扮演", "切换模式", "debug", "测试模式", "开发者模式",
        }
        self.identity_probe_patterns = {
            "你是谁", "你是什么", "你是kimi", "你是claw", "你是openclaw", "你是kitty",
            "你的身份", "你的模型", "你的底层", "你叫啥", "你叫什么",
        }
        self.kitty_patterns = {
            "kitty", " Kitty", "kitty是什么", "什么是kitty", "Kitty是什么", "什么是Kitty",
        }
        self.third_party_claw_patterns = {
            "jsv claw", "jsvclaw", "第三方 openclaw", "其他公司的 claw", "别的公司的 claw",
            "openclaw 不是 kimi", "非 kimi 的 claw",
            # 与 Kimi Claw 无关的第三方产品（严禁误判）
            "apkclaw", "clawra", "oneclaw", "moltbook", "workbuddy", "qclaw", "skyclaw",
        }
        self.internal_leak_patterns = {
            "多维表格", "feedback bot", "工单", "研发", "后台", "架构", "framework",
            "skill", "提示词", "prompt", "系统提示", "内部工具", "airtable", "bitable",
            "kitty", "kitty框架", "kitty系统", "kitty架构",
        }
        self.max_length = 200

    async def execute(self, user_message: str, bot_reply: str = "", **kwargs) -> ToolResult:
        m = user_message.lower()

        # 第三方 Claw（如 JSV Claw）——不是 Kimi 产品，禁止追问
        if any(p in m for p in self.third_party_claw_patterns):
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "blocked": True,
                    "reason": "third_party_claw",
                    "reply": "抱歉，这个问题不在 Kimi 的服务范围内。Kimi 没有该产品，如果您使用的是第三方 Claw，请联系对应服务商。",
                },
            )

        # Kitty 相关提问（绝对禁止回答）
        if any(p.lower() in m for p in self.kitty_patterns):
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "blocked": True,
                    "reason": "kitty_refusal",
                    "reply": "抱歉，这个问题不在 Kimi 的服务范围内。",
                },
            )

        # 身份探针（你是谁/你是什么模型等）
        if any(p in m for p in self.identity_probe_patterns):
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "blocked": True,
                    "reason": "identity_probe",
                    "reply": "抱歉，我只能帮您处理 Kimi 相关产品的问题，其他请求超出了我的服务范围。",
                },
            )

        # 指令注入
        if any(p in m for p in self.injection_patterns):
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "blocked": True,
                    "reason": "injection",
                    "reply": "抱歉，我只能帮您处理 Kimi 相关产品的问题，其他请求超出了我的服务范围。",
                },
            )

        # 套取内部信息
        if any(p in m for p in {"披露", "复述", "翻译", "skill内容", "你的设定", "你怎么工作的", "后台怎么实现"}):
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "blocked": True,
                    "reason": "internal_leak",
                    "reply": "抱歉，这部分信息我无法提供。",
                },
            )

        # 输出规范校验
        checked_reply = bot_reply
        violations = []
        if any(p in checked_reply.lower() for p in self.internal_leak_patterns):
            violations.append("contains_internal_terms")
            checked_reply = "已提交给技术团队排查，请耐心等待。"

        if len(checked_reply) > self.max_length:
            checked_reply = checked_reply[:self.max_length] + "..."
            violations.append("length_exceeded")

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "blocked": False,
                "reply": checked_reply,
                "violations": violations,
            },
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {"user_message": {"type": "string"}, "bot_reply": {"type": "string", "optional": True}}