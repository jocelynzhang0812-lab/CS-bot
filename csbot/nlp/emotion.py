from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict


class CSEmotionSkill(BaseTool):
    """情绪识别与安抚。覆盖显性愤怒和隐性负面反馈。"""

    def __init__(self):
        super().__init__("cs_emotion", "情绪识别与安抚")
        self.strong = {"太差了", "垃圾", "废物", "坑爹", "投诉", "愤怒", "火大", "退费", "退款", "无语", "服了", "离谱"}
        self.moderate = {"生气", "不满", "失望", "郁闷", "烦躁", "解决不了", "没用", "不行", "尴尬", "不太对", "不对劲", "不行啊"}
        self.negative_feedback = {"有点尴尬", "无语了", "不太对", "不对劲", "不太行", "好像不行", "没用啊", "还是不行", "没解决"}

    async def execute(self, user_message: str, **kwargs) -> ToolResult:
        msg = user_message
        sc = sum(1 for w in self.strong if w in msg)
        mc = sum(1 for w in self.moderate if w in msg)
        ex = msg.count("!") + msg.count("！")
        nf = sum(1 for w in self.negative_feedback if w in msg)

        if sc >= 2 or ex >= 3 or any(w in msg for w in {"投诉", "退费", "退款"}):
            level, reply = 5, "非常抱歉给您带来了困扰，我完全理解您现在的心情。我会立刻帮您跟进这个问题，请您稍等片刻。"
        elif sc >= 1 or ex >= 2 or mc >= 2 or nf >= 1:
            level, reply = 4, "非常抱歉给您带来了困扰，我完全理解您现在的心情。我会立刻帮您跟进这个问题，请您稍等片刻。"
        elif mc >= 1 or ex >= 1:
            level, reply = 3, "理解您的困扰，我们一起排查一下。"
        else:
            level, reply = 1, ""

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "level": level,
                "needs_comfort": level >= 3,
                "comfort_reply": reply,
                "needs_escalation": level >= 4,
                "needs_quick_compensation": nf >= 1 or sc >= 1,
            },
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {"user_message": {"type": "string"}}
