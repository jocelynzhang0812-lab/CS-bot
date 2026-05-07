"""知识库数据模型基类，从 knowledge_base.py 重新导出以兼容现有导入。"""
from csbot.knowledge.knowledge_base import KnowledgeDoc, SearchResult, DocType

__all__ = ["KnowledgeDoc", "SearchResult", "DocType"]
