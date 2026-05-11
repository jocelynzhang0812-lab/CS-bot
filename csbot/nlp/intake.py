from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from csbot.nlp.aliases import (
    expand_for_intent_detection,
    expand_for_kb_search,
    is_vague_expression,
    infer_context_from_history,
)
from csbot.nlp.disambiguator import Disambiguator, should_clarify
from csbot.config.loader import get_intent_keywords
from typing import Any, Dict, List, Optional


class CSIntakeSkill(BaseTool):
    """首轮分流：产品类型 -> 功能模块 -> 意图。
    支持上下文感知：对"卡住了"等模糊表达，结合 session 历史进行消歧。
    意图关键词从 config/submission_rules.yaml 加载，保证外部可配置。"""

    def __init__(self):
        super().__init__("cs_intake", "用户意图与产品类型分流")
        self.disambiguator = Disambiguator()
        self.product_types = {
            "云端": {"kimi.com", "网页", "app", "头像", "id", "云端", "web ssh", "设置里打开终端"},
            "desktop": {"desktop", "本地", "电脑客户端", "我的电脑", ".kimi_openclaw", "finder", "访达"},
            "android": {"android", "安卓", "dashboard", "权限", "自启动", "电池优化", "锁屏掉线", "手机"},
            "群聊": {"群聊", "conductor", "thread", "群规", "worker", "群目标", "@机器人"},
        }
        self.modules = {
            "接入鉴权": {"接入", "配置", "扫码", "飞书", "微信", "企微", "钉钉", "微博", "鉴权", "token", "配对", "授权失败"},
            "故障排查": {"不回", "没反应", "连接断开", "超时", "崩溃", "bug", "故障", "离线", "红灯", "很慢", "卡", "卡顿", "异常", "部署失败"},
            "会员额度": {"会员", "额度", "allegretto", "rate limit", "退款", "退订", "开票", "发票"},
            "命令与终端": {"/help", "/status", "/cron", "/logs", "/memory", "/new", "terminal", "ssh", "命令"},
            "记忆上下文": {"失忆", "忘了", "记忆", "上下文", "凌晨", "session", "重置", "memory"},
            "文件产物": {"文件", "下载", "产物", "工作空间", "workspace", "上传", "查看产物"},
            "升级兼容": {"升级", "版本", "插件", "兼容", "恢复初始设置", "恢复初始版本", "openclaw", "更新", "排期", "上线时间", "什么时候上", "多久上线"},
            "问题上报": {"反馈", "上报", "bot id", "提交", "人工", "客服"},
        }
        # 从外部配置加载意图关键词（特殊请求、转人工、回答错误、产品建议、情绪）
        kw_cfg = get_intent_keywords()
        self.emotion = set(kw_cfg.get("emotion", []))
        self.special = set(kw_cfg.get("special", []))
        self.human_request = set(kw_cfg.get("human_request", []))
        self.wrong_answer = set(kw_cfg.get("wrong_answer", []))
        self.product_feedback = set(kw_cfg.get("product_feedback", []))

    async def execute(
        self,
        user_message: str,
        mentioned: bool = False,
        session_state: Optional[Dict] = None,
        history: Optional[List[Dict]] = None,
        **kwargs,
    ) -> ToolResult:
        if not mentioned:
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, result={"action": "ignore"})

        # ── 别名映射（保留原始消息，同时用于意图检测）──
        raw_msg = user_message
        expanded = expand_for_intent_detection(raw_msg)
        m = expanded.lower()
        ex = m.count("!") + m.count("！")

        # 提前初始化，避免消歧追问时 NameError
        ptype = None
        module = None

        # ── 上下文消歧（针对"卡住了"等模糊表达）──
        context_inference = infer_context_from_history(raw_msg, session_state or {}, history or [])

        # ── 实体消歧（针对"群"、"机器人"等高歧义实体）──
        disambig_result = self.disambiguator.resolve(raw_msg, session_state, history)
        resolved_entities = disambig_result.resolved_entities

        # 如果消歧低置信度，优先触发追问
        if should_clarify(disambig_result):
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "intent": "clarify_needed",
                    "emotion_level": 1,
                    "product_type": None,
                    "module": None,
                    "is_special": False,
                    "needs_comfort": False,
                    "needs_kb": False,
                    "is_human_request": False,
                    "is_wrong_answer": False,
                    "is_product_feedback": False,
                    "context_confidence": "low",
                    "context_reasoning": f"歧义词'{disambig_result.clarify_term}'无法确定指向",
                    "needs_clarify": True,
                    "resolved_entities": [r.to_dict() for r in resolved_entities],
                    "引导话术": disambig_result.clarify_message,
                },
            )

        # 将消歧结果合并到上下文推断中（用于后续模块判定）
        # 例如："群"被解析为"claw群聊"时，帮助确定 product_type
        for r in resolved_entities:
            if r.get("confidence") in ("high", "medium"):
                entity = r.get("resolved_entity", "")
                if "claw群聊" in entity and not ptype:
                    ptype = "群聊"
                    context_inference["reasoning"] += f"消歧结果: {entity}; "
                elif "人工客服" in entity or "问题上报" in entity:
                    context_inference["inferred_module"] = "问题上报"
                    context_inference["reasoning"] += f"消歧结果: {entity}; "

        # 1. 判产品类型（优先使用上下文推断）
        ptype = context_inference.get("inferred_product_type")
        if not ptype:
            for pt, kws in self.product_types.items():
                if any(k in m for k in kws):
                    ptype = pt
                    break

        # 2. 判功能模块（优先使用上下文推断）
        module = context_inference.get("inferred_module")
        if not module:
            for mod, kws in self.modules.items():
                if any(k in m for k in kws):
                    module = mod
                    break

        # 3. 判情绪
        emotion_level = 1
        if any(w in m for w in self.emotion) or ex >= 2:
            emotion_level = 4 if ex >= 3 or any(w in m for w in {"投诉", "退费", "退款"}) else 3

        # 4. 判特殊请求 / 转人工 / 回答错误 / 产品建议（按优先级）
        is_special = any(w in m for w in self.special)
        is_human_request = any(w in m for w in self.human_request)
        is_wrong_answer = any(w in m for w in self.wrong_answer)
        is_product_feedback = any(w in m for w in self.product_feedback)

        # 5. 判意图
        intent = "clarify_needed"
        if is_special:
            intent = "special_request"
        elif is_human_request:
            intent = "human_request"
        elif is_wrong_answer:
            intent = "wrong_answer"
        elif is_product_feedback:
            intent = "product_feedback"
        elif module == "故障排查" or any(w in m for w in {"不回", "没反应", "离线", "报错", "bug", "崩溃", "卡顿", "异常", "部署失败"}):
            intent = "tech_bug"
        elif module in {"接入鉴权", "命令与终端", "记忆上下文", "文件产物", "升级兼容"}:
            intent = "faq"
        elif module == "问题上报":
            intent = "feedback"

        # 6. 分流话术（模糊表达且置信度低时，追加追问）
        needs_clarify = context_inference.get("needs_clarify", False)
        reasoning = context_inference.get("reasoning", "")

        if ptype and module and not needs_clarify:
            分流话术 = (
                f"收到，您遇到的是 Kimi Claw（{ptype}）的{module}问题。\n"
                f"这是常见场景，可以先排查一下。您操作后把结果告诉我，我再继续判断下一步。\n"
                f"如果仍未恢复，我会按规范帮您提交技术排查。"
            )
        elif not ptype:
            分流话术 = "为了更快定位问题，先确认下您使用的是哪款产品？如果是 Kimi Claw，请说明是云端、Desktop、Android 还是群聊形态。"
        elif is_human_request:
            分流话术 = "收到，已记录您的请求，正在为您转接人工客服，请稍候。"
        elif is_wrong_answer:
            分流话术 = "抱歉给您带来困扰，我已记录该问题并提交复盘，正确的信息会尽快同步给您。"
        elif is_product_feedback:
            分流话术 = "收到您的建议，我会记录下来同步给产品团队，感谢您的宝贵反馈！"
        elif needs_clarify and is_vague_expression(raw_msg):
            # 模糊表达但有一定上下文
            分流话术 = (
                f"收到，您提到'{raw_msg.strip()}'。"
                f"为了更准确地帮您排查，能否补充说明一下：\n"
                f"1. 具体是在哪个环节出现的（比如部署、对话、查看记忆等）？\n"
                f"2. 当时有什么具体现象（比如报错信息、一直转圈、直接闪退等）？"
            )
        elif disambig_result.needs_clarify:
            分流话术 = disambig_result.clarify_message
        else:
            分流话术 = f"已识别为{ptype}场景，正在定位具体问题模块..."

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "intent": intent,
                "emotion_level": emotion_level,
                "product_type": ptype,
                "module": module,
                "is_special": is_special,
                "needs_comfort": emotion_level >= 3,
                "needs_kb": intent in ("faq", "tech_bug", "feedback", "clarify_needed", "human_request", "wrong_answer", "product_feedback"),
                "is_human_request": is_human_request,
                "is_wrong_answer": is_wrong_answer,
                "is_product_feedback": is_product_feedback,
                "context_confidence": context_inference.get("confidence", "low"),
                "context_reasoning": reasoning,
                "needs_clarify": needs_clarify or disambig_result.needs_clarify,
                "resolved_entities": [r.to_dict() for r in resolved_entities],
                "引导话术": 分流话术,
            },
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "user_message": {"type": "string"},
            "mentioned": {"type": "boolean"},
            "session_state": {"type": "object", "optional": True},
            "history": {"type": "array", "optional": True, "description": "最近对话历史，用于上下文消歧"},
        }