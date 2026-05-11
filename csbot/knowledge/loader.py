"""文档加载器：支持 Markdown 表格、标题层级、错误码、FAQ、SOP 自动拆分"""
from csbot.knowledge.base import KnowledgeDoc, DocType
from typing import List, Dict, Tuple
import re
import hashlib


class KnowledgeLoader:
    """加载各种来源的文档"""

    # ── 通用工具 ─────────────────────────────────────────

    @staticmethod
    def _slug(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()[:8]

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """从文本提取候选关键词：加粗、引号、代码、常见动词名词
        注意：过滤掉包含换行符或过长的伪匹配，防止 markdown 代码块（```）被误提取。"""
        words = set()
        # 加粗（过滤含换行的伪匹配）
        words.update(b.strip() for b in re.findall(r'\*\*(.+?)\*\*', text) if '\n' not in b)
        # 代码/命令：过滤含换行或过长（>40字符）的匹配，避免 ``` 代码块被整段吞入
        words.update(c.strip() for c in re.findall(r'`([^`]+)`', text) if '\n' not in c and len(c) <= 40)
        # 引号
        words.update(q.strip() for q in re.findall(r'[""](.+?)[""]', text) if '\n' not in q)
        # 常见技术词
        tech = re.findall(r'[A-Za-z][A-Za-z0-9_]*(?:\s+[A-Za-z0-9_]+){0,2}', text)
        words.update([t for t in tech if len(t) > 3])
        return list(words)[:15]

    @staticmethod
    def _clean_md(text: str) -> str:
        """去掉 markdown 标记，保留可读性"""
        text = re.sub(r'#{1,6}\s*', '', text)
        text = re.sub(r'\*\*', '', text)
        text = re.sub(r'`', '', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        return text.strip()

    # ── 按文件类型加载 ───────────────────────────────────

    def load_error_code_table(self, path: str, source: str = "") -> List[KnowledgeDoc]:
        """解析《错误码速查表》中的 Markdown 表格"""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        docs = []
        # 在文本中扫描所有表格块（以 | 开头的连续行）
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            # 找表头行
            if not lines[i].strip().startswith("|"):
                i += 1
                continue

            # 收集整个表格
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1

            if len(table_lines) < 3:
                continue

            # 解析表头
            header = [c.strip() for c in table_lines[0].split("|") if c.strip()]
            if len(header) < 3:
                continue

            # 找关键列索引
            code_idx = next((i for i, h in enumerate(header) if "状态码" in h or "错误码" in h or "报错" in h), -1)
            type_idx = next((i for i, h in enumerate(header) if "类型" in h or "含义" in h), -1)
            fix_idx = next((i for i, h in enumerate(header) if "处理" in h or "方法" in h), -1)
            user_idx = next((i for i, h in enumerate(header) if "用户看到" in h or "报错信息" in h), -1)

            for line in table_lines[2:]:  # 跳过分隔行
                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) < 3:
                    continue

                code = cols[code_idx] if code_idx >= 0 else ""
                err_type = cols[type_idx] if type_idx >= 0 else ""
                user_msg = cols[user_idx] if user_idx >= 0 else ""
                fix = cols[fix_idx] if fix_idx >= 0 else ""

                title = f"{code} {err_type}".strip() if code else err_type
                content = f"用户看到：{user_msg}\n\n含义：{err_type}\n\n处理方法：{fix}".strip()
                if not title:
                    continue

                doc_id = f"ec-{self._slug(title)}"
                docs.append(KnowledgeDoc(
                    id=doc_id,
                    doc_type=DocType.ERROR_CODE,
                    title=title,
                    content=content,
                    keywords=self._extract_keywords(content) + [code] if code else [],
                    tags=["错误码", "速查"],
                    source=source or path,
                    meta={"error_code": code, "error_type": err_type},
                ))
        return docs

    def load_troubleshoot(self, path: str, source: str = "") -> List[KnowledgeDoc]:
        """解析《常见bug》：按二级标题拆分为独立排查条目"""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        docs = []
        # 按 ## 或 ### 拆分
        blocks = re.split(r'\n#{2,3}\s+', text)[1:]
        for block in blocks:
            lines = block.strip().splitlines()
            title = lines[0].strip().rstrip("#").strip()
            body = "\n".join(lines[1:]).strip()

            # 提取场景标签
            tags = []
            if "离线" in title or "崩溃" in title:
                tags.append("离线崩溃")
            if "超时" in title:
                tags.append("超时")
            if "记忆" in title or "失忆" in title:
                tags.append("记忆丢失")
            if "token" in title.lower() or "rate limit" in title.lower():
                tags.append("对话限制")
            if "定时" in title:
                tags.append("定时任务")

            # 提取表格里的场景作为独立 doc（如果有）
            table_docs = self._extract_tables_from_block(title, body, source or path)
            if table_docs:
                docs.extend(table_docs)

            # 正文本身也建一条
            if len(body) > 30:
                docs.append(KnowledgeDoc(
                    id=f"ts-{self._slug(title)}",
                    doc_type=DocType.TROUBLESHOOT,
                    title=title,
                    content=self._clean_md(body),
                    keywords=self._extract_keywords(body) + [title],
                    tags=tags + ["故障排查"],
                    source=source or path,
                    meta={"category": "troubleshoot"},
                ))
        return docs

    def _extract_tables_from_block(self, section_title: str, text: str, source: str) -> List[KnowledgeDoc]:
        """从故障排查块中提取场景对照表，每行成一个 doc"""
        docs = []
        # 找表格
        lines = text.splitlines()
        in_table = False
        header = []
        rows = []
        for line in lines:
            if "|" in line and "—" not in line and "---" not in line:
                if not in_table:
                    header = [c.strip() for c in line.split("|") if c.strip()]
                    in_table = True
                else:
                    cols = [c.strip() for c in line.split("|")[1:-1]]
                    if len(cols) >= len(header):
                        rows.append(dict(zip(header, cols)))
            else:
                if in_table and rows:
                    # 表格结束，生成 docs
                    for row in rows:
                        scene = row.get("场景", row.get("用户看到的报错", ""))
                        root = row.get("底层报错信息", row.get("底层报错类型", ""))
                        if not scene:
                            continue
                        content = "\n".join([f"{k}: {v}" for k, v in row.items() if v])
                        docs.append(KnowledgeDoc(
                            id=f"ts-table-{self._slug(scene)}",
                            doc_type=DocType.TROUBLESHOOT,
                            title=f"{section_title} — {scene}",
                            content=content,
                            keywords=self._extract_keywords(content) + [scene, root],
                            tags=["故障排查", "场景对照"],
                            source=source,
                            meta={"table_source": section_title},
                        ))
                    rows = []
                in_table = False
        return docs

    def load_policy(self, path: str, source: str = "") -> List[KnowledgeDoc]:
        """解析《会员权益》：按二级标题拆分为政策条目"""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        docs = []
        blocks = re.split(r'\n#{2,3}\s+', text)[1:]
        for block in blocks:
            lines = block.strip().splitlines()
            title = lines[0].strip().rstrip("#").strip()
            body = "\n".join(lines[1:]).strip()

            tags = ["会员权益"]
            if "退款" in title or "退费" in title or "退订" in body:
                tags.append("退款")
            if "发票" in title or "开票" in body:
                tags.append("开票")

            docs.append(KnowledgeDoc(
                id=f"pol-{self._slug(title)}",
                doc_type=DocType.POLICY,
                title=title,
                content=self._clean_md(body),
                keywords=self._extract_keywords(body) + [title],
                tags=tags,
                source=source or path,
                meta={"policy_type": "membership"},
            ))
        return docs

    def load_config_guide(self, path: str, source: str = "") -> List[KnowledgeDoc]:
        """解析《平台接入与鉴权》：按平台和问题拆分为配置条目"""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        docs = []
        # 按 ## 或 ### 拆分
        blocks = re.split(r'\n#{2,3}\s+', text)[1:]
        current_platform = ""

        for block in blocks:
            lines = block.strip().splitlines()
            title = lines[0].strip().rstrip("#").strip()
            body = "\n".join(lines[1:]).strip()

            # 识别当前平台
            if "飞书" in title:
                current_platform = "飞书"
            elif "微信" in title:
                current_platform = "微信"
            elif "企微" in title or "企业微信" in title:
                current_platform = "企微"
            elif "平台" in title or "支持" in title:
                current_platform = "通用"

            tags = ["平台接入", "鉴权", current_platform] if current_platform else ["平台接入"]

            docs.append(KnowledgeDoc(
                id=f"cfg-{self._slug(title)}",
                doc_type=DocType.CONFIG,
                title=title,
                content=self._clean_md(body),
                keywords=self._extract_keywords(body) + [title, current_platform],
                tags=tags,
                source=source or path,
                meta={"platform": current_platform},
            ))

            # 如果块内有表格（如 2.5 的 Token 场景表），也提取
            table_docs = self._extract_tables_from_block(title, body, source or path)
            for td in table_docs:
                td.doc_type = DocType.CONFIG
                td.tags = list(set(td.tags + tags))
                td.meta["platform"] = current_platform
            docs.extend(table_docs)

        return docs

    def load_sop(self, path: str, source: str = "") -> List[KnowledgeDoc]:
        """解析《问题上报与人工客服处理》：流程与模板"""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        docs = []
        blocks = re.split(r'\n#{2,3}\s+', text)[1:]
        for block in blocks:
            lines = block.strip().splitlines()
            title = lines[0].strip().rstrip("#").strip()
            body = "\n".join(lines[1:]).strip()

            docs.append(KnowledgeDoc(
                id=f"sop-{self._slug(title)}",
                doc_type=DocType.SOP,
                title=title,
                content=self._clean_md(body),
                keywords=self._extract_keywords(body) + ["Bot ID", "反馈", "人工客服"],
                tags=["问题上报", "SOP"],
                source=source or path,
                meta={"sop_type": "feedback"},
            ))
        return docs

    def load_product_guide(self, path: str, source: str = "", platform: str = "") -> List[KnowledgeDoc]:
        """解析产品分类文档（桌面/Android/群聊/云端/通用），按 ## / ### 拆分为条目"""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        docs = []
        blocks = re.split(r'\n#{2,3}\s+', text)[1:]
        for block in blocks:
            lines = block.strip().splitlines()
            title = lines[0].strip().rstrip("#").strip()
            body = "\n".join(lines[1:]).strip()

            if len(body) < 10:
                continue

            tags = ["产品指南", platform] if platform else ["产品指南"]
            meta = {"category": "product_guide"}
            if platform:
                meta["platform"] = platform

            docs.append(KnowledgeDoc(
                id=f"prod-{self._slug(title)}-{platform}",
                doc_type=DocType.PRODUCT,
                title=title,
                content=self._clean_md(body),
                keywords=self._extract_keywords(body) + [title, platform],
                tags=tags,
                source=source or path,
                meta=meta,
            ))
        return docs

    def load_help_center(self, path: str, source: str = "") -> List[KnowledgeDoc]:
        """解析帮助中心文档：按二级标题拆分，自动推断标签与类型"""
        import os
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        fname = os.path.basename(path)
        # 根据文件名确定分类标签、默认类型、以及注入的核心关键词（提升 Help Center FAQ 召回率）
        category_tags = []
        default_type = DocType.FAQ
        file_core_keywords = []
        if "kimi-api" in fname:
            category_tags = ["帮助中心", "Kimi API"]
            default_type = DocType.CONFIG
            file_core_keywords = ["api", "API", "api key", "开发者", "开放平台", "接口", "鉴权"]
        elif "kimi-code" in fname:
            category_tags = ["帮助中心", "Kimi Code"]
            default_type = DocType.PRODUCT
            file_core_keywords = ["code", "编程", "IDE", "vscode", "claude code", "roo code", "终端", "命令行"]
        elif "membership" in fname:
            category_tags = ["帮助中心", "会员权益"]
            default_type = DocType.POLICY
            file_core_keywords = ["会员", "额度", "退款", "付费", "订阅", "充值", "计费", "套餐"]
        elif "new-user-guide" in fname:
            category_tags = ["帮助中心", "新用户指南"]
            default_type = DocType.FAQ
            file_core_keywords = ["新用户", "入门", "新手", "使用", "指南", "开始", "注册"]
        elif "others" in fname:
            category_tags = ["帮助中心", "其他"]
            default_type = DocType.FAQ
            file_core_keywords = ["语言", "支持", "其他", "常见问题", "FAQ"]
        elif "websites" in fname:
            category_tags = ["帮助中心", "Websites"]
            default_type = DocType.PRODUCT
            file_core_keywords = ["websites", "建站", "网站", "网页", "全栈", "部署", "发布"]
        elif "docs-and-sheets" in fname:
            category_tags = ["帮助中心", "Docs", "Sheets"]
            default_type = DocType.PRODUCT
            file_core_keywords = ["docs", "sheets", "文档", "表格", "office", "word", "excel", "ppt"]
        elif "兜底" in fname or "faq" in fname.lower():
            category_tags = ["帮助中心", "兜底FAQ"]
            # 兜底 FAQ 需要覆盖大量知识库未收录的问题，注入高频召回词
            file_core_keywords = [
                "模型能力", "DeepSeek", "对比", "差距", "PDF", "文件大小", "限制", "过载",
                "手机端", "App", "bug", "跳转", "飞书", "App ID", "对话归类", "文件夹",
                "项目管理", "Mac", "桌面端", "上线", "补偿", "老用户", "多设备", "部署",
                "安装", "教程", "引导", "bridge", "coding plan", " thinking", "关闭推理",
            ]
        else:
            category_tags = ["帮助中心"]
            file_core_keywords = ["帮助中心", "客服"]

        docs = []
        blocks = re.split(r'\n#{2,3}\s+', text)[1:]
        for block in blocks:
            lines = block.strip().splitlines()
            title = lines[0].strip().rstrip("#").strip()
            body = "\n".join(lines[1:]).strip()

            if len(body) < 10:
                continue

            tags = list(category_tags)
            if "退款" in title or "退费" in title or "退订" in body:
                tags.append("退款")
            if "发票" in title or "开票" in title or "开票" in body:
                tags.append("开票")
            if "错误" in title or "报错" in title or "故障" in title:
                tags.append("故障排查")
            if "价格" in title or "收费" in title or "计费" in title:
                tags.append("计费")
            if "登录" in title or "认证" in title or "授权" in title:
                tags.append("鉴权")

            # 合并关键词：自动提取 + 标题 + 分类标签 + 文件核心词
            # 帮助中心 FAQ 更容易被召回的关键：给每个 chunk 注入文件级核心关键词
            keywords = self._extract_keywords(body) + [title] + category_tags + file_core_keywords
            docs.append(KnowledgeDoc(
                id=f"hc-{self._slug(title)}-{self._slug(fname)}",
                doc_type=default_type,
                title=title,
                content=self._clean_md(body),
                keywords=keywords,
                tags=tags,
                source=source or fname,
                meta={"category": "help_center", "file": fname},
            ))
        return docs

    def load_all(self, base_dir: str) -> List[KnowledgeDoc]:
        """一键加载标准命名文件。支持传入多个目录（逗号分隔）或单个目录。"""
        import os
        dirs = [d.strip() for d in base_dir.split(",")] if "," in base_dir else [base_dir]

        mapping = {
            "错误码速查表.md": (self.load_error_code_table, DocType.ERROR_CODE),
            "常见bug.md": (self.load_troubleshoot, DocType.TROUBLESHOOT),
            "会员权益.md": (self.load_policy, DocType.POLICY),
            "平台接入与鉴权.md": (self.load_config_guide, DocType.CONFIG),
            "问题上报与人工客服处理.md": (self.load_sop, DocType.SOP),
        }
        docs = []
        for d in dirs:
            for fname, (method, _) in mapping.items():
                fpath = os.path.join(d, fname)
                if os.path.exists(fpath):
                    docs.extend(method(fpath, source=fname))

            # Kimi Claw 产品分类知识库（支持平铺或子目录）
            product_files = {
                "功能使用.md": "通用",
                "部署方式分类.md": "通用",
                "桌面claw.md": "desktop",
                "安卓claw.md": "android",
                "claw群聊.md": "群聊",
                "云端claw.md": "云端",
            }
            for fname, platform in product_files.items():
                # 先查平铺路径
                fpath = os.path.join(d, fname)
                if not os.path.exists(fpath):
                    # 再查 kimi claw分类/ 子目录
                    fpath = os.path.join(d, "kimi claw分类", fname)
                if os.path.exists(fpath):
                    docs.extend(self.load_product_guide(fpath, source=fname, platform=platform))

            # 帮助中心文档
            help_center_dir = os.path.join(d, "help_center")
            if os.path.isdir(help_center_dir):
                for fname in sorted(os.listdir(help_center_dir)):
                    if fname.endswith(".md"):
                        fpath = os.path.join(help_center_dir, fname)
                        docs.extend(self.load_help_center(fpath, source=f"help_center/{fname}"))

            # 其他 Markdown 文件（如 客服.md、工作日志等），按 help_center 方式加载
            for extra_fname in sorted(os.listdir(d)):
                if extra_fname.endswith(".md") and extra_fname not in {k for k in mapping.keys()} | set(product_files.keys()):
                    fpath = os.path.join(d, extra_fname)
                    if os.path.isfile(fpath):
                        docs.extend(self.load_help_center(fpath, source=extra_fname))

        return docs