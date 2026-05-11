#!/usr/bin/env python3
"""阈值扫描：对比不同相似度阈值下的召回率表现"""
import asyncio
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from csbot.knowledge.loader import KnowledgeLoader
from csbot.knowledge.index import KnowledgeIndex
from csbot.knowledge.kb_search import KBSearchSkill

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def run_with_threshold(dataset, data_dirs, threshold):
    loader = KnowledgeLoader()
    index = KnowledgeIndex()
    docs = loader.load_all(data_dirs)
    index.add_batch(docs)

    skill = KBSearchSkill(index, provider=None)
    skill.SIMILARITY_THRESHOLD = threshold

    product_ok = 0
    hit_ok = 0
    total_recall = 0.0
    total_mrr = 0.0
    uncertain_count = 0
    no_hit_count = 0

    for case in dataset:
        tool_result = await skill.execute(case["query"], top_k=3)
        raw = tool_result.result
        detected = raw.get("detected_product", "")
        hits = raw.get("hits", [])

        if "第三方" in detected or "非 Kimi" in detected:
            detected_prod = "third_party"
        elif "不确定" in detected:
            detected_prod = "uncertain"
            uncertain_count += 1
        else:
            reverse_map = {v: k for k, v in skill.PRODUCT_NAMES.items()}
            detected_prod = reverse_map.get(detected, detected)

        if detected_prod == case["expected_product"]:
            product_ok += 1

        hit_sources = [h["source"] for h in hits]
        expected = case.get("expected_sources", [])
        recall = 0.0
        mrr = 0.0
        if expected:
            matched = [s for s in expected if s in hit_sources]
            recall = len(matched) / len(expected)
            for rank, src in enumerate(hit_sources, 1):
                if src in expected:
                    mrr = 1.0 / rank
                    break

        if recall > 0:
            hit_ok += 1
        if not hits:
            no_hit_count += 1

        total_recall += recall
        total_mrr += mrr

    total = len(dataset)
    return {
        "threshold": threshold,
        "product_acc": product_ok / total,
        "hit_rate": hit_ok / total,
        "avg_recall": total_recall / total,
        "avg_mrr": total_mrr / total,
        "uncertain_rate": uncertain_count / total,
        "no_hit_rate": no_hit_count / total,
    }


async def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, "dataset.json"), "r", encoding="utf-8") as f:
        dataset = json.load(f)
    data_dirs = os.path.join(PROJECT_ROOT, "csbot/knowledge/data") + "," + os.path.join(PROJECT_ROOT, "知识库0501")

    thresholds = [0.45, 0.35, 0.25, 0.15, 0.10, 0.05]
    results = []
    for th in thresholds:
        print(f"\n[Running] threshold = {th} ...")
        r = await run_with_threshold(dataset, data_dirs, th)
        results.append(r)
        print(f"  product_acc={r['product_acc']:.1%} hit_rate={r['hit_rate']:.1%} "
              f"avg_recall={r['avg_recall']:.1%} avg_mrr={r['avg_mrr']:.3f} "
              f"uncertain={r['uncertain_rate']:.1%} no_hit={r['no_hit_rate']:.1%}")

    print("\n" + "=" * 90)
    print("📊 阈值扫描结果对比（关键词-only 模式）")
    print("=" * 90)
    print(f"{'Threshold':>10} | {'Product Acc':>12} | {'Hit Rate':>10} | {'Avg Recall':>11} | {'MRR':>8} | {'Uncertain':>10} | {'No Hit':>8}")
    print("-" * 90)
    for r in results:
        print(f"{r['threshold']:>10.2f} | {r['product_acc']:>11.1%} | {r['hit_rate']:>9.1%} | "
              f"{r['avg_recall']:>10.1%} | {r['avg_mrr']:>7.3f} | {r['uncertain_rate']:>9.1%} | {r['no_hit_rate']:>7.1%}")

    best = max(results, key=lambda x: (x['hit_rate'], x['product_acc']))
    print(f"\n✅ 推荐阈值: {best['threshold']} (Hit Rate {best['hit_rate']:.1%}, Product Acc {best['product_acc']:.1%})")

    out = os.path.join(script_dir, "threshold_sweep.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📄 结果已保存: {out}")


if __name__ == "__main__":
    asyncio.run(main())
