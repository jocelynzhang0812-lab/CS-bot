#!/usr/bin/env python3
"""当 knowledge/data/ 下的 .md 文件更新后，重建索引"""
import sys
sys.path.insert(0, ".")

from csbot.knowledge.loader import KnowledgeLoader
from csbot.knowledge.index import KnowledgeIndex

def main():
    loader = KnowledgeLoader()
    index = KnowledgeIndex()
    docs = loader.load_all("csbot/knowledge/data")
    index.add_batch(docs)
    print(f"✅ 索引重建完成，共 {len(docs)} 条文档")
    # 实际生产环境这里应该序列化 index 到磁盘或向量数据库

if __name__ == "__main__":
    main()