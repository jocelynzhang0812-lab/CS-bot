from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict, Optional


class CSSelfDiagnosisSkill(BaseTool):
    def __init__(self):
        super().__init__("cs_self_diagnosis", "已知问题初筛")
        self.rules = [
            {"id": "memory_reset", "kw": {"失忆", "忘记", "不记得", "重置", "凌晨"},
             "cause": "OpenClaw 默认每天凌晨4点自动重置对话上下文，未写入 Memory 的内容会丢失。",
             "fix": "主动说「请记住XXX」可写入长期记忆；或修改 config.yaml 调整重置时间。"},
            {"id": "tailscale_dns", "kw": {"tailscale", "vpn", "dns", "断连"},
             "cause": "Tailscale 覆盖系统 DNS 配置，导致连接中断。",
             "fix": "Tailscale DNS 配置页添加 8.8.8.8，开启 Override DNS Servers，等待30秒。"},
            {"id": "manual_upgrade", "kw": {"手动升级", "插件失效", "微信不能用", "飞书连不上"},
             "cause": "手动升级 OpenClaw 到 3.22 之后版本会导致 Kimi 插件不兼容。",
             "fix": "设置 → 恢复初始设置（保留工作空间和记忆，需重新配置聊天软件）。"},
            {"id": "feishu_group", "kw": {"飞书群", "群里", "群聊", "没反应"},
             "cause": "默认只响应私聊，群聊策略为 closed。",
             "fix": "对 Claw 说「将飞书的群聊策略调整为 open」然后重启。"},
            {"id": "old_version", "kw": {"看不到一键扫码", "没有扫码入口", "找不到微信配置"},
             "cause": "2025年3月22日之前创建的 Claw 默认不包含企微/微信一键部署功能。",
             "fix": "设置 → 恢复初始版本（保留数据），或删除重建。"},
            {"id": "reasoning_show", "kw": {"思考过程", "reasoning", "隐藏思考"},
             "cause": "飞书默认展示 reasoning 过程。", "fix": "发送 /reasoning off 隐藏。"},
            {"id": "rate_limit_burst", "kw": {"rate limit", "api rate limit reached", "请求太频繁", "限流"},
             "cause": "短时间内请求频率超过账户额度限制，或存在循环调用/高频脚本。",
             "fix": "暂停操作 1-2 分钟后重试；检查是否有定时任务或脚本在批量调用；发送 /status 查看额度消耗。"},
            {"id": "feishu_reauth", "kw": {"飞书连不上", "飞书断开", "飞书没反应", "飞书收不到"},
             "cause": "飞书授权过期、Bot 被移出群聊、或 webhook 配置失效。",
             "fix": "在 Kimi Claw 设置中重新扫码授权飞书；检查群成员列表中 Bot 是否存在；查看飞书管理后台权限状态。"},
            {"id": "bot_offline", "kw": {"bot 离线", "bot 红灯", "断连", "bot id 断连", "连不上", "掉线"},
             "cause": "网络波动、配置损坏、或后端实例异常导致 Bot 与服务端断开。",
             "fix": "设置 → 重启 Kimi Claw；无效则修复配置；仍无效则恢复初始设置并记录 Bot ID 提交技术排查。"},
            {"id": "infinite_diag_loop", "kw": {"无限循环", "一直运行", "停不下来", "自我检测", "写了好多代码", "一堆代码", "不停写"},
             "cause": "AI 问题诊断或自定义脚本进入自我调用循环，未正确终止。",
             "fix": "强制停止当前任务（/stop 或关闭窗口）；发送 /logs 定位循环触发点；设置 → 修复配置清除异常状态；必要时重启。"},
            {"id": "version_lag", "kw": {"版本落后", "openclaw 版本", "更新慢", "不上线", "版本差异"},
             "cause": "Kimi Claw 与 OpenClaw 版本发布节奏不同，部分功能存在差异。",
             "fix": "此类版本排期问题建议联系人工客服或产品经理获取最新动态，我无法提供具体上线时间。"},
        ]

    async def execute(self, symptoms: str, platform: Optional[str] = None, **kwargs) -> ToolResult:
        sym = symptoms.lower()
        for r in self.rules:
            if any(k in sym for k in r["kw"]):
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    result={
                        "is_known_issue": True,
                        "rule_id": r["id"],
                        "root_cause": r["cause"],
                        "workaround": r["fix"],
                        "needs_feedback_bot": False,
                        "user_reply": f"{r['cause']}\n\n您可以尝试：{r['fix']}\n\n如仍未解决请继续@我。",
                    },
                )
        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={"is_known_issue": False, "needs_feedback_bot": True},
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {"symptoms": {"type": "string"}, "platform": {"type": "string", "optional": True}}
