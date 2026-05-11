from csbot.agent.core import BaseTool, ToolResult, ToolStatus
from typing import Any, Dict, List


class CSDailyReportSkill(BaseTool):
    """日报生成。生成 Markdown 报表和飞书多维表格数据结构"""

    def __init__(self):
        super().__init__("cs_daily_report", "日报生成")

    async def execute(self, date: str, cases: List[Dict], **kwargs) -> ToolResult:
        total = len(cases)
        resolved = sum(1 for c in cases if c.get("status") == "resolved")
        pending = sum(1 for c in cases if c.get("status") == "pending")
        human = sum(1 for c in cases if c.get("status") == "human_escalation")
        unresolvable = sum(1 for c in cases if c.get("status") == "unresolvable")

        md = [
            f"## 客服日报 {date}",
            f"**总 Case**: {total}",
            f"- 已解决: {resolved}",
            f"- 待修复: {pending}",
            f"- 转人工: {human}",
            f"- 不可修复: {unresolvable}",
            "",
            "### 重点问题 Top 5",
        ]
        for i, c in enumerate(cases[:5], 1):
            md.append(f"{i}. [{c.get('status', 'unknown')}] {c.get('issue_desc', '无描述')[:40]}...")

        payload = {
            "date": date,
            "total": total,
            "resolved": resolved,
            "pending": pending,
            "human_escalation": human,
            "unresolvable": unresolvable,
            "records": cases,
        }

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            result={"markdown": "\n".join(md), "bitable_payload": payload},
        )

    def _get_parameters(self) -> Dict[str, Any]:
        return {"date": {"type": "string"}, "cases": {"type": "array"}}