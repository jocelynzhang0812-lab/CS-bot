"""
HyDE (Hypothetical Document Embedding) 检索器

修复 B：用 LLM 将用户问题扩写为知识库文档风格的假设文档，
再用假设文档做向量检索，解决用词差异导致的 MISSING 问题。
"""

import json
from typing import List, Dict, Optional


class HyDERetriever:
    """HyDE 检索器：生成假设文档 → 嵌入 → 检索。"""

    HYDE_PROMPT = """你是一个 Kimi 产品的客服知识库文档生成助手。

用户问题：{query}

请用知识库文档的风格，将上述用户问题扩写为一段简洁的技术说明文档。
要求：
- 使用知识库中的标准术语和表述方式
- 不要带开头语（如"根据您的问题"、"以下是"）
- 直接输出文档正文，200字以内
- 如果是故障问题，包含现象、原因、解决方向
- 如果是功能咨询，包含功能说明和操作步骤概述
"""

    def __init__(self, llm_client, index, provider=None):
        self.llm = llm_client
        self.index = index
        self.provider = provider

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        use_hyde: bool = True,
    ) -> List[Dict]:
        """
        HyDE 检索流程：
        1. 生成假设文档（LLM 扩写）
        2. 用假设文档做向量检索
        3. 返回检索结果
        """
        if not use_hyde or self.provider is None:
            # 回退到普通检索
            return await self.index.search(query, top_k=top_k, provider=self.provider)

        # Step 1: 生成假设文档
        hypothetical_doc = await self._generate_hypothetical_doc(query)
        if not hypothetical_doc:
            return await self.index.search(query, top_k=top_k, provider=self.provider)

        # Step 2: 用假设文档做向量检索
        results = await self.index.search(
            hypothetical_doc,
            top_k=top_k,
            provider=self.provider,
            use_vector=True,
        )

        # 打印 HyDE 中间结果（方便 debug）
        print(f"[HyDE] query='{query}' hypothetical_doc='{hypothetical_doc[:100]}...' results={len(results)}")

        return results

    async def _generate_hypothetical_doc(self, query: str) -> str:
        """调用 LLM 生成假设文档。"""
        try:
            prompt = self.HYDE_PROMPT.format(query=query)
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                top_p=0.5,
            )
            doc = response.get("content", "").strip()
            # 清理可能的代码块标记
            doc = doc.replace("```", "").strip()
            return doc
        except Exception as e:
            print(f"[HyDE] 生成假设文档失败: {e}")
            return ""
