"""Embedding Provider 抽象与实现

支持外部 API（OpenAI 兼容格式）和本地模型（sentence-transformers）。
默认优先使用外部 API，无配置时自动回退到关键词检索。
"""
from abc import ABC, abstractmethod
from typing import List
import os


class EmbeddingProvider(ABC):
    """文本向量化抽象"""

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """将一批文本编码为向量，返回 List[embedding]"""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    调用 OpenAI 兼容的 Embedding API。
    可接入 OpenAI、SiliconFlow、Azure 等任何兼容 /v1/embeddings 的服务。
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "text-embedding-3-small",
        base_url: str = None,
    ):
        api_key = api_key or os.getenv("EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = base_url or os.getenv("EMBEDDING_BASE_URL")
        if not api_key:
            raise ValueError(
                "OpenAIEmbeddingProvider 需要 api_key 或 EMBEDDING_API_KEY / OPENAI_API_KEY 环境变量"
            )
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def embed(self, texts: List[str]) -> List[List[float]]:
        # OpenAI embedding API 单次最多 2048 条，这里直接批量发送
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]


class SentenceTransformerProvider(EmbeddingProvider):
    """
    本地轻量模型（sentence-transformers），离线运行、零 API 费用。
    需要：pip install sentence-transformers

    推荐模型：
      - BAAI/bge-small-zh-v1.5   （中文场景，~100MB）
      - paraphrase-multilingual-MiniLM-L12-v2  （多语言，~120MB）
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "SentenceTransformerProvider 需要 sentence-transformers。\n"
                "请执行：pip install sentence-transformers"
            ) from e
        self.model = SentenceTransformer(model_name)

    async def embed(self, texts: List[str]) -> List[List[float]]:
        # sentence-transformers 是 CPU 密集型同步操作，扔到线程池避免阻塞事件循环
        import asyncio

        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, self.model.encode, texts)
        return embeddings.tolist()
