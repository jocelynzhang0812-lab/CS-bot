"""测试多产品分流与知识库检索"""
import asyncio
import sys
sys.path.insert(0, ".")

from csbot.knowledge.base import KnowledgeDoc, DocType, SearchResult
from csbot.knowledge.index import KnowledgeIndex
from csbot.knowledge.kb_search import KBSearchSkill


def build_mock_index() -> KnowledgeIndex:
    """构建一个包含多产品文档的模拟索引"""
    index = KnowledgeIndex()
    docs = [
        KnowledgeDoc(
            id="c1", doc_type=DocType.PRODUCT, title="Claw 部署",
            content="云端 Kimi Claw 可以通过 kimi.com 一键部署。",
            keywords=["部署", "claw", "云端"], tags=["产品指南", "claw"],
            source="功能使用.md", meta={"platform": "通用"},
        ),
        KnowledgeDoc(
            id="c2", doc_type=DocType.TROUBLESHOOT, title="Claw 失忆",
            content="Kimi Claw 失忆可能是因为记忆文件损坏。",
            keywords=["失忆", "记忆", "claw"], tags=["故障排查", "claw"],
            source="常见bug.md", meta={"category": "troubleshoot"},
        ),
        KnowledgeDoc(
            id="code1", doc_type=DocType.PRODUCT, title="Kimi Code 安装",
            content="Kimi Code 可以通过 VS Code 插件市场安装。",
            keywords=["vscode", "插件", "kimi code", "安装"], tags=["产品指南", "code"],
            source="help_center/kimi-code.md", meta={"category": "help_center"},
        ),
        KnowledgeDoc(
            id="api1", doc_type=DocType.CONFIG, title="API Key 申请",
            content="在 platform.kimi.ai 申请 API Key。",
            keywords=["api key", "platform.kimi.ai", "开发者"], tags=["帮助中心", "Kimi API"],
            source="help_center/kimi-api.md", meta={"category": "help_center"},
        ),
        KnowledgeDoc(
            id="g1", doc_type=DocType.POLICY, title="会员退款",
            content="会员退款可以通过设置页取消订阅。",
            keywords=["退款", "会员", "取消订阅"], tags=["帮助中心", "会员权益"],
            source="help_center/membership-help.md", meta={"policy_type": "membership"},
        ),
    ]
    index.add_batch(docs)
    return index


async def test_product_detection():
    index = build_mock_index()
    skill = KBSearchSkill(index, provider=None)

    # 1. 明确属于 Claw
    assert skill._detect_product("我的 claw 失忆了") == "claw"
    print("✅ 明确 Claw 查询识别正确")

    # 2. 明确属于 Code
    assert skill._detect_product("kimi code 怎么安装") == "code"
    print("✅ 明确 Code 查询识别正确")

    # 3. 明确属于 API
    assert skill._detect_product("api key 怎么申请") == "api"
    print("✅ 明确 API 查询识别正确")

    # 4. 模糊查询 → uncertain
    assert skill._detect_product("你好") == "uncertain"
    print("✅ 模糊查询返回 uncertain")

    # 5. 第三方 Claw
    assert skill._detect_product("jsv claw 怎么用") == "third_party"
    print("✅ 第三方 Claw 识别正确")

    # 6. 边界模糊：同时包含 code 和 api 关键词且得分相同（差距 < UNCERTAINTY_GAP）
    # "kimi code api key" → code 匹配 "kimi code"(1)，api 匹配 "api key"(1)，差距=0 < 1 → uncertain
    assert skill._detect_product("kimi code api key") == "uncertain"
    print("✅ 边界模糊查询返回 uncertain")


async def test_filter_by_product():
    index = build_mock_index()
    skill = KBSearchSkill(index, provider=None)

    # 模拟搜索结果（不按产品过滤前的原始结果）
    raw_results = [
        SearchResult(doc=index.all()[0], score=0.9, matched_keyword="claw", snippet="..."),  # claw
        SearchResult(doc=index.all()[1], score=0.8, matched_keyword="claw", snippet="..."),  # claw
        SearchResult(doc=index.all()[2], score=0.7, matched_keyword="code", snippet="..."), # code
        SearchResult(doc=index.all()[4], score=0.6, matched_keyword="会员", snippet="..."), # general
    ]

    # Claw 查询：应该看到 claw + general
    filtered = skill._filter_by_product(raw_results, "claw")
    sources = [r.doc.source for r in filtered]
    assert "功能使用.md" in sources
    assert "常见bug.md" in sources
    assert "help_center/membership-help.md" in sources
    assert "help_center/kimi-code.md" not in sources
    print("✅ Claw 查询过滤正确（包含通用文档，排除其他产品专属文档）")

    # Code 查询：应该只看到 code + general
    filtered = skill._filter_by_product(raw_results, "code")
    sources = [r.doc.source for r in filtered]
    assert "help_center/kimi-code.md" in sources
    assert "help_center/membership-help.md" in sources
    assert "功能使用.md" not in sources
    print("✅ Code 查询过滤正确（只能看到 Code + 通用文档）")


async def test_kb_search_uncertain():
    """测试 search_knowledge_base 对 uncertain 产品的返回"""
    index = build_mock_index()
    skill = KBSearchSkill(index, provider=None)

    result = await skill.execute("你好", top_k=3)
    assert result.result["detected_product"] == "不确定"
    assert result.result["reply_hint"] == "UNCERTAIN_PRODUCT"
    assert result.result["hit"] is False
    print("✅ uncertain 查询返回正确提示")


async def main():
    await test_product_detection()
    await test_filter_by_product()
    await test_kb_search_uncertain()
    print("\n🎉 所有测试通过！")


if __name__ == "__main__":
    asyncio.run(main())
