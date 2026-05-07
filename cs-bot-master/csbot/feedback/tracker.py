"""工单状态跟踪。内存级索引 + 结构化数据输出，生产环境接 Bitable/Redis。"""
from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict, Optional
import time


class CSTicketTrackerSkill(BaseTool):
    """工单状态跟踪与续跟管理"""

    def __init__(self):
        super().__init__("cs_ticket_tracker", "工单状态跟踪")
        self._tickets: Dict[str, Dict] = {}

    async def execute(
        self,
        action: str,
        ticket_id: Optional[str] = None,
        bug_info: Optional[Dict] = None,
        feedback_message: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:

        # ── 1. 创建新工单 ──────────────────────────────
        if action == "create" and bug_info:
            tid = f"T{int(time.time() * 1000)}"
            self._tickets[tid] = {
                "id": tid,
                "type": "original",
                "parent_id": None,
                "status": "open",
                "info": dict(bug_info),
                "feedback": None,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={"ticket_id": tid, "status": "open", "type": "original"},
            )

        # ── 2. 续跟工单 ──────────────────────────────
        if action == "follow_up" and bug_info:
            parent_id = bug_info.get("parent_record_id") or bug_info.get("parent_id")
            tid = f"FU{int(time.time() * 1000)}"
            record = {
                "id": tid,
                "type": "follow_up",
                "parent_id": parent_id,
                "status": "open",
                "info": dict(bug_info),
                "feedback": None,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            self._tickets[tid] = record
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "ticket_id": tid,
                    "status": "open",
                    "type": "follow_up",
                    "parent_id": parent_id,
                },
            )

        # ── 3. 更新工单（Feedback Bot / 研发回复）──────
        if action == "update" and ticket_id:
            t = self._tickets.get(ticket_id)
            if not t:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.FAILED,
                    result=None,
                    error_message="Ticket not found",
                )

            t["feedback"] = feedback_message or ""
            t["updated_at"] = time.time()
            msg = feedback_message or ""

            if any(w in msg for w in {"已修复", "修复方案", "解决了"}):
                t["status"] = "resolved"
                reply = (
                    f"问题已定位并修复。{msg}\n\n"
                    f"如仍有问题随时@我。"
                )
            elif any(w in msg for w in {"不可修复", "无法解决", "暂不支持"}):
                t["status"] = "unresolvable"
                reply = (
                    f"经排查，该问题目前暂无法修复。原因：{msg}\n\n"
                    f"替代方案：设置 → 恢复初始设置（保留工作空间和记忆）。"
                )
            elif any(w in msg for w in {"需要转人工", "转人工", "人工处理"}):
                t["status"] = "human_escalation"
                reply = "该问题需要人工客服进一步处理，已为您转接，请稍等。"
            else:
                t["status"] = "pending"
                reply = None

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "ticket_id": ticket_id,
                    "status": t["status"],
                    "user_reply": reply,
                    "type": t["type"],
                    "parent_id": t.get("parent_id"),
                },
            )

        # ── 4. 查询单条 ───────────────────────────────
        if action == "get" and ticket_id:
            t = self._tickets.get(ticket_id)
            if not t:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.FAILED,
                    result=None,
                    error_message="Ticket not found",
                )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result=dict(t),
            )

        # ── 5. 查询全部 ───────────────────────────────
        if action == "list":
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result=list(self._tickets.values()),
            )

        # ── 6. 按状态筛选 ─────────────────────────────
        if action == "list_by_status":
            target = kwargs.get("status", "open")
            items = [t for t in self._tickets.values() if t["status"] == target]
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result=items,
            )

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.FAILED,
            result=None,
            error_message="Invalid action",
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "enum": ["create", "follow_up", "update", "get", "list", "list_by_status"],
            },
            "ticket_id": {"type": "string", "optional": True},
            "bug_info": {"type": "object", "optional": True},
            "feedback_message": {"type": "string", "optional": True},
        }