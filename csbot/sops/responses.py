from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict


class CSResponseTemplatesSkill(BaseTool):
    """标准话术模板"""

    def __init__(self):
        super().__init__("cs_response_templates", "标准话术模板")

    async def execute(self, template_type: str, **kwargs) -> ToolResult:
        templates = {
            "refund": (
                "关于退款，您可以通过以下方式处理：\n\n"
                "退订会员服务：退订当前选定的自动续费服务。成功退订后，该自动续费服务到期后将不再续订，但不影响当期有效权益。\n\n"
                "常见路径（以页面实际展示为准）：\n【首页】→【设置页】→【订阅】→【取消订阅】\n\n"
                "会员权益相关咨询：membership@moonshot.cn\n客服同学会进一步核实处理。"
            ),
            "invoice": (
                "您可以自助开具发票，路径如下：\n"
                "APP/网页 →【我的账户】→【管理-订阅】→【账单】→【开发票】\n\n"
                "如遇问题欢迎随时告诉我。"
            ),
            "out_of_scope": (
                "抱歉，这个问题不在 Kimi 的服务范围内。如果您使用的是第三方产品，请联系对应服务商。"
            ),
            "submitted": "感谢您提供的信息，我已提交给技术团队排查，请耐心等待，有进展我会第一时间通知您。",
            "resolved": "好消息！您反馈的问题已经修复，{detail}。您可以重新尝试，如还有问题随时告诉我。",
            "unresolvable": "非常抱歉，经过技术团队评估，您遇到的问题暂时无法自动修复。{reason}。如有其他疑问我随时在这里。",
            "human_escalation": "您的问题需要人工客服进一步协助，我已通知相关同学，请稍候。",
            "timeout": "您反馈的问题仍在排查中，感谢您的耐心等待，我们会尽快给您结果。",
            "follow_up": "了解，我已重新为您提交，技术团队会进一步跟进。",
            "human_request_submitted": "已记录您的请求，正在为您转接人工客服，请稍候。",
            "wrong_answer_submitted": "抱歉给您带来困扰，我已记录该问题并提交复盘，正确的信息会尽快同步给您。",
            "product_feedback_submitted": "感谢您的宝贵建议！我已记录下来并同步给产品团队，有进展会第一时间通知您。",
            "injection": "抱歉，我只能帮您处理 Kimi 相关产品的问题，其他请求超出了我的服务范围。",
            "internal_leak": "抱歉，这部分信息我无法提供。",
            "kitty_refusal": "抱歉，这个问题不在 Kimi 的服务范围内。",
            "identity_probe": "抱歉，我只能帮您处理 Kimi 相关产品的问题，其他请求超出了我的服务范围。",
            "third_party_claw": "抱歉，这个问题不在 Kimi 的服务范围内。Kimi 没有该产品，如果您使用的是第三方 Claw，请联系对应服务商。",
            "kb_miss": "抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。",
            "version_schedule": "关于版本更新和排期的具体信息，建议您联系人工客服或产品经理获取最新动态。",
            "direct_answer_prompt": "我会直接给出准确答案，不过度搜索。",
        }

        text = templates.get(template_type, "")
        if "{detail}" in text:
            text = text.format(detail=kwargs.get("detail", "请按建议方案操作"))
        if "{reason}" in text:
            text = text.format(reason=kwargs.get("reason", "具体原因请见替代方案"))

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={"reply": text, "template_type": template_type},
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {"template_type": {"type": "string"}}
