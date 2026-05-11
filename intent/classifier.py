"""
Layer 1 意图分类器

输出标签限定为四类，其余一律返回 other：
- knowledge_query：询问功能、用法、排查步骤
- fault_report：反馈故障、报错、设备异常
- greeting：问候、闲聊、感谢
- other：无法归类

Prompt 中只允许输出标签，不得包含解释或多余文字。
"""

from typing import Optional


INTENT_LABELS = {"knowledge_query", "fault_report", "greeting", "other"}

INTENT_PROMPT = """你是一个意图分类器。请分析以下用户输入，仅输出一个标签，不得包含任何解释。

可选标签（严格四选一）：
- knowledge_query：用户询问产品功能、用法、操作步骤、排查方法
- fault_report：用户反馈故障、报错信息、设备异常、无法使用
- greeting：用户打招呼、闲聊、感谢、告别
- other：无法归入以上三类

用户输入：{user_input}

标签："""


class IntentClassifier:
    """意图分类器。用 LLM 做分类，代码层做合法性校验。"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def classify(self, user_input: str) -> str:
        """
        分类用户意图。
        :return: knowledge_query | fault_report | greeting | other
        """
        if not user_input or not user_input.strip():
            return "other"

        # 快速规则层（不调用 LLM）
        fast_result = self._fast_classify(user_input.strip())
        if fast_result:
            return fast_result

        # LLM 层
        try:
            prompt = INTENT_PROMPT.format(user_input=user_input.strip())
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                top_p=0.1,
            )
            raw_label = response.get("content", "").strip().lower()

            # 清理可能的 markdown、引号、多余空格
            raw_label = raw_label.replace("`", "").replace("'", "").replace('"', "").strip()

            # 合法性校验
            if raw_label in INTENT_LABELS:
                return raw_label

            # 模糊匹配
            for label in INTENT_LABELS:
                if label in raw_label:
                    return label

            # 非法输出降级
            print(f"[IntentClassifier] 非法输出，降级为 other: '{raw_label}'")
            return "other"

        except Exception as e:
            print(f"[IntentClassifier] LLM 调用失败，降级为 other: {e}")
            return "other"

    def _fast_classify(self, text: str) -> Optional[str]:
        """基于关键词的快速规则分类。命中则直接返回，不调用 LLM。"""
        lower = text.lower()

        # greeting 规则（高优先级，短文本优先匹配）
        greeting_words = {
            "你好", "您好", "在吗", "hi", "hello", "hey",
            "谢谢", "感谢", "再见", "拜拜", "bye",
            "早上好", "下午好", "晚上好",
        }
        if any(w in lower for w in greeting_words) and len(text) < 20:
            return "greeting"

        # fault_report 规则
        fault_signals = {
            "报错", "错误", "失败", "崩溃", "卡住", "离线", "连不上",
            "没反应", "不工作", "异常", "bug", "故障", "挂了", "崩了",
            "timeout", "error", "failed", "crash",
            "401", "403", "404", "500",
        }
        if any(w in lower for w in fault_signals):
            return "fault_report"

        # knowledge_query 规则
        query_signals = {
            "怎么", "如何", "怎样", "哪里", "什么", "吗？", "吗?",
            "支持", "可以", "能否", "帮忙", "请问",
            "怎么做", "怎么用", "怎么设置", "怎么部署",
        }
        if any(w in lower for w in query_signals):
            return "knowledge_query"

        return None
