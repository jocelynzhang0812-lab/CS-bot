"""知识库索引与检索（支持关键词 + 向量语义混合检索）"""
from csbot.knowledge.base import KnowledgeDoc, SearchResult, DocType
from typing import List, Dict, Optional
import re


class KnowledgeIndex:
    def __init__(self):
        self._docs: Dict[str, KnowledgeDoc] = {}
        self._keyword_map: Dict[str, List[str]] = {}
        self._error_code_map: Dict[str, str] = {}  # "400" -> doc_id
        self._platform_map: Dict[str, List[str]] = {}  # "飞书" -> [doc_id]
        self._embeddings: Dict[str, List[float]] = {}

    # ── 文档管理 ────────────────────────────────────────

    def add(self, doc: KnowledgeDoc):
        self._docs[doc.id] = doc

        # 关键词索引（去重，避免同一关键词在同一文档下重复加分）
        all_kw = []
        seen_kw = set()
        for kw in doc.keywords + doc.title.split() + doc.tags:
            if kw not in seen_kw:
                seen_kw.add(kw)
                all_kw.append(kw)
        for kw in all_kw:
            kw_lower = kw.lower()
            doc_list = self._keyword_map.setdefault(kw_lower, [])
            if doc.id not in doc_list:
                doc_list.append(doc.id)

        # 错误码精确索引
        if doc.doc_type == DocType.ERROR_CODE:
            code = doc.meta.get("error_code", "")
            if code:
                self._error_code_map[code] = doc.id

        # 平台索引
        platform = doc.meta.get("platform", "")
        if platform:
            self._platform_map.setdefault(platform, []).append(doc.id)

    def add_batch(self, docs: List[KnowledgeDoc]):
        for d in docs:
            self.add(d)

    def set_doc_embedding(self, doc_id: str, embedding: List[float]):
        """为单条文档注入向量"""
        if doc_id in self._docs:
            self._embeddings[doc_id] = embedding

    async def build_embeddings(self, provider) -> None:
        """批量编码所有已添加的文档（启动时调用一次）"""
        if not self._docs:
            return
        texts = [f"{doc.title}\n{doc.content}" for doc in self._docs.values()]
        embeddings = await provider.embed(texts)
        for doc_id, emb in zip(self._docs.keys(), embeddings):
            self._embeddings[doc_id] = emb

    # ── 检索 ────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int = 3,
        doc_type: Optional[DocType] = None,
        platform: Optional[str] = None,
        provider=None,
        use_vector: bool = True,
    ) -> List[SearchResult]:
        """
        混合检索：
        1. 若有向量索引且 use_vector=True，优先用余弦相似度做语义召回
        2. 同时保留关键词匹配作为补充和过滤手段
        """
        q = query.lower()

        # ── Step 1: 向量语义召回 ────────────────────────
        vector_scores: Dict[str, float] = {}
        if use_vector and self._embeddings and provider is not None:
            query_emb = (await provider.embed([query]))[0]
            for doc_id, doc_emb in self._embeddings.items():
                sim = self._cosine_similarity(query_emb, doc_emb)
                vector_scores[doc_id] = sim

        # ── Step 2: 关键词匹配召回 ──────────────────────
        keyword_scores = self._keyword_search_scores(q)

        # ── Step 3: 混合打分 ────────────────────────────
        # 策略：向量分数 * 0.7 + 关键词分数 * 0.3（归一化后）
        all_ids = set(vector_scores.keys()) | set(keyword_scores.keys())
        final_scores: Dict[str, float] = {}

        # 归一化向量分数到 [0, 1]
        max_vec = max(vector_scores.values()) if vector_scores else 1.0
        max_kw = max(keyword_scores.values()) if keyword_scores else 1.0

        for did in all_ids:
            v_score = vector_scores.get(did, 0.0) / max_vec if max_vec > 0 else 0.0
            k_score = keyword_scores.get(did, 0.0) / max_kw if max_kw > 0 else 0.0

            # 若只有关键词命中（无向量），则完全依赖关键词
            if did not in vector_scores:
                final_scores[did] = k_score * 0.5
            # 若只有向量命中（无关键词），则完全依赖向量
            elif did not in keyword_scores:
                final_scores[did] = v_score * 0.9
            # 两者都命中，混合加权
            else:
                final_scores[did] = v_score * 0.7 + k_score * 0.3

        # ── Step 4: 组装结果 ────────────────────────────
        results = []
        for did, score in sorted(final_scores.items(), key=lambda x: x[1], reverse=True):
            doc = self._docs[did]

            # 类型过滤
            if doc_type and doc.doc_type != doc_type:
                continue
            # 平台过滤
            if platform and doc.meta.get("platform") != platform:
                continue

            # 命中关键词展示
            matched = next((k for k in doc.keywords if k.lower() in q), "")
            if not matched:
                err_code = doc.meta.get("error_code")
                if err_code and err_code in q:
                    matched = err_code

            results.append(SearchResult(
                doc=doc,
                score=min(score, 1.0),
                matched_keyword=matched,
                snippet=doc.content[:200] + ("..." if len(doc.content) > 200 else ""),
            ))

        # ── Debug 日志：打印原始召回分数 ──
        print(f"[KnowledgeIndex] query='{query}' top_k={top_k} vector={len(vector_scores)} kw={len(keyword_scores)} total={len(results)}")
        for i, r in enumerate(results[:top_k], 1):
            print(f"  [recall {i}] score={round(r.score, 3)} source={r.doc.source} kw={r.matched_keyword or '-'} title={r.doc.title[:40]}")

        return results[:top_k]

    # ── 内部工具 ────────────────────────────────────────

    def _keyword_search_scores(self, query_lower: str) -> Dict[str, float]:
        """基于关键词的传统匹配，返回 doc_id -> raw_score"""
        raw_words = set(re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z0-9]+', query_lower))
        # 对长中文词拆分为单字和 2-gram，提升口语化查询的召回率
        q_words: set = set()
        for w in raw_words:
            if len(w) > 2 and all('\u4e00' <= c <= '\u9fa5' for c in w):
                q_words.update(w)           # 单字
                q_words.update(w[i:i + 2] for i in range(len(w) - 1))  # 2-gram
            else:
                q_words.add(w)
        scores: Dict[str, float] = {}

        # 错误码精确匹配
        for word in q_words:
            if word in self._error_code_map:
                did = self._error_code_map[word]
                scores[did] = scores.get(did, 0) + 2.0

        # 关键词匹配
        for kw, doc_ids in self._keyword_map.items():
            if any(w in kw for w in q_words):
                for did in doc_ids:
                    scores[did] = scores.get(did, 0) + 0.5

        # 标题包含（提高权重，标题更准确地反映文档主题）
        # 停用词过滤：过于常见的词不参与 title match 加分，避免泛化标题（如"有哪些推荐的群聊使用模板"）霸榜
        TITLE_STOPWORDS = {
            "使用", "怎么", "如何", "什么", "推荐", "问题", "帮助", "关于", "指南",
            "方法", "解决", "没有", "无法", "不能", "可以", "需要", "是否", "为什么",
            "多少", "哪里", "怎样", "建议", "技巧", "介绍", "说明", "教程", "常用",
            "是", "么", "什", "呢", "吗", "吧", "啊", "哦", "嗯",
        }
        for did, doc in self._docs.items():
            title_hit_words = [w for w in q_words if w in doc.title.lower() and w not in TITLE_STOPWORDS]
            if title_hit_words:
                scores[did] = scores.get(did, 0) + 0.6

        # 内容包含
        for did, doc in self._docs.items():
            if any(w in doc.content.lower() for w in q_words):
                scores[did] = scores.get(did, 0) + 0.2

        return scores

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_by_error_code(self, code: str) -> Optional[KnowledgeDoc]:
        did = self._error_code_map.get(code)
        return self._docs.get(did) if did else None

    def get_by_platform(self, platform: str) -> List[KnowledgeDoc]:
        ids = self._platform_map.get(platform, [])
        return [self._docs[i] for i in ids]

    def all(self) -> List[KnowledgeDoc]:
        return list(self._docs.values())
