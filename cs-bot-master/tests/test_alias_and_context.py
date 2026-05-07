"""测试别名映射与上下文意图识别"""
import asyncio
import sys
sys.path.insert(0, ".")

from csbot.nlp.aliases import (
    normalize_user_expression,
    expand_for_intent_detection,
    is_vague_expression,
    infer_context_from_history,
)
from csbot.nlp.intake import CSIntakeSkill
from csbot.knowledge.base import KnowledgeDoc, DocType
from csbot.knowledge.index import KnowledgeIndex
from csbot.knowledge.kb_search import KBSearchSkill


def test_alias_normalization():
    """测试口语化别名映射"""
    # 别名映射会将口语化表达替换为标准术语，用于意图检测
    assert "claw" in normalize_user_expression("我的小龙虾卡住了")
    assert "卡顿" in normalize_user_expression("我的小龙虾卡住了")
    assert "claw" in normalize_user_expression("小爪子没反应")
    assert "不回消息" in normalize_user_expression("小爪子没反应")
    assert "部署失败" in normalize_user_expression("装不上")
    assert normalize_user_expression("正常文本") == "正常文本"
    print("✅ 别名映射正确")


def test_expand_for_intent():
    """测试意图检测扩展文本"""
    expanded = expand_for_intent_detection("小龙虾挂了")
    assert "小龙虾" in expanded
    assert "claw" in expanded
    assert "离线" in expanded
    print("✅ 意图检测扩展文本正确")


def test_vague_detection():
    """测试模糊表达检测"""
    assert is_vague_expression("卡住了") is True
    assert is_vague_expression("崩了") is True
    assert is_vague_expression("怎么部署") is False
    assert is_vague_expression("会员怎么退款") is False
    print("✅ 模糊表达检测正确")


def test_context_inference():
    """测试基于上下文的意图推断"""
    # 场景1: 孤立模糊表达，无上下文 → 置信度低，需要追问
    r1 = infer_context_from_history("卡住了", {}, [])
    assert r1["confidence"] == "low"
    assert r1["needs_clarify"] is True
    print("✅ 无上下文模糊表达 → 低置信度 + 需追问")

    # 场景2: 有已确认的产品类型
    r2 = infer_context_from_history("卡住了", {"product_type": "desktop"}, [])
    assert r2["inferred_product_type"] == "desktop"
    assert r2["confidence"] == "medium"
    print("✅ 继承已确认产品类型")

    # 场景3: 历史对话涉及部署
    history = [
        {"role": "user", "content": "我在部署 Kimi Claw Desktop"},
        {"role": "assistant", "content": "好的，请描述问题"},
        {"role": "user", "content": "卡住了"},
    ]
    r3 = infer_context_from_history("卡住了", {}, history)
    assert r3["inferred_issue_type"] == "部署/安装问题"
    assert r3["confidence"] == "high"
    assert r3["needs_clarify"] is False
    print("✅ 部署上下文 + '卡住了' → 推断为部署问题")

    # 场景4: 历史对话涉及聊天功能
    history2 = [
        {"role": "user", "content": "我的 claw 不回消息"},
        {"role": "assistant", "content": "请提供更多细节"},
        {"role": "user", "content": "又卡住了"},
    ]
    r4 = infer_context_from_history("又卡住了", {}, history2)
    assert r4["inferred_issue_type"] == "对话功能异常"
    print("✅ 对话上下文 + '卡住了' → 推断为对话功能异常")

    # 场景5: 历史对话涉及会员
    history3 = [
        {"role": "user", "content": "会员充值不了"},
        {"role": "assistant", "content": "请描述现象"},
        {"role": "user", "content": "卡住了"},
    ]
    r5 = infer_context_from_history("卡住了", {}, history3)
    assert r5["inferred_module"] == "会员额度"
    print("✅ 会员上下文 + '卡住了' → 推断为会员额度问题")


async def test_kb_search_with_alias():
    """测试知识库产品识别支持别名"""
    index = KnowledgeIndex()
    docs = [
        KnowledgeDoc(
            id="c1", doc_type=DocType.PRODUCT, title="Claw 部署",
            content="云端 Kimi Claw 可以通过 kimi.com 一键部署。",
            keywords=["部署", "claw", "云端"], tags=["产品指南", "claw"],
            source="功能使用.md", meta={"platform": "通用"},
        ),
    ]
    index.add_batch(docs)
    skill = KBSearchSkill(index, provider=None)

    # "小龙虾" 应通过别名映射识别为 claw
    product = skill._detect_product("我的小龙虾怎么部署")
    assert product == "claw", f"期望 claw，实际得到 {product}"
    print("✅ '小龙虾' 别名识别为 claw")

    # "小爪子" 也应识别为 claw
    product2 = skill._detect_product("小爪子挂了")
    assert product2 == "claw", f"期望 claw，实际得到 {product2}"
    print("✅ '小爪子' 别名识别为 claw")


async def test_intake_with_context():
    """测试 intake 结合上下文的意图识别"""
    skill = CSIntakeSkill()

    # 场景1: 孤立模糊消息
    r1 = await skill.execute("卡住了", mentioned=True, session_state={}, history=[])
    assert r1.result["needs_clarify"] is True
    assert "具体是在哪个环节" in r1.result["引导话术"] or "确认" in r1.result["引导话术"]
    print("✅ 孤立'卡住了' → 需要追问")

    # 场景2: 有产品类型上下文
    r2 = await skill.execute(
        "卡住了", mentioned=True,
        session_state={"product_type": "desktop", "module": "故障排查"},
        history=[{"role": "user", "content": "我在装 Desktop 版"}],
    )
    assert r2.result["product_type"] == "desktop"
    print("✅ 有上下文时 '卡住了' → 继承产品类型")

    # 场景3: 别名识别
    r3 = await skill.execute("小龙虾不回消息", mentioned=True, session_state={}, history=[])
    assert r3.result["intent"] == "tech_bug"
    print("✅ '小龙虾不回消息' → 识别为 claw 故障")


async def main():
    test_alias_normalization()
    test_expand_for_intent()
    test_vague_detection()
    test_context_inference()
    await test_kb_search_with_alias()
    await test_intake_with_context()
    print("\n🎉 别名映射与上下文意图识别测试全部通过！")


if __name__ == "__main__":
    asyncio.run(main())
