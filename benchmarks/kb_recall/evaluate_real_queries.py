#!/usr/bin/env python3
"""真实用户查询召回率评测"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from csbot.knowledge.loader import KnowledgeLoader
from csbot.knowledge.index import KnowledgeIndex
from csbot.knowledge.kb_search import KBSearchSkill

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    dataset_path = os.path.join(os.path.dirname(__file__), "real_user_queries.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"[Dataset] 加载 {len(dataset)} 条真实用户查询\n")

    loader = KnowledgeLoader()
    index = KnowledgeIndex()
    docs = loader.load_all(os.path.join(PROJECT_ROOT, "csbot/knowledge/data") + "," + os.path.join(PROJECT_ROOT, "知识库0501"))
    index.add_batch(docs)
    print(f"[Setup] 共加载 {len(docs)} 条文档\n")

    skill = KBSearchSkill(index, provider=None)
    # 使用当前优化后的阈值
    skill.SIMILARITY_THRESHOLD = 0.35

    product_ok = 0
    hit_ok = 0
    total_recall = 0.0
    total_mrr = 0.0
    fp_count = 0
    uncertain_count = 0
    no_hit_count = 0

    results = []

    for case in dataset:
        query = case["query"]
        tool_result = await skill.execute(query, top_k=3)
        raw = tool_result.result
        detected = raw.get("detected_product", "")
        hits = raw.get("hits", [])

        # normalize detected product
        if "第三方" in detected or "非 Kimi" in detected:
            detected_prod = "third_party"
        elif "不确定" in detected:
            detected_prod = "uncertain"
            uncertain_count += 1
        else:
            reverse_map = {v: k for k, v in skill.PRODUCT_NAMES.items()}
            detected_prod = reverse_map.get(detected, detected)

        expected_product = case["expected_product"]
        expected_sources = case.get("expected_sources", [])
        product_correct = detected_prod == expected_product
        if product_correct:
            product_ok += 1

        hit_sources = [h["source"] for h in hits]
        recall = 0.0
        mrr = 0.0
        if expected_sources:
            matched = [s for s in expected_sources if s in hit_sources]
            recall = len(matched) / len(expected_sources)
            for rank, src in enumerate(hit_sources, 1):
                if src in expected_sources:
                    mrr = 1.0 / rank
                    break

        if recall > 0:
            hit_ok += 1
        if not hits:
            no_hit_count += 1

        # false positive
        fp = False
        if expected_product not in ("uncertain", "third_party") and expected_sources:
            for h in hits:
                src = h["source"]
                if src not in expected_sources:
                    doc_product = skill.SOURCE_PRODUCT_MAP.get(src, "claw")
                    if doc_product != expected_product and doc_product != "general":
                        fp = True
                        break
        if fp:
            fp_count += 1

        total_recall += recall
        total_mrr += mrr

        results.append({
            "id": case["id"],
            "query": query,
            "detected": detected_prod,
            "expected": expected_product,
            "product_correct": product_correct,
            "recall": recall,
            "mrr": mrr,
            "hits": hit_sources[:3],
            "fp": fp,
        })

    total = len(dataset)
    print("=" * 80)
    print("📊 真实用户查询召回率评测报告")
    print("=" * 80)
    print(f"测试用例数: {total}")
    print(f"\n🎯 核心指标")
    print(f"  产品识别准确率: {product_ok / total:.1%}")
    print(f"  文档召回命中率: {hit_ok / total:.1%}")
    print(f"  平均召回率:     {total_recall / total:.1%}")
    print(f"  平均 MRR:       {total_mrr / total:.3f}")
    print(f"  误召回率:       {fp_count / total:.1%}")
    print(f"  uncertain 比例: {uncertain_count / total:.1%}")
    print(f"  无命中比例:     {no_hit_count / total:.1%}")

    # 按 case_type 分组
    from collections import defaultdict
    type_stats = defaultdict(lambda: {"total": 0, "hit": 0, "product_ok": 0})
    for r in results:
        ct = next((c.get("case_type", "unknown") for c in dataset if c["id"] == r["id"]), "unknown")
        s = type_stats[ct]
        s["total"] += 1
        if r["recall"] > 0:
            s["hit"] += 1
        if r["product_correct"]:
            s["product_ok"] += 1

    print(f"\n📁 按问题类型分组")
    print(f"  {'类型':<15} {'总数':>6} {'命中':>8} {'命中率':>8} {'产品识别':>10}")
    for ct, s in sorted(type_stats.items()):
        print(f"  {ct:<15} {s['total']:>6} {s['hit']:>8} {s['hit']/s['total']:>7.0%} {s['product_ok']/s['total']:>9.0%}")

    print(f"\n❌ 未命中的 case 详情")
    fail_count = 0
    for r in results:
        if r["recall"] == 0:
            fail_count += 1
            hits_str = " | ".join(r["hits"]) if r["hits"] else "(无命中)"
            print(f"\n  [{r['id']}] {r['query'][:60]}")
            print(f"    期望: {r['expected']} | 识别: {r['detected']}")
            print(f"    召回: {hits_str}")
    if fail_count == 0:
        print("  🎉 全部命中！")

    # 保存结果
    out = os.path.join(os.path.dirname(__file__), "real_user_results.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total": total,
                "product_accuracy": product_ok / total,
                "hit_rate": hit_ok / total,
                "avg_recall": total_recall / total,
                "avg_mrr": total_mrr / total,
                "fp_rate": fp_count / total,
                "uncertain_rate": uncertain_count / total,
                "no_hit_rate": no_hit_count / total,
            },
            "type_breakdown": {k: dict(v) for k, v in type_stats.items()},
            "details": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n📄 详细结果已保存: {out}")

if __name__ == "__main__":
    asyncio.run(main())
