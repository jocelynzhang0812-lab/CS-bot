"""知识库数据模型与基类"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class DocType(Enum):
    FAQ = "faq"
    SOP = "sop"
    PRODUCT = "product"
    TROUBLESHOOT = "ts"       # 故障排查手册
    POLICY = "policy"         # 政策/权益
    ERROR_CODE = "error_code" # 错误码速查
    CONFIG = "config"         # 平台配置/鉴权


@dataclass
class KnowledgeDoc:
    id: str
    doc_type: DocType
    title: str
    content: str
    keywords: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    source: str = ""
    version: str = "1.0"
    updated_at: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)  # 扩展字段：错误码、平台、套餐等级等


@dataclass
class SearchResult:
    doc: KnowledgeDoc
    score: float
    matched_keyword: str = ""
    snippet: str = ""
