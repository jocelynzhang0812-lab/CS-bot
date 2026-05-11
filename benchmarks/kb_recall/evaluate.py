#!/usr/bin/env python3
"""
CS-Bot 知识库召回率评测脚本

用法:
    cd /root/cs-bot && python3 benchmarks/kb_recall/evaluate.py

环境变量:
    OPENAI_API_KEY 或 EMBEDDING_API_KEY: 如需测向量检索（混合模式）
    不传则自动回退到关键词-only 模式
"""

import asyncio
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Any

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from csbot.knowledge.loader import KnowledgeLoader
from csbot.knowledge.index import KnowledgeIndex
from csbot.knowledge.kb_search import KBSearchSkill
from csbot.knowledge.embeddings import OpenAIEmbeddingProvider, SentenceTransformerProvider


@dataclass
class EvalResult:
    case_id: str
    query: str
    expected_product: str
    expected_sources: List[str]
    detected_product: str
    hits: List[Dict[str, Any]] = field(default_factory=list)
    hit: bool = False
    product_correct: bool = False
    recall_at_k: float = 0.0
    mrr: float = 0.0
    false_positive: bool = False
    raw_result: Dict[str, Any] = field(default_factory=dict)


class KBRecallBenchmark:
    def __init__(self, dataset_path: str, data_dirs: str, use_vector: bool = False):
        self.dataset_path = dataset_path
        self.data_dirs = data_dirs
        self.use_vector = use_vector
        self.index = KnowledgeIndex()
        self.skill = None
        self.dataset = []
        self.results: List[EvalResult] = []

    async def setup(self):
        """加载知识库并构建索引"""
        print("[Setup] 加载知识库文档...")
        loader = KnowledgeLoader()
        docs = loader.load_all(self.data_dirs)
        print(f"[Setup] 共加载 {len(docs)} 条文档")

        self.index.add_batch(docs)

        provider = None
        if self.use_vector:
            provider = await self._create_embedding_provider()
            if provider:
                print("[Setup] 构建向量索引...")
                await self.index.build_embeddings(provider)
                print("[Setup] 向量索引构建完成")
            else:
                print("[Setup] 无法创建 Embedding Provider，回退到关键词-only 模式")
                self.use_vector = False
        else:
            print("[Setup] 使用关键词-only 模式（无向量检索）")

        self.skill = KBSearchSkill(self.index, provider=provider)
        print("[Setup] KBSearchSkill 初始化完成\n")

    async def _create_embedding_provider(self):
        """尝试创建 Embedding Provider"""
        # 优先尝试 OpenAI 兼容 API
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("EMBEDDING_API_KEY")
        base_url = os.getenv("EMBEDDING_BASE_URL")
        if api_key:
            try:
                return OpenAIEmbeddingProvider(api_key=api_key, base_url=base_url)
            except Exception as e:
                print(f"[Warning] OpenAI Embedding 初始化失败: {e}")

        # 回退到本地 sentence-transformers
        try:
            return SentenceTransformerProvider(model_name="BAAI/bge-small-zh-v1.5")
        except Exception as e:
            print(f"[Warning] SentenceTransformer 初始化失败: {e}")

        return None

    def load_dataset(self):
        """加载测试数据集"""
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            self.dataset = json.load(f)
        print(f"[Dataset] 加载 {len(self.dataset)} 条测试用例\n")

    async def run(self):
        """执行评测"""
        for case in self.dataset:
            result = await self._eval_case(case)
            self.results.append(result)

    async def _eval_case(self, case: Dict) -> EvalResult:
        """单条 case 评测"""
        query = case["query"]
        expected_product = case["expected_product"]
        expected_sources = case.get("expected_sources", [])

        # 调用 KBSearchSkill
        tool_result = await self.skill.execute(query, top_k=3)
        raw = tool_result.result

        detected_product = self._normalize_product(raw.get("detected_product", ""))
        hits = raw.get("hits", [])
        hit_flag = raw.get("hit", False)

        # 产品识别是否正确
        product_correct = detected_product == expected_product

        # 计算 Recall@K 和 MRR
        hit_sources = [h["source"] for h in hits]
        recall_at_k = 0.0
        mrr = 0.0
        if expected_sources:
            matched = [s for s in expected_sources if s in hit_sources]
            recall_at_k = len(matched) / len(expected_sources)

            # MRR: 第一个正确文档的排名的倒数
            for rank, src in enumerate(hit_sources, 1):
                if src in expected_sources:
                    mrr = 1.0 / rank
                    break

        # 是否召回了错误产品的文档（仅限有明确期望产品且不是 negative 的 case）
        false_positive = False
        if expected_product not in ("uncertain", "third_party") and expected_sources:
            for h in hits:
                src = h["source"]
                if src not in expected_sources:
                    # 检查这个 source 是否属于其他产品
                    doc_product = self.skill.SOURCE_PRODUCT_MAP.get(src, "claw")
                    if doc_product != expected_product and doc_product != "general":
                        false_positive = True
                        break

        return EvalResult(
            case_id=case["id"],
            query=query,
            expected_product=expected_product,
            expected_sources=expected_sources,
            detected_product=detected_product,
            hits=hits,
            hit=hit_flag,
            product_correct=product_correct,
            recall_at_k=recall_at_k,
            mrr=mrr,
            false_positive=false_positive,
            raw_result=raw,
        )

    def _normalize_product(self, name: str) -> str:
        """将 detected_product 的友好名称映射回内部标识"""
        reverse_map = {v: k for k, v in self.skill.PRODUCT_NAMES.items()}
        # 处理特殊值
        if "第三方" in name or "非 Kimi" in name:
            return "third_party"
        if "不确定" in name:
            return "uncertain"
        return reverse_map.get(name, name)

    def report(self):
        """输出评测报告"""
        total = len(self.results)

        # 按 case_type 分组统计
        type_stats = defaultdict(lambda: {"total": 0, "product_ok": 0, "hit_ok": 0, "fp": 0})
        for r in self.results:
            ct = next((c.get("case_type", "unknown") for c in self.dataset if c["id"] == r.case_id), "unknown")
            s = type_stats[ct]
            s["total"] += 1
            if r.product_correct:
                s["product_ok"] += 1
            if r.recall_at_k > 0:
                s["hit_ok"] += 1
            if r.false_positive:
                s["fp"] += 1

        # 全局指标
        product_acc = sum(1 for r in self.results if r.product_correct) / total
        hit_rate = sum(1 for r in self.results if r.recall_at_k > 0) / total
        avg_recall = sum(r.recall_at_k for r in self.results) / total
        avg_mrr = sum(r.mrr for r in self.results) / total
        fp_rate = sum(1 for r in self.results if r.false_positive) / total

        print("=" * 70)
        print("📊 CS-Bot 知识库召回率评测报告")
        print("=" * 70)
        print(f"\n模式: {'混合检索（向量+关键词）' if self.use_vector else '关键词-only'}")
        print(f"测试用例数: {total}")
        print(f"知识库文档数: {len(self.index.all())}")

        print(f"\n{'─' * 70}")
        print("🎯 核心指标")
        print(f"{'─' * 70}")
        print(f"  产品识别准确率 (Product Accuracy): {product_acc:.1%}")
        print(f"  文档召回命中率 (Hit Rate @top3):   {hit_rate:.1%}")
        print(f"  平均召回率     (Avg Recall@K):     {avg_recall:.1%}")
        print(f"  平均 MRR:                           {avg_mrr:.3f}")
        print(f"  误召回率       (False Positive):   {fp_rate:.1%}")

        print(f"\n{'─' * 70}")
        print("📁 按场景分组统计")
        print(f"{'─' * 70}")
        print(f"  {'场景':<20} {'总数':>6} {'产品识别':>10} {'命中':>8} {'误召':>8}")
        for ct, s in sorted(type_stats.items()):
            print(f"  {ct:<20} {s['total']:>6} {s['product_ok']/s['total']:>9.0%} {s['hit_ok']/s['total']:>7.0%} {s['fp']/s['total']:>7.0%}")

        # 失败 case 详情
        print(f"\n{'─' * 70}")
        print("❌ 失败详情（产品识别错误或召回失败）")
        print(f"{'─' * 70}")
        fail_count = 0
        for r in self.results:
            if not r.product_correct or r.recall_at_k == 0:
                fail_count += 1
                expected = ", ".join(r.expected_sources) if r.expected_sources else "(无)"
                hits_str = " | ".join([f"{h['source']}({h['score']})" for h in r.hits[:3]]) if r.hits else "(无命中)"
                print(f"\n  [{r.case_id}] {r.query}")
                print(f"    期望产品: {r.expected_product} | 识别产品: {r.detected_product}")
                print(f"    期望文档: {expected}")
                print(f"    召回结果: {hits_str}")
                print(f"    原因: {'产品识别错误' if not r.product_correct else '未召回期望文档'}")
        if fail_count == 0:
            print("  🎉 所有 case 均通过！")

        # 误召回详情
        print(f"\n{'─' * 70}")
        print("⚠️  误召回详情（召回了非目标产品的专属文档）")
        print(f"{'─' * 70}")
        fp_count = 0
        for r in self.results:
            if r.false_positive:
                fp_count += 1
                hits_str = " | ".join([f"{h['source']}({h['score']})" for h in r.hits[:3]])
                print(f"  [{r.case_id}] {r.query}")
                print(f"    召回结果: {hits_str}")
        if fp_count == 0:
            print("  🎉 无跨产品误召回！")

        print(f"\n{'=' * 70}")

        # 返回结构化结果供后续使用
        return {
            "mode": "hybrid" if self.use_vector else "keyword_only",
            "total_cases": total,
            "product_accuracy": product_acc,
            "hit_rate": hit_rate,
            "avg_recall": avg_recall,
            "avg_mrr": avg_mrr,
            "false_positive_rate": fp_rate,
            "type_breakdown": {k: dict(v) for k, v in type_stats.items()},
        }


async def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(script_dir, "dataset.json")
    data_dirs = "csbot/knowledge/data,知识库0501"

    # 检测是否有 embedding key，有则启用混合检索
    has_embedding_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("EMBEDDING_API_KEY"))
    use_vector = has_embedding_key

    bench = KBRecallBenchmark(
        dataset_path=dataset_path,
        data_dirs=data_dirs,
        use_vector=use_vector,
    )

    bench.load_dataset()
    await bench.setup()
    await bench.run()
    summary = bench.report()

    # 可选：将结果写入 JSON
    result_path = os.path.join(script_dir, "result.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n📄 详细结果已保存: {result_path}")


if __name__ == "__main__":
    asyncio.run(main())
