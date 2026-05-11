"""
Agent Router —— 主路由层

路由逻辑：
- greeting → 直接回复，不走 RAG
- knowledge_query → 召回 → 有结果则回答，无结果走 fallback
- fault_report → 槽位提取 → 写入反馈记录
- other → 转人工兜底

System Prompt 中明确禁止 LLM 使用检索结果以外的信息，
知识库为空时必须说"未找到相关信息"。
"""

from typing import Dict, Any, Optional

from intent.classifier import IntentClassifier
from intent.slot_extractor import SlotExtractor
from retrieval.retrieve import Retriever


GREETING_REPLIES = [
    "你好！我是 Kimi 官方客服助手，有什么可以帮您的吗？",
    "您好！欢迎咨询 Kimi 产品相关问题。",
    "在的，请问有什么可以帮您？",
]

FALLBACK_REPLY = "抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。"

FAULT_COLLECT_REPLY = (
    "已记录您反馈的问题，技术团队会尽快排查。"
    "如有进展我们会第一时间通知您，感谢您的耐心等待。"
)


class AgentRouter:
    """客服 Agent 主路由。"""

    def __init__(
        self,
        llm_client,
        retriever: Retriever,
        classifier: IntentClassifier,
        slot_extractor: SlotExtractor,
    ):
        self.llm = llm_client
        self.retriever = retriever
        self.classifier = classifier
        self.slot_extractor = slot_extractor

    async def route(self, user_input: str) -> Dict[str, Any]:
        """
        主路由入口。
        :return: {
            "type": "greeting" | "answer" | "fault_record" | "knowledge_not_found" | "human_handoff",
            "reply": str,
            "slots": dict | None,
            "retrieval_results": list | None,
        }
        """
        # Step 1: 意图分类
        intent = await self.classifier.classify(user_input)
        print(f"[Router] intent={intent} query='{user_input[:50]}'")

        if intent == "greeting":
            return await self._handle_greeting(user_input)

        elif intent == "knowledge_query":
            return await self._handle_knowledge_query(user_input)

        elif intent == "fault_report":
            return await self._handle_fault_report(user_input)

        else:  # other
            return await self._handle_other(user_input)

    async def _handle_greeting(self, user_input: str) -> Dict[str, Any]:
        """问候类：直接回复，不走 RAG。"""
        import random
        return {
            "type": "greeting",
            "reply": random.choice(GREETING_REPLIES),
            "slots": None,
            "retrieval_results": None,
        }

    async def _handle_knowledge_query(self, user_input: str) -> Dict[str, Any]:
        """知识查询类：召回 → 有结果则回答，无结果走 fallback。"""
        retrieval = await self.retriever.retrieve(user_input, top_k=5)

        if not retrieval["hit"]:
            return {
                "type": "knowledge_not_found",
                "reply": self.retriever.handle_knowledge_not_found(user_input),
                "slots": None,
                "retrieval_results": [],
            }

        # 构造 grounded context
        context = self._build_context(retrieval["results"])

        # 调用 LLM 回答（严格基于检索结果）
        system_msg = (
            "你是 Kimi 官方客服助手。请仅根据以下知识库内容回答用户问题。\n"
            "严禁使用知识库以外的信息。知识库为空时必须回复：\n"
            f"「{FALLBACK_REPLY}」\n\n"
            f"知识库内容：\n{context}"
        )

        try:
            response = await self.llm.chat(
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.1,
                top_p=0.1,
            )
            reply = response.get("content", FALLBACK_REPLY).strip()
        except Exception as e:
            print(f"[Router] LLM 回答失败: {e}")
            reply = FALLBACK_REPLY

        return {
            "type": "answer",
            "reply": reply,
            "slots": None,
            "retrieval_results": retrieval["results"],
        }

    async def _handle_fault_report(self, user_input: str) -> Dict[str, Any]:
        """故障报告类：槽位提取 → 写入反馈记录。"""
        slots = await self.slot_extractor.extract(user_input)
        print(f"[Router] slots={slots}")

        # 同时尝试知识库召回（可能已有已知故障）
        retrieval = await self.retriever.retrieve(user_input, top_k=3)

        if retrieval["hit"]:
            # 如果知识库有已知故障，基于知识库回答
            context = self._build_context(retrieval["results"])
            system_msg = (
                "用户反馈了一个故障。请根据知识库内容给出排查建议。\n"
                f"知识库内容：\n{context}"
            )
            try:
                response = await self.llm.chat(
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_input},
                    ],
                    temperature=0.1,
                )
                reply = response.get("content", FAULT_COLLECT_REPLY).strip()
            except Exception:
                reply = FAULT_COLLECT_REPLY
        else:
            reply = FAULT_COLLECT_REPLY

        return {
            "type": "fault_record",
            "reply": reply,
            "slots": slots,
            "retrieval_results": retrieval["results"] if retrieval["hit"] else [],
        }

    async def _handle_other(self, user_input: str) -> Dict[str, Any]:
        """其他类：转人工兜底。"""
        return {
            "type": "human_handoff",
            "reply": FALLBACK_REPLY,
            "slots": None,
            "retrieval_results": None,
        }

    def _build_context(self, results: list) -> str:
        """将检索结果格式化为 grounded context。"""
        lines = []
        for i, r in enumerate(results, 1):
            doc = r.get("doc")
            if doc:
                lines.append(f"[文档{i}] {doc.title}\n{doc.content[:500]}")
        return "\n\n".join(lines)
