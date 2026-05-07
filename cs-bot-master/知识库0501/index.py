"""知识库索引与检索（已迁移至 csbot.knowledge.index，此处保留向后兼容入口）"""
from csbot.knowledge.index import KnowledgeIndex
from csbot.knowledge.base import KnowledgeDoc, SearchResult, DocType

__all__ = ["KnowledgeIndex", "KnowledgeDoc", "SearchResult", "DocType"]
