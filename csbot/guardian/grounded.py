"""
Hallucination Guardian —— 从根源杜绝知识库无关内容的硬约束防御层

设计原则：
1. 检索先行（Retrieve-First）：LLM 生成之前必须完成知识库检索
2. 硬阻断（Hard Gate）：未命中时直接返回固定话术，不经过 LLM
3. 引用约束（Citation Lock）：要求 LLM 在回答中标注信息来源
4. 后验验证（Post-Hoc Check）：生成后用程序验证答案是否 grounded 于检索结果
"""

import re
import json
from typing import List, Dict, Any, Tuple, Optional
from difflib import SequenceMatcher


class CitationParser:
    """解析 LLM 回答中的引用标记，如 [来源1]、[来源A] 等"""

    CITATION_PATTERN = re.compile(r"[【\[]\s*来源\s*(\d+|[a-zA-Z])\s*[】\]]")

    @classmethod
    def extract_citations(cls, text: str) -> List[str]:
        """提取所有引用标记，返回如 ['1', '2']"""
        matches = cls.CITATION_PATTERN.findall(text)
        return list(dict.fromkeys(matches))  # 去重保序

    @classmethod
    def strip_citations(cls, text: str) -> str:
        """去除引用标记，得到纯文本用于验证"""
        return cls.CITATION_PATTERN.sub("", text).strip()


class GroundingChecker:
    """
    后验验证器：检查 bot_reply 中的信息是否能在 retrieval_hits 中找到依据。
    
    策略：
    - 将回答拆分为语义块（句子/子句）
    - 对每个语义块，计算其与所有检索结果文本的最大相似度
    - 若整体覆盖率低于阈值，判定为幻觉
    """

    def __init__(self, min_coverage: float = 0.85, min_similarity: float = 0.70):
        """
        :param min_coverage: 语义块中必须有至少多少比例能在检索结果中找到相似依据
        :param min_similarity: 单个语义块与检索文本的最低相似度阈值
        """
        self.min_coverage = min_coverage
        self.min_similarity = min_similarity

    def check(
        self,
        bot_reply: str,
        retrieval_hits: List[Dict[str, Any]],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        :return: (is_grounded, detail_dict)
        is_grounded=True 表示通过验证，无幻觉嫌疑
        """
        # 如果回答本身就是固定话术，跳过验证
        stripped = bot_reply.strip()
        fixed_phrases = {
            "抱歉，这个问题我暂时无法回答",
            "抱歉，这个问题不在 Kimi 的服务范围内",
            "建议您联系人工客服",
            "已记录您的请求",
            "已提交给技术团队",
            "感谢您的反馈",
        }
        if any(fp in stripped for fp in fixed_phrases):
            return True, {"reason": "fixed_phrase_skip"}

        if not bot_reply or not retrieval_hits:
            # 无回答或无检索结果，视为不通过
            return False, {"reason": "empty_reply_or_no_hits", "coverage": 0.0}

        # 1. 收集所有检索文本（标题 + 内容）
        corpus_texts = []
        for hit in retrieval_hits:
            title = hit.get("title", "")
            content = hit.get("content", "")
            corpus_texts.append(f"{title}\n{content}")

        corpus = "\n".join(corpus_texts)

        # 2. 将回答拆分为语义块（按句子切分）
        pure_reply = CitationParser.strip_citations(bot_reply)
        chunks = self._split_into_chunks(pure_reply)

        if not chunks:
            return True, {"reason": "no_substantive_content", "coverage": 1.0}

        # 3. 计算每个语义块与检索文本的相似度
        matched = 0
        chunk_details = []
        for chunk in chunks:
            sim = self._max_similarity(chunk, corpus_texts)
            is_match = sim >= self.min_similarity
            if is_match:
                matched += 1
            chunk_details.append({
                "chunk": chunk,
                "max_similarity": round(sim, 3),
                "matched": is_match,
            })

        coverage = matched / len(chunks) if chunks else 1.0
        is_grounded = coverage >= self.min_coverage

        detail = {
            "reason": "coverage_check",
            "coverage": round(coverage, 3),
            "threshold": self.min_coverage,
            "chunks_total": len(chunks),
            "chunks_matched": matched,
            "chunk_details": chunk_details,
        }
        return is_grounded, detail

    @staticmethod
    def _split_into_chunks(text: str) -> List[str]:
        """
        将文本拆分为语义验证单元。
        - 先按句子切分
        - 过滤掉过短（<6字）的句子（客套话、过渡语）
        - 对长句按逗号/分号再切分
        """
        # 按句号、问号、感叹号切分句子
        raw_sentences = re.split(r"(?<=[。！？\n])", text)
        chunks = []
        for s in raw_sentences:
            s = s.strip()
            if len(s) < 6:
                continue
            # 长句按逗号/分号再切
            if len(s) > 40:
                sub_chunks = re.split(r"[,，;；]", s)
                for sub in sub_chunks:
                    sub = sub.strip()
                    if len(sub) >= 6:
                        chunks.append(sub)
            else:
                chunks.append(s)
        return chunks

    @staticmethod
    def _max_similarity(chunk: str, corpus_texts: List[str]) -> float:
        """计算 chunk 与语料库中任意文本的最大相似度"""
        best = 0.0
        for doc_text in corpus_texts:
            # 快速子串匹配：如果 chunk 直接出现在文档中，视为高度匹配
            if chunk.lower() in doc_text.lower():
                return 1.0
            # 否则用 SequenceMatcher
            sim = SequenceMatcher(None, chunk.lower(), doc_text.lower()).ratio()
            if sim > best:
                best = sim
            # 也尝试 chunk 与文档的滑动窗口匹配（处理长文档）
            if len(doc_text) > 200:
                window_size = min(len(chunk) * 3, 200)
                for i in range(0, len(doc_text) - window_size + 1, window_size // 2):
                    window = doc_text[i:i + window_size]
                    sim = SequenceMatcher(None, chunk.lower(), window.lower()).ratio()
                    if sim > best:
                        best = sim
        return best


class HardRAGGate:
    """
    硬阻断门：在 LLM 介入之前，强制完成知识库检索并做路由决策。
    
    规则：
    - 命中知识库 → 放行，携带检索结果进入 LLM
    - 未命中 / 产品不确定 / 第三方产品 → 硬阻断，返回固定话术，不调用 LLM
    """

    # 允许绕过检索的意图白名单（纯操作类、纯情绪类）
    BYPASS_INTENTS = {
        "human_request",      # 用户明确要求转人工
        "wrong_answer",       # 用户反馈回答错误
        "product_feedback",   # 产品建议
        "special_request",    # 退款/开票等特殊请求
        "greeting",           # 纯打招呼
        "farewell",           # 纯结束语
    }

    # 硬阻断时的固定话术映射
    BLOCK_REPLY_MAP = {
        "OUT_OF_SCOPE": (
            "抱歉，这个问题不在 Kimi 的服务范围内。"
            "如果您使用的是第三方产品，请联系对应服务商。"
        ),
        "UNCERTAIN_PRODUCT": (
            "抱歉，我暂时无法确定您咨询的是哪个 Kimi 产品，"
            "这个问题我暂时无法回答，建议您联系人工客服进一步协助。"
        ),
        "KB_MISS": (
            "抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。"
        ),
        "GUARDRAIL_BLOCK": (
            "抱歉，这部分信息我无法提供。"
        ),
        "INVALID_MEMBERSHIP_PRICE": (
            "Kimi 官方会员套餐中没有此价格档位。目前提供的会员套餐为："
            "Adagio（免费）、Andante（¥49/月）、Moderato（¥99/月）、"
            "Allegretto（¥199/月）、Allegro（¥699/月）。"
        ),
    }

    @classmethod
    def should_bypass(cls, message: str, intent: Optional[str] = None) -> bool:
        """判断是否属于无需检索即可直接处理的意图"""
        if intent in cls.BYPASS_INTENTS:
            return True
        # 纯打招呼/结束语快速判断
        greeting_patterns = {"你好", "您好", "在吗", "hi", "hello", "谢谢", "再见", "拜拜"}
        if message.strip().lower() in greeting_patterns:
            return True
        # 用户明确要求转人工时 bypass 检索，确保进入 LLM 循环调用 cs_sop_router
        human_request_keywords = {"转人工", "找人工", "要人工", "人工客服", "找真人", "找客服", "接人工", "换人"}
        if any(kw in message for kw in human_request_keywords):
            return True
        return False

    @classmethod
    def get_block_reply(cls, reply_hint: str, reason: str = "") -> str:
        """根据 reply_hint 获取硬阻断回复"""
        return cls.BLOCK_REPLY_MAP.get(reply_hint, cls.BLOCK_REPLY_MAP["KB_MISS"])


class RetrievalInjector:
    """
    检索结果注入器：将知识库命中结果格式化为 LLM 上下文中的 Grounded Context。
    
    核心约束：
    - 每条文档前加 [来源N] 标记
    - 明确提示 LLM：只能基于以下文档回答，必须标注来源
    - 如果文档信息不完整，禁止补全
    """

    @classmethod
    def format_context(
        cls,
        hits: List[Dict[str, Any]],
        detected_product: str,
    ) -> str:
        if not hits:
            return (
                "\n<知识库检索_result>\n"
                "  <product>不确定</product>\n"
                "  <status>未命中</status>\n"
                "  <chunks></chunks>\n"
                "</知识库检索_result>\n"
                "\n"
                "<回答约束>\n"
                "  请仅根据知识库检索结果回答。当前结果为空，请直接告知用户：\n"
                "  「抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。」\n"
                "  严禁基于训练数据编造、推测或补全任何信息。\n"
                "</回答约束>\n"
            )

        chunks_lines = []
        for idx, hit in enumerate(hits, 1):
            title = hit.get("title", "无标题")
            content = hit.get("content", "")
            source = hit.get("source", "")
            chunk = f"""    <chunk id="{idx}">
      <title>{title}</title>
      <source>{source}</source>
      <content>
{cls._indent_content(content, 8)}
      </content>
    </chunk>"""
            chunks_lines.append(chunk)

        chunks_body = "\n".join(chunks_lines)
        return (
            "\n<知识库检索_result>\n"
            f"  <product>{detected_product}</product>\n"
            "  <status>已命中</status>\n"
            "  <chunks>\n"
            f"{chunks_body}\n"
            "  </chunks>\n"
            "</知识库检索_result>\n"
            "\n"
            "<回答约束>\n"
            "  请仅根据上述 <知识库检索_result> 中的 <chunk> 内容回答用户问题。\n"
            "  严禁添加 <chunk> 中未明确提供的信息、代码、命令、配置、步骤、参数、版本要求等。\n"
            "  即使文档信息不完整，也禁止基于训练数据补全、推测或扩展。\n"
            "  每条信息必须在句末标注来源编号，格式严格为 [来源1]、[来源2]、[来源3] 等。\n"
            "  不得编造不存在的来源编号。\n"
            "  如果 <chunk> 无法回答用户问题，请直接回复：\n"
            "  「抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。」\n"
            "</回答约束>\n"
        )

    @staticmethod
    def _indent_content(content: str, spaces: int) -> str:
        """将内容按行缩进，用于 XML 格式化。"""
        indent = " " * spaces
        lines = content.split("\n")
        return "\n".join(indent + line for line in lines)


class CodeGroundingChecker:
    """
    代码专用 grounding 验证器：检查 bot_reply 中的代码块、命令行、配置片段
    是否能在 retrieval_hits 中找到依据。

    策略：
    - 提取回答中所有代码块（```...```）和行内代码（`...`）
    - 通过启发式规则识别未格式化的代码、命令、文件路径、JSON/YAML 配置
    - 提取检索结果中的所有代码片段
    - 对每个代码片段，检查是否在知识库代码块中（标准化后匹配）
    - 若存在任何未 grounding 的代码 → 判定为幻觉，直接拦截
    """

    CODE_BLOCK_PATTERN = re.compile(r"```[\w]*\n?(.*?)```", re.DOTALL)
    INLINE_CODE_PATTERN = re.compile(r"`([^`]{3,})`")

    # 启发式：未格式化但看起来像代码/命令的内容
    # 文件路径（~/.openclaw/openclaw.json、/usr/local/bin/xxx）
    FILE_PATH_PATTERN = re.compile(
        r"(?:~|/|\.[\/])"           # 以 ~、/、./ 开头
        r"[\w\-./]+"                 # 路径字符
        r"(?:\.[a-zA-Z0-9]+)?"       # 可选扩展名
    )
    # 命令行：以常见命令开头的独立行
    COMMAND_LINE_PATTERN = re.compile(
        r"^[\s]*"                    # 行前空白
        r"(?:cp|mv|rm|cat|ls|cd|mkdir|chmod|chown|"
        r"openclaw|npx|npm|yarn|pip|python|python3|"
        r"curl|wget|ssh|git|docker|kubectl|"
        r"kimi|code|vim|nano|echo|export|source)"
        r"[\s]+[^\n]{5,}",           # 后面跟着至少5个非换行字符
        re.MULTILINE,
    )
    # JSON/YAML 结构：{ "key": "value" } 或 key: value（缩进）
    CONFIG_BLOCK_PATTERN = re.compile(
        r"(?:^|\n)"                  # 行首
        r"[\s]*\{[\s\S]{10,200}?\}"  # JSON 对象（10-200字符）
        r"|"
        r"(?:^|\n)"
        r"[\s]*[\w_]+:\s*[\w_\"\'\[][^\n]{3,}",  # key: value 行
        re.MULTILINE,
    )
    # 选项参数：--xxx 或 -x（前后有空白或行首/行尾）
    OPTION_PATTERN = re.compile(r"(?:^|\s)--[\w\-]+(?:\s|$)")

    def __init__(
        self,
        min_similarity: float = 0.70,
        min_line_match_ratio: float = 0.60,
    ):
        self.min_similarity = min_similarity
        self.min_line_match_ratio = min_line_match_ratio

    def check(
        self,
        bot_reply: str,
        retrieval_hits: List[Dict[str, Any]],
    ) -> Tuple[bool, Dict[str, Any]]:
        # 1. 提取回答中的代码片段（格式化 + 启发式）
        code_snippets = self._extract_code_snippets(bot_reply)
        if not code_snippets:
            return True, {"reason": "no_code_snippets"}

        # 2. 提取知识库中的所有代码片段
        kb_codes = self._extract_kb_codes(retrieval_hits)
        if not kb_codes:
            # 知识库中完全没有代码，但回答中有代码 → 绝对拦截
            return False, {
                "reason": "code_without_kb_support",
                "ungrounded_snippets": [
                    {"snippet": s[:200], "type": t} for s, t in code_snippets
                ],
            }

        # 3. 逐一验证
        ungrounded = []
        for snippet, snippet_type in code_snippets:
            if not self._is_grounded(snippet, kb_codes):
                ungrounded.append({
                    "snippet": snippet[:200],
                    "type": snippet_type,
                })

        if ungrounded:
            return False, {
                "reason": "ungrounded_code_snippets",
                "ungrounded_snippets": ungrounded,
                "total_snippets": len(code_snippets),
            }

        return True, {
            "reason": "all_code_grounded",
            "snippet_count": len(code_snippets),
        }

    def _extract_code_snippets(self, text: str) -> List[Tuple[str, str]]:
        """提取代码片段，返回 (snippet, type) 列表。
        同时支持格式化代码（```、`）和未格式化的启发式代码检测。
        """
        snippets = []
        seen = set()

        def _add(snippet: str, stype: str) -> None:
            s = snippet.strip()
            key = s.lower()
            if key and key not in seen and len(s) >= 5:
                seen.add(key)
                snippets.append((s, stype))

        # 1. 格式化的代码块
        for m in self.CODE_BLOCK_PATTERN.finditer(text):
            _add(m.group(1), "block")

        # 2. 格式化的行内代码
        for m in self.INLINE_CODE_PATTERN.finditer(text):
            code = m.group(1).strip()
            if len(code) >= 10:
                _add(code, "inline")
            elif len(code) >= 5 and not code.isalpha():
                _add(code, "inline")

        # 3. 启发式：文件路径（如 ~/.openclaw/openclaw.json）
        for m in self.FILE_PATH_PATTERN.finditer(text):
            path = m.group(0).strip()
            if len(path) >= 10 and "/" in path:
                _add(path, "heuristic_path")

        # 4. 启发式：命令行（独立行，以常见命令开头）
        for m in self.COMMAND_LINE_PATTERN.finditer(text):
            cmd = m.group(0).strip()
            if len(cmd) >= 10:
                _add(cmd, "heuristic_cmd")

        # 5. 启发式：JSON/YAML 配置块
        for m in self.CONFIG_BLOCK_PATTERN.finditer(text):
            cfg = m.group(0).strip()
            if len(cfg) >= 15:
                _add(cfg, "heuristic_config")

        return snippets

    def _extract_kb_codes(self, hits: List[Dict[str, Any]]) -> List[str]:
        """从检索结果中提取所有代码片段（格式化 + 启发式）"""
        codes = []
        for hit in hits:
            content = hit.get("content", "")
            title = hit.get("title", "")
            for text in (content, title):
                # 格式化代码
                for m in self.CODE_BLOCK_PATTERN.finditer(text):
                    code = m.group(1).strip()
                    if code:
                        codes.append(code)
                for m in self.INLINE_CODE_PATTERN.finditer(text):
                    code = m.group(1).strip()
                    if len(code) >= 5:
                        codes.append(code)
                # 启发式：文件路径和命令（知识库中的命令也要被索引）
                for m in self.FILE_PATH_PATTERN.finditer(text):
                    path = m.group(0).strip()
                    if len(path) >= 10 and "/" in path:
                        codes.append(path)
                for m in self.COMMAND_LINE_PATTERN.finditer(text):
                    cmd = m.group(0).strip()
                    if len(cmd) >= 10:
                        codes.append(cmd)
        return codes

    def _is_grounded(self, snippet: str, kb_codes: List[str]) -> bool:
        """检查单个代码片段是否在知识库中有依据"""
        normalized_snippet = self._normalize_code(snippet)

        for kb_code in kb_codes:
            normalized_kb = self._normalize_code(kb_code)

            # 1. 子串匹配（最严格，也最可靠）
            if normalized_snippet in normalized_kb or normalized_kb in normalized_snippet:
                return True

            # 2. 整段相似度（用于处理格式差异）
            sim = SequenceMatcher(None, normalized_snippet, normalized_kb).ratio()
            if sim >= self.min_similarity:
                return True

            # 3. 逐行匹配（用于处理长代码块中部分匹配的情况）
            if self._line_match(snippet, kb_code):
                return True

        return False

    def _normalize_code(self, code: str) -> str:
        """标准化代码：统一空白、统一换行、转小写"""
        lines = [line.strip() for line in code.splitlines()]
        lines = [line for line in lines if line]
        normalized = " ".join(
            line.replace("\t", " ").replace("  ", " ")
            for line in lines
        )
        return normalized.lower()

    def _line_match(self, snippet: str, kb_code: str) -> bool:
        """逐行匹配：如果 snippet 中有一定比例的行能在 kb_code 中找到相似行"""
        snippet_lines = [
            l.strip() for l in snippet.splitlines()
            if l.strip() and not l.strip().startswith(("#", "//", "*", "-"))
        ]
        kb_lines = [l.strip() for l in kb_code.splitlines() if l.strip()]

        if not snippet_lines:
            return False

        matched = 0
        for s_line in snippet_lines:
            for kb_line in kb_lines:
                if s_line.lower() in kb_line.lower() or kb_line.lower() in s_line.lower():
                    matched += 1
                    break
                if SequenceMatcher(None, s_line.lower(), kb_line.lower()).ratio() >= 0.85:
                    matched += 1
                    break

        ratio = matched / len(snippet_lines)
        return ratio >= self.min_line_match_ratio


class HallucinationGuard:
    """
    幻觉防御总控：串联 Pre-RAG Gate → Retrieval → LLM Generation → Post-Hoc Check
    """

    def __init__(
        self,
        checker: Optional[GroundingChecker] = None,
        code_checker: Optional[CodeGroundingChecker] = None,
    ):
        self.checker = checker or GroundingChecker()
        self.code_checker = code_checker or CodeGroundingChecker()
        self.gate = HardRAGGate()
        self.injector = RetrievalInjector()

    def pre_check(
        self,
        kb_result: Dict[str, Any],
        intent: Optional[str] = None,
        message: str = "",
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        前置检查：决定是否硬阻断。
        :return: (should_proceed, block_reply, enriched_context)
        - should_proceed=True：放行，继续调用 LLM
        - should_proceed=False：硬阻断，直接返回 block_reply
        """
        # 白名单意图放行
        if self.gate.should_bypass(message, intent):
            return True, None, None

        reply_hint = kb_result.get("reply_hint", "")
        hit = kb_result.get("hit", False)
        hits = kb_result.get("hits", [])
        detected_product = kb_result.get("detected_product", "未知")

        # 第三方产品 / 不确定产品 / 非标准会员价格 → 硬阻断
        if reply_hint in ("OUT_OF_SCOPE", "UNCERTAIN_PRODUCT", "INVALID_MEMBERSHIP_PRICE"):
            block_reply = self.gate.get_block_reply(reply_hint)
            return False, block_reply, None

        # 未命中知识库 → 硬阻断（不进入 LLM 自由生成）
        if not hit or not hits:
            block_reply = self.gate.get_block_reply("KB_MISS")
            return False, block_reply, None

        # 放行：构造 Grounded Context
        context = self.injector.format_context(hits, detected_product)
        return True, None, {
            "grounded_context": context,
            "hits": hits,
            "detected_product": detected_product,
        }

    def post_check(
        self,
        bot_reply: str,
        retrieval_hits: List[Dict[str, Any]],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        后置检查：验证 LLM 回答是否 grounded 于检索结果。
        :return: (is_safe, final_reply, check_detail)
        - is_safe=True：回答通过验证
        - is_safe=False：回答被拦截，替换为兜底话术
        """
        # 如果回答本身就是固定话术，跳过验证
        stripped = bot_reply.strip()
        fixed_phrases = {
            "抱歉，这个问题我暂时无法回答",
            "抱歉，这个问题不在 Kimi 的服务范围内",
            "建议您联系人工客服",
            "已记录您的请求",
            "已提交给技术团队",
            "感谢您的反馈",
        }
        if any(fp in stripped for fp in fixed_phrases):
            return True, bot_reply, {"reason": "fixed_phrase_skip"}

        # 1. 通用文本 grounding 检查
        is_grounded, detail = self.checker.check(bot_reply, retrieval_hits)
        if not is_grounded:
            fallback = (
                "抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。"
            )
            return False, fallback, detail

        # 2. 代码/命令专用 grounding 检查（新增）
        is_code_grounded, code_detail = self.code_checker.check(bot_reply, retrieval_hits)
        if not is_code_grounded:
            fallback = (
                "抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。"
            )
            return False, fallback, code_detail

        return True, bot_reply, {
            "reason": "all_checks_passed",
            "text_detail": detail,
            "code_detail": code_detail,
        }
