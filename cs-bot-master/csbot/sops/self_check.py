from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict


class CSSelfCheckSkill(BaseTool):
    """引导用户执行自助检查命令。覆盖常见故障场景。"""

    def __init__(self):
        super().__init__("cs_self_check", "自助检查引导")

    async def execute(self, issue_type: str, product_type: str = "云端", **kwargs) -> ToolResult:
        guides = {
            "定时任务": {
                "header": "为了排查定时任务问题，请您依次执行：",
                "steps": [
                    "发送 `/cron` 查看当前所有定时任务列表",
                    "发送 `/status` 查看系统运行状态",
                    "找到任务 ID 后，发送 `/cron log <任务ID>` 查看执行日志",
                ],
                "ask": "请告诉我：列表中能看到您的定时任务吗？状态是启用还是禁用？有报错信息吗？",
            },
            "不回消息": {
                "header": "我们可以按以下步骤排查：",
                "steps": [
                    "再发一条消息测试是否只是临时延迟",
                    "刷新页面后重试",
                    "进入设置 → 点击「重启 Kimi Claw」等待重启完成",
                    "若仍无效，设置 → 点击「修复 Kimi Claw 配置」",
                    "最后尝试设置 → 「恢复初始设置」（会保留工作空间和记忆）",
                ],
                "ask": "请告诉我每一步的结果。",
            },
            "报错崩溃": {
                "header": "请先执行以下诊断命令：",
                "steps": [
                    "发送 `/status` 查看系统状态",
                    "发送 `/logs` 查看最近日志",
                    "进入设置 → AI 问题诊断，输入遇到的问题和报错信息",
                ],
                "ask": "诊断结果如何？",
            },
            "离线": {
                "header": "Bot 显示红色表示离线状态，请依次尝试：",
                "steps": [
                    "设置 → 点击「重启 Kimi Claw」",
                    "设置 → 点击「修复 Kimi Claw 配置」",
                    "设置 → 点击「恢复初始设置」",
                ],
                "ask": "操作后 Bot 状态恢复绿色了吗？",
            },
            "遗忘对话": {
                "header": "请先尝试以下操作：",
                "steps": [
                    "发送 `/new` 创建新 Session（保留历史）",
                    "发送 `/memory` 检查记忆空间状态",
                ],
                "ask": "新建 Session 后对话是否正常？记忆显示多少条目？",
            },
            "rate_limit": {
                "header": "遇到 API Rate Limit，请按以下步骤排查：",
                "steps": [
                    "确认当前是否在高频调用（如批量操作、循环脚本）",
                    "发送 `/status` 查看当前请求频率和额度消耗",
                    "检查是否有定时任务或外部集成在短时间内大量请求",
                    "等待 1-2 分钟后重试，观察是否恢复",
                ],
                "ask": "您当时是在执行什么操作？是批量任务还是正常对话？等待后是否恢复？",
            },
            "feishu_connection": {
                "header": "飞书连接异常，请依次排查：",
                "steps": [
                    "检查飞书 Bot 是否仍在群成员列表中",
                    "在 Kimi Claw 设置中重新进行飞书扫码授权",
                    "发送 `/status` 查看飞书连接状态",
                    "检查飞书管理后台是否有权限变更或封禁通知",
                    "若以上无效，设置 → 「修复 Kimi Claw 配置」→ 重新选择飞书平台",
                ],
                "ask": "重新授权后连接是否恢复？飞书后台有异常通知吗？",
            },
            "bot_disconnect": {
                "header": "Bot ID 断连且无法自动修复，请按顺序操作：",
                "steps": [
                    "记录当前 Bot ID（设置 → 头像下方）",
                    "设置 → 点击「修复 Kimi Claw 配置」",
                    "若仍无效，设置 → 点击「恢复初始设置」（保留工作空间和记忆）",
                    "重启后检查 Bot 状态灯是否变绿",
                    "若仍为红色/离线，请提供 Bot ID 和最后正常时间，我帮您提交技术排查",
                ],
                "ask": "恢复初始设置后状态恢复了吗？请提供 Bot ID 和大概的断连时间。",
            },
            "infinite_loop": {
                "header": "AI 自我检测或脚本出现无限循环，请立即：",
                "steps": [
                    "强制停止当前运行（关闭窗口或发送 /stop）",
                    "发送 `/logs` 查看最近循环日志，定位触发循环的操作",
                    "检查是否有自定义脚本或定时任务在自我调用",
                    "设置 → 点击「修复 Kimi Claw 配置」清除异常状态",
                    "若无法停止，直接重启 Kimi Claw",
                ],
                "ask": "循环是在执行什么操作时触发的？是问题诊断、定时任务还是自定义脚本？",
            },
        }

        guide = guides.get(issue_type, guides["不回消息"])
        steps_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(guide["steps"])])

        reply = (
            f"{guide['header']}\n\n"
            f"{steps_text}\n\n"
            f"{guide['ask']}\n\n"
            f"完成后请告诉我结果。如果问题已解决，那太好了；如果还在，我会帮您记录给技术团队。"
        )

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={"reply": reply, "steps": guide["steps"]},
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {"issue_type": {"type": "string"}, "product_type": {"type": "string", "default": "云端"}}
