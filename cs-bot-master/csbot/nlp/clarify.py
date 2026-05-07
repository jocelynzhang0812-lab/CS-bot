from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from csbot.nlp.aliases import normalize_user_expression
from typing import Any, Dict, Optional
import re


class CSClarifySkill(BaseTool):
    """多轮信息收集。最多追问 2 轮，之后即使缺失必填字段也强制入表。"""

    MAX_CLARIFY_ROUNDS = 2

    def __init__(self):
        super().__init__("cs_clarify", "多轮信息收集")
        self.fields = [
            ("product_type", "产品类型", True),
            ("bot_id", "Bot ID", False),
            ("issue_desc", "问题描述", True),
            ("self_check", "自助检查结果", False),
            ("time", "发生时间", True),
            ("repro_steps", "复现步骤", False),
            ("screenshot", "截图", False),
        ]
        self.platforms = {"飞书", "微信", "企微", "企业微信", "钉钉", "微博", "网页", "ios", "android", "desktop"}

    async def execute(self, user_message: str, session_state: Optional[Dict] = None, **kwargs) -> ToolResult:
        state = dict(session_state) if session_state else {}
        state = self._extract(state, user_message)

        # 轮次追踪
        clarify_count = state.get("clarify_count", 0) + 1
        state["clarify_count"] = clarify_count

        missing_required = [f for f, _, req in self.fields if req and not state.get(f)]
        missing_optional = [f for f, _, req in self.fields if not req and not state.get(f)]

        # 已达最大轮次：即使必填字段缺失也强制标记为完成
        max_rounds_reached = clarify_count >= self.MAX_CLARIFY_ROUNDS
        if max_rounds_reached or not missing_required:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "is_complete": True,
                    "collected": state,
                    "next_question": None,
                    "max_rounds_reached": max_rounds_reached,
                    "missing_fields": missing_required,
                },
            )

        # 单次只问 1 个最关键字段，简化追问
        to_ask = missing_required[:1]

        questions = []
        for field, label, req in self.fields:
            if field in to_ask:
                q = self._question_for(field, label, req)
                questions.append(q)

        reply = questions[0] if questions else "请补充一下相关信息～"

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "is_complete": False,
                "collected": state,
                "next_question": reply,
                "missing_fields": to_ask,
                "max_rounds_reached": False,
            },
        )

    def _question_for(self, field: str, label: str, required: bool) -> str:
        if field == "product_type":
            return "请问您用的是什么产品？"
        if field == "bot_id":
            return "如果是 Claw，请提供 Bot ID。"
        if field == "issue_desc":
            return "具体遇到了什么问题？"
        if field == "self_check":
            return "您尝试过哪些操作？"
        if field == "time":
            return "问题大概什么时候开始的？"
        if field == "repro_steps":
            return "能描述一下复现步骤吗？"
        if field == "screenshot":
            return "有报错截图吗？有的话请直接发送。"
        return f"请提供{label}："

    def _extract(self, s: Dict, msg: str) -> Dict:
        st = dict(s)
        # 先进行别名映射，再提取字段（便于识别"小龙虾"→claw 等口语化表达）
        normalized_msg = normalize_user_expression(msg)
        m = normalized_msg.lower()
        raw_lower = msg.lower()

        if not st.get("product_type"):
            if any(w in m for w in {"desktop", "本地", "电脑", "finder", "访达"}):
                st["product_type"] = "desktop"
            elif any(w in m for w in {"android", "安卓", "手机", "dashboard", "权限"}):
                st["product_type"] = "android"
            elif any(w in m for w in {"群聊", "conductor", "thread", "群规"}):
                st["product_type"] = "群聊"
            elif any(w in m for w in {"云端", "网页", "app", "kimi.com", "web ssh"}):
                st["product_type"] = "云端"
            # 别名映射后的 claw 识别（如"小龙虾"已映射为"claw"）
            elif "claw" in m and "claw" not in raw_lower:
                # 用户使用了别名（如小龙虾），但尚未明确具体形态，暂不赋值具体形态
                # 保留待后续追问
                st["product_type"] = "claw（待确认形态）"

        if not st.get("bot_id"):
            ids = re.findall(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', msg)
            if not ids:
                ids = re.findall(r'\b\d{6,}\b', msg)
            if ids:
                st["bot_id"] = ids[0]

        if not st.get("platform"):
            for p in self.platforms:
                if p in m or p in msg:
                    st["platform"] = p
                    break

        if not st.get("time") and any(h in msg for h in {"今天", "昨天", "早上", "下午", "刚才", "最近", "小时", "分钟"}):
            st["time"] = msg

        if not st.get("screenshot") and any(w in msg for w in {"截图", "图片", "录屏", "附件"}):
            st["screenshot"] = "用户提及有截图"

        if not st.get("issue_desc"):
            st["issue_desc"] = msg
        elif not st.get("self_check") and len(msg) > 5:
            st["self_check"] = msg

        return st

    def _get_parameters(self) -> Dict[str, Any]:
        return {"user_message": {"type": "string"}, "session_state": {"type": "object", "optional": True}}
