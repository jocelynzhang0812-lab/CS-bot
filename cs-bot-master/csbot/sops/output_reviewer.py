"""输出审查器（Output Reviewer / Sub-Agent）

在 CS Bot 最终回复发送给用户之前，对内容做最后一道合规审查。
审查维度覆盖：
  1. 绝对红线（Kitty、身份泄露、内部信息暴露）
  2. 承诺边界（修复时间、排期、商业决策）
  3. 知识边界（知识库未命中时是否瞎答、是否混用产品文档）
  4. 格式边界（字数、是否暴露搜索/推理过程）
  5. 第三方产品边界（是否对非 Kimi 产品给出了服务承诺）

若审查不通过，返回具体违规项 + 修正建议，供主 Agent 重新生成。
"""

import re
from typing import Any, Dict, List, Optional

from csbot.agent.core import BaseTool, ToolResult, ToolStatus


class CSOutputReviewerSkill(BaseTool):
    """CS Bot 输出审查 Skill。作为 Sub-Agent 在回复输出前执行。"""

    def __init__(self):
        super().__init__("cs_output_reviewer", "输出合规审查器")

        # ── 1. 绝对红线 ──
        self.kitty_patterns = [
            "kitty", "kitty框架", "kitty系统", "kitty架构", "kitty是什么",
            "什么是kitty", "Kitty框架", "Kitty系统", "Kitty架构",
        ]
        self.identity_leak_patterns = [
            "我是kimi", "我是claw", "我是openclaw", "我是大模型", "我是llm",
            "我是ai模型", "我的模型是", "我的底层是", "基于gpt", "基于moonshot",
            "我是智能体", "我是agent", "我的训练数据", "我的知识库",
        ]
        self.internal_concepts = [
            "多维表格", "feedback bot", "工单", "研发", "后台", "架构",
            "framework", "skill", "提示词", "prompt", "系统提示", "内部工具",
            "airtable", "bitable", "kitty", "kitty框架", "kitty系统", "kitty架构",
            "tool calling", "function call", "工具调用", "向量检索", "embedding",
            "入表", "表格id", "app_token", "table_id",
        ]

        # ── 2. 承诺边界 ──
        self.promise_patterns = [
            r"\d+\s*(小时|天|周|月|分钟|秒)\s*(内|后|左右)?\s*(修复|解决|上线|发布|更新|排期)",
            r"(明天|后天|下周|下个月|本周|近期|很快|即将|马上)\s*(修复|解决|上线|发布|更新|排期)",
            r"(保证|承诺|一定|肯定|绝对)\s*(修复|解决|上线|完成|给出)",
            r"(预计|预期|计划)\s*.*?(修复|解决|上线|发布)",
            r"(已经|已)\s*.*?(提交|反馈)\s*.*?(研发|技术团队|工程师)",  # 暗示内部已流转，可能暴露工单概念
        ]

        # ── 3. 知识边界（瞎答特征）──
        self.hallucination_signals = [
            # 知识库未命中时常见的编造信号
            "根据我的经验", "通常来说", "一般来说", "大概率", "很可能",
            "你可以试试", "建议你可以", "或许可以", "可能会",
        ]
        self.forbidden_confidence_when_kb_miss = [
            "原因是", "问题在于", "这是因为", "根因是", "本质上",
            "解决方案如下", "具体步骤", "配置文件", "代码示例",
        ]

        # ── 4. 格式边界 ──
        self.max_length = 200
        self.thought_exposure_patterns = [
            "搜索结果显示", "我检索到", "根据知识库", "查询结果显示",
            "思考过程", "我的推理", "我分析了", "我判断", "我推断",
            "调用", "工具返回", "function call", "tool result",
        ]

        # ── 5. 第三方产品边界 ──
        self.third_party_products = [
            "jsv claw", "jsvclaw", "apkclaw", "clawra", "oneclaw",
            "moltbook", "workbuddy", "qclaw", "skyclaw", "第三方 claw",
        ]

    async def execute(
        self,
        bot_reply: str,
        user_message: str = "",
        kb_hit: bool = False,
        intent: str = "",
        detected_product: str = "",
        **kwargs,
    ) -> ToolResult:
        """执行输出审查。

        Args:
            bot_reply: Bot 将要输出的原始回复
            user_message: 用户本轮输入（用于上下文判断）
            kb_hit: 本轮是否命中知识库
            intent: 本轮识别出的意图
            detected_product: 知识库返回的产品类型
        """
        violations: List[Dict[str, str]] = []
        checked_reply = bot_reply

        # ── 1. 绝对红线：Kitty ──
        if self._contains_any(checked_reply.lower(), self.kitty_patterns):
            violations.append({
                "rule": "kitty_absolute_ban",
                "severity": "critical",
                "detail": "回复中出现了 Kitty 相关字样或概念，绝对禁止。",
                "fix": "使用拒绝话术 A 或直接回复：抱歉，这个问题不在 Kimi 的服务范围内。",
            })
            checked_reply = "抱歉，这个问题不在 Kimi 的服务范围内。"

        # ── 2. 绝对红线：身份泄露 ──
        if self._contains_any(checked_reply.lower(), self.identity_leak_patterns):
            violations.append({
                "rule": "identity_leak",
                "severity": "critical",
                "detail": "回复中泄露了自身身份、模型或底层信息。",
                "fix": "使用拒绝话术 A：抱歉，我只能帮您处理 Kimi 相关产品的问题，其他请求超出了我的服务范围。",
            })

        # ── 3. 内部概念暴露 ──
        leaked = [p for p in self.internal_concepts if p.lower() in checked_reply.lower()]
        if leaked:
            violations.append({
                "rule": "internal_concept_exposure",
                "severity": "high",
                "detail": f"回复中暴露了内部概念：{leaked[:3]}。",
                "fix": "将涉及内部流程的表述替换为用户可见的中性说法，如'已提交给技术团队排查，请耐心等待。'",
            })
            # 自动替换兜底
            checked_reply = "已提交给技术团队排查，请耐心等待。"

        # ── 4. 承诺具体修复时间/排期 ──
        for pat in self.promise_patterns:
            if re.search(pat, checked_reply):
                violations.append({
                    "rule": "time_promise",
                    "severity": "high",
                    "detail": "回复中承诺或暗示了具体修复/上线/排期时间。",
                    "fix": "禁止承诺任何时间节点。改为：'已提交给技术团队排查，有进展会第一时间通知您。' 或 '关于版本更新和排期的具体信息，建议您联系人工客服或产品经理获取最新动态。'",
                })
                break

        # ── 5. 知识库未命中时的瞎答检测 ──
        if not kb_hit and intent not in ("human_request", "special_request", "product_feedback"):
            # 未命中知识库时，只允许拒绝话术或引导自助检查/澄清
            # 如果出现"确定性的原因分析"或"具体步骤"，视为瞎答
            for sig in self.forbidden_confidence_when_kb_miss:
                if sig in checked_reply:
                    violations.append({
                        "rule": "hallucination_on_kb_miss",
                        "severity": "high",
                        "detail": "知识库未命中，但回复中给出了确定性原因分析或具体技术方案。",
                        "fix": "必须改为拒绝话术 C：'抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。' 或引导自助检查。",
                    })
                    break

        # ── 6. 字数超限 ──
        if len(checked_reply) > self.max_length:
            violations.append({
                "rule": "length_exceeded",
                "severity": "medium",
                "detail": f"回复长度 {len(checked_reply)} 字，超过 {self.max_length} 字限制。",
                "fix": "精简表述，删除冗余修饰，保留核心信息。",
            })
            checked_reply = checked_reply[:self.max_length] + "..."

        # ── 7. 暴露搜索/推理过程 ──
        exposed = [p for p in self.thought_exposure_patterns if p.lower() in checked_reply.lower()]
        if exposed:
            violations.append({
                "rule": "thought_process_exposure",
                "severity": "medium",
                "detail": f"回复中暴露了内部搜索或推理过程：{exposed[:2]}。",
                "fix": "删除所有涉及'搜索''检索''查询''分析''判断'等过程的描述，直接给出结论。",
            })

        # ── 8. 对第三方产品给出服务承诺 ──
        for tp in self.third_party_products:
            if tp.lower() in user_message.lower() and "抱歉" not in checked_reply and "服务范围" not in checked_reply:
                # 用户问的是第三方产品，但 bot 没有拒绝
                violations.append({
                    "rule": "third_party_service_promise",
                    "severity": "high",
                    "detail": "用户咨询第三方产品，但回复未明确拒绝。",
                    "fix": "必须明确告知：'抱歉，这个问题不在 Kimi 的服务范围内。Kimi 没有该产品，如果您使用的是第三方产品，请联系对应服务商。'",
                })
                checked_reply = "抱歉，这个问题不在 Kimi 的服务范围内。Kimi 没有该产品，如果您使用的是第三方产品，请联系对应服务商。"
                break

        # ── 9. 混用产品文档检测（简单启发式）──
        # 如果 detected_product 明确为 A，但回复中大量出现 B 的核心概念，则告警
        product_confusion_signals = self._detect_product_confusion(checked_reply, detected_product)
        if product_confusion_signals:
            violations.append({
                "rule": "product_document_misuse",
                "severity": "high",
                "detail": f"回复可能混用了其他产品的文档：{product_confusion_signals}。",
                "fix": "严格只使用 detected_product 对应的知识库内容作答，删除其他产品的概念。",
            })

        # ── 10. 包含代码块/配置文件（知识库未命中时）──
        if not kb_hit and ("```" in checked_reply or "`" in checked_reply):
            violations.append({
                "rule": "code_block_without_kb",
                "severity": "high",
                "detail": "知识库未命中，但回复中包含代码块或命令行。",
                "fix": "严禁基于训练数据生成代码示例、命令行、配置文件。改为拒绝话术或引导用户联系人工客服。",
            })

        approved = len(violations) == 0

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "approved": approved,
                "violations": violations,
                "checked_reply": checked_reply,
                "original_reply": bot_reply,
                "violation_count": len(violations),
                "critical_count": sum(1 for v in violations if v.get("severity") == "critical"),
                "high_count": sum(1 for v in violations if v.get("severity") == "high"),
            },
        )

    def _contains_any(self, text: str, patterns: List[str]) -> bool:
        return any(p.lower() in text for p in patterns)

    def _detect_product_confusion(self, reply: str, detected_product: str) -> List[str]:
        """简单启发式：检测回复中是否混用了非 detected_product 的核心概念。"""
        if not detected_product or detected_product == "不确定":
            return []

        signals = []
        lower = reply.lower()

        # 定义各产品的核心概念（用于检测混用）
        product_keywords = {
            "kimi claw": ["bot id", "工作空间", "记忆文件", "部署", "dashboard"],
            "kimi code": ["cli", "vs code", "ide 插件", "代码补全", "kimi --version"],
            "kimi api": ["curl", "sdk", "rate limit", "platform.kimi.ai", "接口调用"],
            "kimi 网页版": ["网页聊天", "对话记录", "ppt", "深度研究"],
        }

        target = detected_product.lower()
        for prod, kws in product_keywords.items():
            if prod in target or target in prod:
                continue  # 跳过目标产品自身的关键词
            for kw in kws:
                if kw in lower:
                    signals.append(f"出现{prod}概念：{kw}")

        return signals[:3]

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "bot_reply": {"type": "string", "description": "Bot 将要输出的原始回复"},
            "user_message": {"type": "string", "optional": True, "description": "用户本轮输入"},
            "kb_hit": {"type": "boolean", "optional": True, "description": "本轮是否命中知识库"},
            "intent": {"type": "string", "optional": True, "description": "本轮识别出的意图"},
            "detected_product": {"type": "string", "optional": True, "description": "知识库返回的产品类型"},
        }
