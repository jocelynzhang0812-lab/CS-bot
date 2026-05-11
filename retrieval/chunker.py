"""
Chunk 切割优化器

修复 A：使用语义感知切割策略，替代原有的整文档加载。
参数：
  chunk_size=512, chunk_overlap=64
  separators=["\n\n", "\n", "。", "！", "？", " "]
"""

import re
from typing import List


class SemanticChunker:
    """语义感知文本切割器。优先按段落、句子切割，保持语义完整性。"""

    DEFAULT_SEPARATORS = ["\n\n", "\n", "。", "！", "？", " "]

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64, separators=None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or self.DEFAULT_SEPARATORS

    def split(self, text: str) -> List[str]:
        """将长文本切割为语义完整的 chunk 列表。"""
        if not text:
            return []

        # 先按最高优先级分隔符拆分为"原子块"
        atomic_blocks = self._split_to_atoms(text)

        chunks = []
        current_chunk = ""

        for block in atomic_blocks:
            block = block.strip()
            if not block:
                continue

            # 单个块就超过 chunk_size，需要进一步拆分
            if len(block) > self.chunk_size:
                sub_chunks = self._split_oversized(block)
                for sc in sub_chunks:
                    if not current_chunk:
                        current_chunk = sc
                    elif len(current_chunk) + len(sc) + 1 <= self.chunk_size:
                        current_chunk += "\n" + sc
                    else:
                        chunks.append(current_chunk.strip())
                        # 保留 overlap
                        current_chunk = self._take_overlap(current_chunk) + "\n" + sc
                continue

            # 尝试合并到当前 chunk
            if not current_chunk:
                current_chunk = block
            elif len(current_chunk) + len(block) + 1 <= self.chunk_size:
                current_chunk += "\n" + block
            else:
                # 当前 chunk 已满，保存并开新 chunk
                chunks.append(current_chunk.strip())
                current_chunk = self._take_overlap(current_chunk) + "\n" + block

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _split_to_atoms(self, text: str) -> List[str]:
        """按优先级分隔符拆分文本为原子块。"""
        # 先用最高优先级分隔符
        blocks = [text]
        for sep in self.separators:
            new_blocks = []
            for b in blocks:
                parts = b.split(sep)
                for i, p in enumerate(parts):
                    if i < len(parts) - 1:
                        new_blocks.append(p + sep)
                    else:
                        new_blocks.append(p)
            blocks = [b for b in new_blocks if b.strip()]
            # 如果已经拆得够细了，停止
            if len(blocks) >= len(text) // self.chunk_size * 2:
                break
        return blocks

    def _split_oversized(self, text: str) -> List[str]:
        """对超过 chunk_size 的块按字符强制切割，尽量在句末切分。"""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            # 尝试在最近的句子结束处切分
            if end < len(text):
                for sep in "。！？\n":
                    pos = text.rfind(sep, start, end)
                    if pos > start + self.chunk_size // 2:
                        end = pos + 1
                        break
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end
        return chunks

    def _take_overlap(self, text: str) -> str:
        """从文本末尾取出 overlap 部分。"""
        if len(text) <= self.chunk_overlap:
            return text
        # 尽量在句子边界取 overlap
        for sep in "\n。！？":
            pos = text.rfind(sep, len(text) - self.chunk_overlap - 20, len(text))
            if pos > 0:
                return text[pos:].strip()
        return text[-self.chunk_overlap:].strip()
