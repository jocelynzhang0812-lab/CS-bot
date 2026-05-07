from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from csbot.knowledge.index import KnowledgeIndex
from csbot.nlp.aliases import expand_for_intent_detection
from typing import Any, Dict


class KBSearchSkill(BaseTool):
    """知识库检索 Skill，供 LLM 调用。支持向量语义检索 + 关键词混合召回。
    支持多产品分流：根据查询内容自动识别用户咨询的 Kimi 产品，只检索对应产品的知识库文档。"""

    # ── 文档来源 → 产品映射 ─────────────────────────────
    SOURCE_PRODUCT_MAP = {
        # Help center — 按产品隔离
        "help_center/kimi-code.md": "code",
        "help_center/kimi-api.md": "api",
        "help_center/websites-help.md": "websites",
        "help_center/docs-and-sheets-help.md": "docs_sheets",
        # Help center — 通用文档（所有产品可见）
        "help_center/membership-help.md": "general",
        "help_center/new-user-guide.md": "general",
        "help_center/others-help.md": "general",
        # 核心文档默认归属 Claw（支持 csbot/knowledge/data/ 和 知识库0501/ 两种路径）
        "功能使用.md": "claw",
        "常见bug.md": "claw",
        "错误码速查表.md": "claw",
        "会员权益.md": "claw",
        "平台接入与鉴权.md": "claw",
        "问题上报与用户交流群.md": "claw",
        "部署方式分类.md": "claw",
        "桌面claw.md": "claw",
        "安卓claw.md": "claw",
        "claw群聊.md": "claw",
        "云端claw.md": "claw",
        # 知识库0501 子目录映射
        "kimi claw分类/功能使用.md": "claw",
        "kimi claw分类/常见bug.md": "claw",
        "kimi claw分类/错误码速查表.md": "claw",
        "kimi claw分类/会员权益.md": "claw",
        "kimi claw分类/平台接入与鉴权.md": "claw",
        "kimi claw分类/问题上报与用户交流群.md": "claw",
        "kimi claw分类/部署方式分类.md": "claw",
        "kimi claw分类/桌面claw.md": "claw",
        "kimi claw分类/安卓claw.md": "claw",
        "kimi claw分类/claw群聊.md": "claw",
        "kimi claw分类/云端claw.md": "claw",
        "kimi claw分类/客服.md": "general",
        "客服.md": "general",
    }

    # 产品识别关键词（查询中包含时判定为对应产品）
    PRODUCT_KEYWORDS = {
        "claw": {
            "claw", "openclaw", "bot", "agent", "部署", "群聊",
            "dashboard", "记忆", "工作空间", "bot id",
        },
        "code": {
            "kimi code", "kimi-code", "kimi cli", "claude code", "roo code",
            "vscode 插件", "vs code 插件", "编程", "ide", "代码",
        },
        "api": {
            "kimi api", "kimi-api", "platform.kimi.ai", "api key", "apikey",
            "sdk", "curl", "开发者", "开放平台", "接口",
        },
        "websites": {
            "websites", "kimi websites", "建站", "网站", "网页搭建",
        },
        "docs_sheets": {
            "kimi docs", "kimi sheets", "智能文档", "智能表格",
            "docs-and-sheets", "doc", "sheet",
        },
        "app": {
            "网页版 kimi", "kimi 网页版", "kimi app", "手机端 kimi",
            "kimi.com", "对话", "聊天",
        },
        "research": {
            "深度研究", "deep research", "ppt 生成", "ppt", "agent 集群", "研究",
        },
    }

    # 明确拒绝的第三方产品（不是 Kimi 的产品）
    # 注意：以下产品名与 Kimi Claw 无关，严禁误判为 Kimi 产品
    THIRD_PARTY_KEYWORDS = {
        "jsv claw", "jsvclaw",
        "第三方 openclaw", "其他公司的 claw", "别的公司的 claw",
        "其他厂商的 claw", "非 kimi 的 claw",
        # 用户明确提及的非 Kimi 产品（扩展列表）
        "apkclaw", "clawra", "oneclaw", "moltbook", "workbuddy", "qclaw", "skyclaw",
    }

    # 产品友好名称（返回给 LLM 使用）
    PRODUCT_NAMES = {
        "claw": "Kimi Claw",
        "code": "Kimi Code",
        "api": "Kimi API",
        "websites": "Kimi Websites",
        "docs_sheets": "Kimi Docs & Sheets",
        "app": "Kimi 网页版/App",
        "research": "深度研究/PPT",
    }

    def __init__(self, index: KnowledgeIndex, provider=None):
        super().__init__(
            "search_knowledge_base",
            "检索 Kimi 产品客服知识库。支持多产品分流：根据查询自动识别用户咨询的 Kimi 产品"
            "（Claw / Code / API / Websites / Docs & Sheets / 网页版 / 深度研究等），"
            "并只返回对应产品的知识库文档。注意：非 Kimi 产品（如第三方 Claw）的问题应直接拒绝。",
        )
        self.index = index
        self.provider = provider

    # ── 产品识别 ─────────────────────────────────────────

    # 置信度阈值：最佳与次佳差距不足此值时视为不确定
    UNCERTAINTY_GAP = 1

    def _detect_product(self, query: str) -> str:
        """识别用户咨询的 Kimi 产品，返回产品标识符。
        若关键词匹配模糊（最高与次高同分或均为 0）返回 'uncertain'。
        支持口语化别名映射（如"小龙虾"→claw）。
        """
        # 先进行别名扩展，保留原始查询的同时加入映射后的术语
        expanded = expand_for_intent_detection(query)
        q = expanded.lower()

        # 第三方 Claw 直接标记
        if any(kw in q for kw in self.THIRD_PARTY_KEYWORDS):
            return "third_party"

        scores = {}
        for product, keywords in self.PRODUCT_KEYWORDS.items():
            scores[product] = sum(1 for kw in keywords if kw in q)

        if not scores or max(scores.values()) == 0:
            return "uncertain"

        best = max(scores, key=scores.get)
        best_score = scores[best]

        # 检查是否有其他产品与最佳分数接近（差距 < UNCERTAINTY_GAP）
        for prod, sc in scores.items():
            if prod != best and sc > 0 and (best_score - sc) < self.UNCERTAINTY_GAP:
                return "uncertain"

        return best

    # ── 结果过滤 ─────────────────────────────────────────

    def _filter_by_product(self, results, product: str) -> list:
        """按产品过滤检索结果"""
        filtered = []
        for r in results:
            src = r.doc.source
            doc_product = self.SOURCE_PRODUCT_MAP.get(src, "claw")

            # 通用文档所有产品都可以访问
            if doc_product == "general":
                filtered.append(r)
                continue

            # 文档明确属于目标产品
            if doc_product == product:
                filtered.append(r)
                continue

            # 非 claw 查询不允许访问其他产品的专属文档和 claw 核心文档
            if product != "claw":
                continue

            # claw 查询允许访问所有非专属文档
            if product == "claw" and doc_product not in ("code", "api", "websites", "docs_sheets"):
                filtered.append(r)
                continue

        return filtered

    # ── 执行检索 ─────────────────────────────────────────

    async def execute(self, query: str, top_k: int = 3, **kwargs) -> ToolResult:
        product = self._detect_product(query)

        # 第三方产品直接拒绝
        if product == "third_party":
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "hit": False,
                    "hits": [],
                    "reply_hint": "OUT_OF_SCOPE",
                    "detected_product": "第三方 Claw（非 Kimi 产品）",
                    "reason": "查询涉及非 Kimi 产品（如第三方 Claw），不在服务范围内",
                },
            )

        # 产品类型不确定时拒绝回答，防止跨产品误答
        if product == "uncertain":
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "hit": False,
                    "hits": [],
                    "reply_hint": "UNCERTAIN_PRODUCT",
                    "detected_product": "不确定",
                    "reason": "无法根据查询内容确定用户咨询的 Kimi 产品类型",
                },
            )

        # 扩大检索量再过滤，保证分流后仍有足够结果
        results = await self.index.search(query, top_k=top_k * 3, provider=self.provider)
        filtered = self._filter_by_product(results, product)
        filtered = filtered[:top_k]

        hits = []
        for r in filtered:
            hits.append({
                "title": r.doc.title,
                "content": r.doc.content,
                "score": r.score,
                "source": r.doc.source,
                "tags": r.doc.tags,
            })

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={
                "hit": len(hits) > 0 and hits[0].get("score", 0) >= 0.25,
                "hits": hits,
                "detected_product": self.PRODUCT_NAMES.get(product, product),
                "reply_hint": "基于知识库直接回答" if hits else "未命中，进入排查流程",
            },
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "query": {"type": "string", "description": "用户问题或关键词"},
            "top_k": {"type": "integer", "default": 3, "description": "返回几条结果"},
        }
