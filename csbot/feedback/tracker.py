"""工单状态跟踪。内存级索引 + 结构化数据输出，生产环境接 Bitable/Redis。"""
from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from csbot.sops.bitable import BitableClient
from typing import Any, Dict, List, Optional
import json
import time


class CSTicketTrackerSkill(BaseTool):
    """工单状态跟踪与续跟管理（已接入飞书多维表格）"""

    def __init__(
        self,
        bitable: Optional[BitableClient] = None,
        app_token: Optional[str] = None,
        table_id: Optional[str] = None,
    ):
        super().__init__("cs_ticket_tracker", "工单状态跟踪")
        self.bitable = bitable
        self.app_token = app_token
        self.table_id = table_id
        # 当未配置 bitable 时回退到内存字典（兼容旧行为）
        self._tickets: Dict[str, Dict] = {}
        self._fallback = bitable is None or not app_token or not table_id

    def _make_tid(self, prefix: str = "T") -> str:
        return f"{prefix}{int(time.time() * 1000)}"

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _build_fields(
        self,
        tid: str,
        ttype: str,
        status: str,
        bug_info: Optional[Dict],
        parent_id: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> Dict:
        """构建 Bitable 字段字典"""
        info = bug_info or {}
        user_info = {
            "user_id": info.get("user_id", ""),
            "session_id": info.get("session_id", ""),
        }
        return {
            "工单ID": tid,
            "类型": "原始工单" if ttype == "original" else "续跟",
            "父工单ID": parent_id or "",
            "状态": self._status_display(status),
            "问题描述": info.get("issue_desc", "") or str(info.get("collected", "")),
            "用户信息": json.dumps(user_info, ensure_ascii=False),
            "反馈内容": feedback or "",
            "创建时间": self._now_ms(),
            "更新时间": self._now_ms(),
        }

    def _status_display(self, status: str) -> str:
        mapping = {
            "open": "待处理",
            "pending": "处理中",
            "resolved": "已修复",
            "unresolvable": "不可修复",
            "human_escalation": "已转人工",
        }
        return mapping.get(status, status)

    def _status_code(self, display: str) -> str:
        mapping = {
            "待处理": "open",
            "处理中": "pending",
            "已修复": "resolved",
            "不可修复": "unresolvable",
            "已转人工": "human_escalation",
        }
        return mapping.get(display, display)

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
            tid = self._make_tid("T")
            record = {
                "id": tid,
                "type": "original",
                "parent_id": None,
                "status": "open",
                "info": dict(bug_info),
                "feedback": None,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            if self._fallback:
                self._tickets[tid] = record
            else:
                fields = self._build_fields(tid, "original", "open", bug_info)
                await self.bitable.upsert_raw(
                    fields=fields,
                    dedup_keys=["用户信息", "问题描述"],
                    app_token=self.app_token,
                    table_id=self.table_id,
                )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={"ticket_id": tid, "status": "open", "type": "original"},
            )

        # ── 2. 续跟工单 ──────────────────────────────
        if action == "follow_up" and bug_info:
            parent_id = bug_info.get("parent_record_id") or bug_info.get("parent_id")
            tid = self._make_tid("FU")
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
            if self._fallback:
                self._tickets[tid] = record
            else:
                fields = self._build_fields(tid, "follow_up", "open", bug_info, parent_id=parent_id)
                await self.bitable.create_raw(
                    fields=fields,
                    app_token=self.app_token,
                    table_id=self.table_id,
                )
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
            msg = feedback_message or ""
            status = "pending"
            reply = None

            if any(w in msg for w in {"已修复", "修复方案", "解决了"}):
                status = "resolved"
                reply = f"问题已定位并修复。{msg}\n\n如仍有问题随时@我。"
            elif any(w in msg for w in {"不可修复", "无法解决", "暂不支持"}):
                status = "unresolvable"
                reply = (
                    f"经排查，该问题目前暂无法修复。原因：{msg}\n\n"
                    f"替代方案：设置 → 恢复初始设置（保留工作空间和记忆）。"
                )
            elif any(w in msg for w in {"需要转人工", "转人工", "人工处理"}):
                status = "human_escalation"
                reply = "该问题需要人工客服进一步处理，已为您转接，请稍等。"

            if self._fallback:
                t = self._tickets.get(ticket_id)
                if not t:
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.FAILED,
                        result=None,
                        error_message="Ticket not found",
                    )
                t["feedback"] = msg
                t["status"] = status
                t["updated_at"] = time.time()
            else:
                records = await self.bitable.search_records(
                    filter_str=f'CurrentValue.[工单ID] == "{ticket_id}"',
                    app_token=self.app_token,
                    table_id=self.table_id,
                )
                if not records:
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.FAILED,
                        result=None,
                        error_message="Ticket not found",
                    )
                record_id = records[0]["record_id"]
                await self.bitable.update_record_fields(
                    record_id=record_id,
                    fields={
                        "状态": self._status_display(status),
                        "反馈内容": msg,
                        "更新时间": self._now_ms(),
                    },
                    app_token=self.app_token,
                    table_id=self.table_id,
                )

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                result={
                    "ticket_id": ticket_id,
                    "status": status,
                    "user_reply": reply,
                    "type": "original",
                },
            )

        # ── 4. 查询单条 ───────────────────────────────
        if action == "get" and ticket_id:
            if self._fallback:
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
            else:
                records = await self.bitable.search_records(
                    filter_str=f'CurrentValue.[工单ID] == "{ticket_id}"',
                    app_token=self.app_token,
                    table_id=self.table_id,
                )
                if not records:
                    return ToolResult(
                        tool_name=self.name,
                        status=ToolStatus.FAILED,
                        result=None,
                        error_message="Ticket not found",
                    )
                fields = records[0]["fields"]
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    result=self._fields_to_ticket(fields),
                )

        # ── 5. 查询全部 ───────────────────────────────
        if action == "list":
            if self._fallback:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    result=list(self._tickets.values()),
                )
            else:
                records = await self.bitable.search_records(
                    app_token=self.app_token,
                    table_id=self.table_id,
                )
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    result=[self._fields_to_ticket(r["fields"]) for r in records],
                )

        # ── 6. 按状态筛选 ─────────────────────────────
        if action == "list_by_status":
            target = kwargs.get("status", "open")
            if self._fallback:
                items = [t for t in self._tickets.values() if t["status"] == target]
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    result=items,
                )
            else:
                display_status = self._status_display(target)
                records = await self.bitable.search_records(
                    filter_str=f'CurrentValue.[状态] == "{display_status}"',
                    app_token=self.app_token,
                    table_id=self.table_id,
                )
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    result=[self._fields_to_ticket(r["fields"]) for r in records],
                )

        # ── 7. 按用户查询 ─────────────────────────────
        if action == "list_by_user":
            user_id = kwargs.get("user_id", "")
            if self._fallback:
                items = [
                    t for t in self._tickets.values()
                    if t.get("info", {}).get("user_id") == user_id
                ]
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    result=items,
                )
            else:
                records = await self.bitable.search_records(
                    filter_str=f'CurrentValue.[用户信息] contains "\"user_id\":\"{user_id}\""',
                    app_token=self.app_token,
                    table_id=self.table_id,
                )
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    result=[self._fields_to_ticket(r["fields"]) for r in records],
                )

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.FAILED,
            result=None,
            error_message="Invalid action",
        )

    def _fields_to_ticket(self, fields: Dict) -> Dict:
        """将 Bitable 字段转回内部 ticket 结构"""
        user_info = {}
        try:
            user_info = json.loads(fields.get("用户信息", "{}"))
        except Exception:
            pass
        # 将问题描述也注入 info，方便上层统一读取
        user_info["issue_desc"] = fields.get("问题描述", "")
        return {
            "id": fields.get("工单ID", ""),
            "type": "original" if fields.get("类型") == "原始工单" else "follow_up",
            "parent_id": fields.get("父工单ID") or None,
            "status": self._status_code(fields.get("状态", "")),
            "info": user_info,
            "feedback": fields.get("反馈内容", ""),
            "created_at": fields.get("创建时间", 0) // 1000 if isinstance(fields.get("创建时间"), int) else 0,
            "updated_at": fields.get("更新时间", 0) // 1000 if isinstance(fields.get("更新时间"), int) else 0,
        }

    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "enum": ["create", "follow_up", "update", "get", "list", "list_by_status", "list_by_user"],
            },
            "ticket_id": {"type": "string", "optional": True},
            "bug_info": {"type": "object", "optional": True},
            "feedback_message": {"type": "string", "optional": True},
            "user_id": {"type": "string", "optional": True},
            "status": {"type": "string", "optional": True},
        }
