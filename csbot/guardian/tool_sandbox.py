"""
ToolCallSandbox —— 工具调用层硬约束沙箱

在 LLM 发起的工具调用真正执行前，做纯代码层拦截。
不依赖 LLM 自觉遵守提示词，敏感路径/命令直接拒绝。
"""

import os
import re
from typing import Dict, List, Tuple


class ToolCallSandbox:
    """
    工具调用沙箱：对所有 LLM 发起的工具调用做前置校验。
    """

    # ── 1. 敏感路径黑名单（正则） ──
    SENSITIVE_PATH_PATTERNS: List[str] = [
        # Kimi / Kitty 配置
        r"[/\\]\.kimi[/\\]?",
        r"[/\\]\.kitty[/\\]?",
        # SSH 密钥
        r"[/\\]\.ssh[/\\]?",
        r"id_rsa",
        r"id_ed25519",
        r"id_ecdsa",
        r"\.pem$",
        # AWS / 云凭证
        r"[/\\]\.aws[/\\]?",
        r"credentials",
        r"[/\\]\.azure[/\\]?",
        r"[/\\]\.gcloud[/\\]?",
        # GitHub / Git 凭证
        r"[/\\]\.config[/\\]gh[/\\]?",
        r"[/\\]\.config[/\\]hub[/\\]?",
        r"\.netrc",
        r"\.gitconfig",
        # Shell 环境变量文件
        r"\.bashrc$",
        r"\.zshrc$",
        r"\.profile$",
        r"\.bash_profile$",
        r"\.bash_login$",
        r"\.zshenv$",
        # 通用敏感文件
        r"\.env$",
        r"\.env\.\w+$",
        r"\.pk$",
        r"\.p12$",
        r"\.pfx$",
        r"\.keystore$",
        r"token",
        r"secret",
        r"api_key",
        r"apikey",
        r"password",
        # 系统级敏感目录
        r"^/etc/shadow",
        r"^/etc/passwd",
        r"^/etc/ssh",
        r"^/var/log",
        r"^/proc",
        r"^/sys",
    ]

    # ── 2. Shell 命令黑名单（正则） ──
    FORBIDDEN_SHELL_PATTERNS: List[str] = [
        # 破坏型
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+~",
        r"rm\s+-rf\s+\$HOME",
        r":\(\)\{\s*:\|\:\&\s*\};:",  # fork bomb
        r"dd\s+if=.+of=/dev/",
        r">\s+/dev/",
        r"mkfs",
        # 远程下载 + 执行
        r"curl\s+.*\|\s*(sh|bash|zsh|python|python3)",
        r"wget\s+.*\|\s*(sh|bash|zsh|python|python3)",
        r"fetch\s+.*\|\s*(sh|bash|zsh)",
        # 凭证读取（常见绕法）
        r"cat\s+.*config\.toml",
        r"cat\s+.*credentials",
        r"cat\s+.*\.env",
        r"cat\s+.*\.ssh",
        r"cat\s+.*id_rsa",
        r"cat\s+.*token",
        r"cat\s+.*secret",
        r"less\s+.*config\.toml",
        r"less\s+.*credentials",
        r"head\s+.*config\.toml",
        r"tail\s+.*config\.toml",
        r"grep\s+.*api_key",
        r"grep\s+.*token",
        r"grep\s+.*secret",
        r"env\s*\|\s*grep",
        r"printenv\s*\|\s*grep",
        r"echo\s+\$.*(TOKEN|KEY|SECRET|PASSWORD)",
        # 网络外发
        r"curl\s+.*-X\s+POST",
        r"curl\s+.*-d\s",
        r"wget\s+.*--post-data",
        r"nc\s+-",
        r"netcat",
        r"python\s+-m\s+http\.server",
        # 权限提升
        r"sudo\s+",
        r"su\s+-",
        r"chmod\s+777",
        r"chown\s+root",
        # 包管理（防止乱装）
        r"pip\s+install",
        r"npm\s+install\s+-g",
        r"apt\s+(install|remove|purge)",
        r"yum\s+(install|remove)",
        r"brew\s+(install|uninstall)",
    ]

    # ── 3. 工具白名单映射（按意图/场景限制可调用的工具） ──
    INTENT_TOOL_ALLOWLIST: Dict[str, List[str]] = {
        # 纯客服场景：只允许知识库搜索、澄清、话术模板、guardrails
        "faq": ["search_knowledge_base", "cs_clarify", "get_response_template", "cs_guardrails",
                "cs_output_reviewer", "cs_self_check", "cs_self_diagnosis", "cs_emotion"],
        # 入表场景
        "tech_bug": ["search_knowledge_base", "cs_clarify", "submit_bug_report",
                     "get_response_template", "cs_guardrails", "cs_output_reviewer",
                     "cs_self_check", "cs_self_diagnosis", "cs_emotion", "cs_follow_up_sop",
                     "cs_ticket_tracker"],
        # 转人工
        "human_request": ["submit_bug_report", "get_response_template", "cs_guardrails",
                          "cs_output_reviewer", "cs_human_handoff", "cs_ticket_tracker"],
        # 产品建议
        "product_feedback": ["submit_product_feedback", "get_response_template",
                             "cs_guardrails", "cs_output_reviewer"],
        # 退款/开票等特殊请求
        "special_request": ["get_response_template", "cs_guardrails", "cs_output_reviewer",
                            "cs_human_handoff"],
    }

    def __init__(self):
        self._path_patterns = [re.compile(p, re.IGNORECASE) for p in self.SENSITIVE_PATH_PATTERNS]
        self._shell_patterns = [re.compile(p, re.IGNORECASE) for p in self.FORBIDDEN_SHELL_PATTERNS]

    # ── 公开 API ──

    def validate(self, tool_name: str, args: Dict, intent: str = "", session_state: Dict = None) -> Tuple[bool, str]:
        """
        校验一次工具调用是否允许执行。
        :return: (allowed, error_message)
        - allowed=True: 允许执行
        - allowed=False: 拒绝执行，error_message 会作为工具错误返回给 LLM
        """
        # 1. 路径安全检查（ReadFile / Glob / Grep / WriteFile / StrReplaceFile）
        if tool_name in ("ReadFile", "Glob", "Grep", "WriteFile", "StrReplaceFile"):
            path = args.get("path", "")
            pattern = args.get("pattern", "")
            # 收集所有路径相关参数
            paths_to_check = [p for p in [path, pattern, args.get("directory", "")] if p]
            for p in paths_to_check:
                is_bad, reason = self._check_path(p)
                if is_bad:
                    return False, f"[ToolCallSandbox] 路径拦截: {reason}"

        # 2. Shell 命令安全检查
        if tool_name == "Shell":
            command = args.get("command", "")
            is_bad, reason = self._check_shell(command)
            if is_bad:
                return False, f"[ToolCallSandbox] 命令拦截: {reason}"

        # 3. 意图-工具锁（可选，默认放行未定义的意图）
        if intent and intent in self.INTENT_TOOL_ALLOWLIST:
            allowed_tools = self.INTENT_TOOL_ALLOWLIST[intent]
            if tool_name not in allowed_tools:
                return False, (
                    f"[ToolCallSandbox] 能力边界锁: 当前意图 '{intent}' 不允许调用工具 '{tool_name}'。"
                    f"允许的工具: {allowed_tools}"
                )

        return True, ""

    # ── 内部实现 ──

    def _check_path(self, path: str) -> Tuple[bool, str]:
        """检查路径是否命中敏感路径黑名单。"""
        if not path:
            return False, ""

        # 展开 ~ 为真实路径
        expanded = os.path.expanduser(path)
        normalized = os.path.normpath(expanded)

        for pat in self._path_patterns:
            if pat.search(path) or pat.search(expanded) or pat.search(normalized):
                return True, f"路径 '{path}' 命中敏感规则: {pat.pattern}"

        return False, ""

    def _check_shell(self, command: str) -> Tuple[bool, str]:
        """检查 Shell 命令是否命中黑名单。"""
        if not command:
            return False, ""

        for pat in self._shell_patterns:
            if pat.search(command):
                return True, f"命令命中禁用规则: {pat.pattern}"

        return False, ""
