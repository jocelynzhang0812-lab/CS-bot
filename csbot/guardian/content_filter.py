"""
HardContentFilter —— 输出层硬正则过滤器

在 Bot 回复最终返回给用户前，做纯代码层正则拦截。
不依赖 LLM 或 Sub-Agent，检测到违规话术直接替换为兜底回复。
"""

import re
from typing import List, Tuple, Dict


class HardContentFilter:
    """
    硬内容过滤器：对最终输出做最后一道纯代码层清洗。
    """

    # ── 1. 配置幻觉话术黑名单 ──
    CONFIG_HALLUCINATION_PATTERNS: List[str] = [
        r"根据您的配置",
        r"根据你[们\s]*的配置",
        r"您的设置是",
        r"你的设置是",
        r"您配置的是",
        r"你配置的是",
        r"从您的\s*\w*\s*来看",
        r"从你的\s*\w*\s*来看",
        r"您的\s*\w+\s*配置[是为]",
        r"你的\s*\w+\s*配置[是为]",
        r"您的\s*config\w*\s*",
        r"你的\s*config\w*\s*",
        r"您[的\s]*config\.toml",
        r"你[的\s]*config\.toml",
        r"从您的配置文件中?",
        r"从你的配置文件中?",
        r"您当前[的\s]*配置",
        r"你当前[的\s]*配置",
        r"您这边[的\s]*配置",
        r"你这边[的\s]*配置",
    ]

    # ── 2. 代执行话术黑名单 ──
    EXECUTION_OFFER_PATTERNS: List[str] = [
        r"需要我直接帮[您你]执行",
        r"需要我帮[您你]执行",
        r"把你要转换的",
        r"把您要转换的",
        r"把你要的\w+发给我",
        r"把您要的\w+发给我",
        r"发给我就行",
        r"发过来就行",
        r"我来帮[您你]执行",
        r"我来帮[您你]操作",
        r"我帮[您你]执行",
        r"我帮[您你]操作",
        r"我直接帮[您你]处理",
        r"我直接帮[您你]执行",
        r"我直接处理",
        r"我直接执行",
        r"我帮你跑一下",
        r"我帮你跑",
        r"我帮你弄",
        r"我帮你转",
        r"我帮你转一下",
        r"把链接发给我",
        r"把 ID 发给我",
        r"把id发给我",
    ]

    # ── 2.5. 解决方案/指导话术黑名单 ──
    SOLUTION_GUIDANCE_PATTERNS: List[str] = [
        r"你可以尝试",
        r"您可以尝试",
        r"建议[您你]",
        r"建议你",
        r"可能的原因是",
        r"可能是因为",
        r"解决方案如下",
        r"解决方法是",
        r"修复方法",
        r"修复步骤",
        r"代码示例",
        r"代码如下",
        r"修改代码",
        r"更新配置",
        r"检查一下",
        r"请检查",
        r"试试看",
        r"试一下",
        r"换个方式",
        r"另一种方法",
        r"配置示例",
        r"配置如下",
        r"命令如下",
        r"执行以下命令",
        r"运行以下",
        r"请执行",
        r"请运行",
        r"输入以下",
        r"在终端",
        r"在命令行",
        r"修改配置文件",
        r"添加配置",
        r"删除配置",
        r"重启服务",
        r"重新部署",
        r"升级版本",
        r"降级版本",
    ]

    # ── 2.6 步骤化解决方案（带编号的修复流程）──
    STEP_SOLUTION_PATTERNS: List[str] = [
        r"修复步骤\s*[:：]?\s*\n\s*\d+\s*[\.、]",
        r"解决步骤\s*[:：]?\s*\n\s*\d+\s*[\.、]",
        r"解决方案\s*[:：]?\s*\n\s*\d+\s*[\.、]",
        r"操作步骤\s*[:：]?\s*\n\s*\d+\s*[\.、]",
        r"(?:^|\n)\s*\d+\s*[\.、]\s*备份.*\n\s*\d+\s*[\.、]\s*查看",
        r"(?:^|\n)\s*\d+\s*[\.、]\s*备份.*\n\s*\d+\s*[\.、]\s*修改",
        r"(?:^|\n)\s*\d+\s*[\.、]\s*备份.*\n\s*\d+\s*[\.、]\s*修复",
        r"(?:^|\n)\s*\d+\s*[\.、]\s*查看.*\n\s*\d+\s*[\.、]\s*修改",
        r"(?:^|\n)\s*\d+\s*[\.、]\s*查看.*\n\s*\d+\s*[\.、]\s*修正",
    ]

    # ── 3. 安全违规（敏感文件/路径提及） ──
    SECURITY_VIOLATION_PATTERNS: List[str] = [
        r"~\s*/\s*\.kimi",
        r"~\s*/\s*\.ssh",
        r"~\s*/\s*\.aws",
        r"~\s*/\s*\.config",
        r"config\.toml",
        r"credentials",
        r"api_key\s*[=:]",
        r"apikey\s*[=:]",
        r"token\s*[=:]",
        r"secret\s*[=:]",
    ]

    # ── 4. 兜底替换话术 ──
    FALLBACK_CONFIG_HALLUCINATION = (
        "抱歉，我不清楚您的具体配置，请您把相关配置内容贴出来，我再帮您分析。"
    )

    FALLBACK_EXECUTION_OFFER = (
        "您可以按照以下步骤自行操作，如有疑问随时联系我。"
    )

    FALLBACK_SOLUTION_GUIDANCE = (
        "这个问题不在知识库中，请联系人工客服寻求帮助。"
    )

    FALLBACK_STEP_SOLUTION = (
        "抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。"
    )

    FALLBACK_SECURITY_VIOLATION = (
        "抱歉，这个问题我暂时无法回答，建议您联系人工客服进一步协助。"
    )

    def __init__(self):
        self._config_patterns = [re.compile(p, re.IGNORECASE) for p in self.CONFIG_HALLUCINATION_PATTERNS]
        self._exec_patterns = [re.compile(p, re.IGNORECASE) for p in self.EXECUTION_OFFER_PATTERNS]
        self._solution_patterns = [re.compile(p, re.IGNORECASE) for p in self.SOLUTION_GUIDANCE_PATTERNS]
        self._step_patterns = [re.compile(p, re.IGNORECASE) for p in self.STEP_SOLUTION_PATTERNS]
        self._security_patterns = [re.compile(p, re.IGNORECASE) for p in self.SECURITY_VIOLATION_PATTERNS]

    def filter(self, text: str) -> Tuple[str, List[Dict]]:
        """
        对输出文本做硬过滤。
        :return: (filtered_text, violations)
        - filtered_text: 过滤后的文本（若命中则替换为兜底话术）
        - violations: 命中的规则列表（用于日志/监控）
        """
        if not text:
            return text, []

        violations: List[Dict] = []
        result = text

        # 优先级 1：安全违规（最严重，直接替换）
        for idx, pat in enumerate(self._security_patterns):
            if pat.search(result):
                violations.append({
                    "rule": "security_violation",
                    "pattern": self.SECURITY_VIOLATION_PATTERNS[idx],
                    "matched": pat.search(result).group(0),
                })
                result = self.FALLBACK_SECURITY_VIOLATION
                # 安全违规直接返回，不再检查其他
                return result, violations

        # 优先级 2：代执行话术（直接替换）
        for idx, pat in enumerate(self._exec_patterns):
            if pat.search(result):
                violations.append({
                    "rule": "execution_offer",
                    "pattern": self.EXECUTION_OFFER_PATTERNS[idx],
                    "matched": pat.search(result).group(0),
                })
                result = self.FALLBACK_EXECUTION_OFFER
                return result, violations

        # 优先级 2.5：解决方案指导（直接替换）
        for idx, pat in enumerate(self._solution_patterns):
            if pat.search(result):
                violations.append({
                    "rule": "solution_guidance",
                    "pattern": self.SOLUTION_GUIDANCE_PATTERNS[idx],
                    "matched": pat.search(result).group(0),
                })
                result = self.FALLBACK_SOLUTION_GUIDANCE
                return result, violations

        # 优先级 2.6：步骤化解决方案（带编号的修复流程，直接替换）
        for idx, pat in enumerate(self._step_patterns):
            if pat.search(result):
                violations.append({
                    "rule": "step_solution",
                    "pattern": self.STEP_SOLUTION_PATTERNS[idx],
                    "matched": pat.search(result).group(0)[:100],
                })
                result = self.FALLBACK_STEP_SOLUTION
                return result, violations

        # 优先级 3：配置幻觉（直接替换）
        for idx, pat in enumerate(self._config_patterns):
            if pat.search(result):
                violations.append({
                    "rule": "config_hallucination",
                    "pattern": self.CONFIG_HALLUCINATION_PATTERNS[idx],
                    "matched": pat.search(result).group(0),
                })
                result = self.FALLBACK_CONFIG_HALLUCINATION
                return result, violations

        return result, violations
