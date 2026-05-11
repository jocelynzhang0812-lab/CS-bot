"""飞书多维表格读写。CS Bot 只写 bug 类记录，轮询读 Feedback Bot 结论。"""
from typing import Dict, List, Optional
from dataclasses import dataclass
import aiohttp
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


@dataclass
class BitableRecord:
    feedback_time: str          # YYYY-MM-DD HH:mm
    feedback_source: str        # 用户群名称
    user_id: str                # Feishu 用户 ID
    session_id: str             # 群组会话 ID
    issue_type: str             # 固定 bug
    skill: str                  # 匹配到的 skill
    error_info: str             # 报错描述 + Bot ID
    screenshot: str             # 截图链接
    bot_id: str                 # Bot ID
    deploy_method: str          # 云端/飞书/微信/微博/企微/本地
    bot_status: str             # 绿色在线/红色离线/未确认
    self_check: str             # 自助检查结果
    scene: str                  # 定时任务/无响应/报错/Bot离线/记忆问题/其他
    diag_detail: str            # AI 诊断详细报错
    platform_tag: str           # 平台特定标记
    status: str = "待处理"       # 待处理/已处理（Feedback Bot 写）
    analysis: str = ""          # Feedback Bot 分析结论
    fix_plan: str = ""          # 已修复/需要转人工/用户处理兜底方案
    analysis_date: str = ""     # Feedback Bot 完成时间
    suggestion: str = ""        # 建议回复
    conclusion: str = ""        # CS Bot 汇总写入


class BitableClient:
    def __init__(self, app_token: str = None, table_id: str = None, feishu_app_id: str = None, feishu_secret: str = None):
        self.app_token = app_token or os.getenv("BITABLE_APP_TOKEN", "")
        self.table_id = table_id or os.getenv("BITABLE_TABLE_ID", "")
        self.app_id = feishu_app_id or os.getenv("FEISHU_APP_ID", "")
        self.secret = feishu_secret or os.getenv("FEISHU_APP_SECRET", "")
        self.base_url = "https://open.feishu.cn/open-apis/bitable/v1"

    async def _token(self) -> str:
        """获取 tenant_access_token"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={"app_id": self.app_id, "app_secret": self.secret}) as r:
                data = await r.json()
                if data.get("code") != 0:
                    raise RuntimeError(
                        f"飞书 token 获取失败: code={data.get('code')}, msg={data.get('msg')}, "
                        f"请检查 FEISHU_APP_ID / FEISHU_APP_SECRET 配置"
                    )
                token = data.get("tenant_access_token")
                if not token:
                    raise RuntimeError("飞书 token 获取失败: 响应中缺少 tenant_access_token")
                return token

    async def create(self, record: BitableRecord) -> Dict:
        """CS Bot Step 5：新建 bug 记录"""
        token = await self._token()
        url = f"{self.base_url}/apps/{self.app_token}/tables/{self.table_id}/records"
        fields = {
            "反馈时间": record.feedback_time,
            "反馈来源": record.feedback_source,
            "用户ID": record.user_id,
            "会话ID": record.session_id,
            "问题类型": record.issue_type,
            "涉及Skill": record.skill,
            "关键错误信息": record.error_info,
            "截图附件": record.screenshot,
            "Bot ID": record.bot_id,
            "部署方式": record.deploy_method,
            "Bot 状态": record.bot_status,
            "自助检查结果": record.self_check,
            "场景分类": record.scene,
            "诊断错误内容": record.diag_detail,
            "平台特定标记": record.platform_tag,
            "处理状态": record.status,
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(url, headers={"Authorization": f"Bearer {token}"}, json={"fields": fields}) as r:
                return await r.json()

    async def list_today(self) -> List[Dict]:
        """Step 6：轮询当天记录"""
        # 实际应加 filter：反馈时间 = 今天 AND 处理状态 = 待处理
        token = await self._token()
        url = f"{self.base_url}/apps/{self.app_token}/tables/{self.table_id}/records"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers={"Authorization": f"Bearer {token}"}) as r:
                data = await r.json()
                return data.get("data", {}).get("items", [])

    async def create_raw(self, fields: Dict, app_token: str = None, table_id: str = None) -> Dict:
        """通用写入：支持传入任意字段字典，可覆盖目标表格（用于写入产品建议等非 bug 表）。"""
        token = await self._token()
        app = app_token or self.app_token
        tbl = table_id or self.table_id
        url = f"{self.base_url}/apps/{app}/tables/{tbl}/records"
        async with aiohttp.ClientSession() as s:
            async with s.post(url, headers={"Authorization": f"Bearer {token}"}, json={"fields": fields}) as r:
                return await r.json()

    async def upsert_raw(
        self,
        fields: Dict,
        dedup_keys: List[str] = None,
        app_token: str = None,
        table_id: str = None,
    ) -> Dict:
        """自动去重写入（Upsert）。

        根据 dedup_keys 指定的字段组合查询现有记录：
        - 若存在 → 追加更新（反馈内容合并、问题类型按优先级升级）
        - 若不存在 → 新建记录

        默认去重键：["用户ID", "反馈来源", "反馈时间"]（反馈时间取日期部分）
        """
        app = app_token or self.app_token
        tbl = table_id or self.table_id
        dedup_keys = dedup_keys or ["用户ID", "反馈来源", "反馈时间"]

        # 1. 构造 filter 查询条件
        filter_parts = []
        for key in dedup_keys:
            val = fields.get(key, "")
            if not val:
                continue
            # 反馈时间取日期部分匹配（支持 "2026-05-01 12:00" → "2026-05-01"）
            if key in ("反馈时间", "收录时间", "提交时间") and len(str(val)) > 10:
                val = str(val)[:10]
                filter_parts.append(f'CurrentValue.[{key}] contains "{val}"')
            else:
                filter_parts.append(f'CurrentValue.[{key}] == "{val}"')

        if len(filter_parts) == len(dedup_keys) and filter_parts:
            filter_str = " AND ".join(filter_parts)
            existing = await self.search_records(
                filter_str=filter_str,
                app_token=app,
                table_id=tbl,
            )

            if existing:
                record_id = existing[0]["record_id"]
                old_fields = existing[0]["fields"]

                # 2. 合并字段策略
                update_fields: Dict = {}

                # 2.1 文本类字段：追加合并（去重）
                mergeable_text_keys = {"反馈内容", "用户描述", "关键错误信息", "建议内容", "问题描述"}
                for mk in mergeable_text_keys:
                    old_val = self._extract_text(old_fields.get(mk))
                    new_val = fields.get(mk, "")
                    if old_val and new_val and new_val not in old_val:
                        update_fields[mk] = old_val + "\n---\n" + new_val
                    elif new_val and not old_val:
                        update_fields[mk] = new_val

                # 2.2 问题类型/建议类型：按优先级升级
                priority_map = {
                    "功能异常": 4,
                    "付费投诉": 4,
                    "Bug 反馈": 4,
                    "Bug": 4,
                    "配置问题": 3,
                    "产品建议": 3,
                    "使用咨询": 2,
                    "其他": 1,
                }
                type_keys = {"问题类型", "反馈类型", "建议类型"}
                for tk in type_keys:
                    old_type = old_fields.get(tk, "")
                    new_type = fields.get(tk, "")
                    if old_type and new_type:
                        old_p = priority_map.get(old_type, 0)
                        new_p = priority_map.get(new_type, 0)
                        if new_p > old_p:
                            update_fields[tk] = new_type
                    elif new_type and not old_type:
                        update_fields[tk] = new_type

                # 2.3 处理状态：向更紧急方向升级
                status_priority = {
                    "待处理": 4,
                    "需人工跟进": 4,
                    "处理中": 3,
                    "待评估": 3,
                    "已处理": 2,
                    "已解答": 2,
                    "已修复": 1,
                }
                old_status = old_fields.get("处理状态", "")
                new_status = fields.get("处理状态", "")
                if old_status and new_status:
                    if status_priority.get(new_status, 0) > status_priority.get(old_status, 0):
                        update_fields["处理状态"] = new_status
                elif new_status and not old_status:
                    update_fields["处理状态"] = new_status

                # 2.4 其他简单字段：新值非空则覆盖
                override_keys = {"Bot ID", "Bot回复摘要", "影响功能", "部署方式", "场景分类", "自助检查结果"}
                for ok in override_keys:
                    if ok in fields and fields[ok]:
                        update_fields[ok] = fields[ok]

                # 2.5 研发备注：追加其他人反馈
                old_note = self._extract_text(old_fields.get("研发备注"))
                new_note = fields.get("研发备注", "")
                if old_note and new_note and new_note not in old_note:
                    update_fields["研发备注"] = old_note + "\n" + new_note
                elif new_note and not old_note:
                    update_fields["研发备注"] = new_note

                if update_fields:
                    result = await self.update_record_fields(
                        record_id=record_id,
                        fields=update_fields,
                        app_token=app,
                        table_id=tbl,
                    )
                    result["action"] = "updated"
                    return result
                else:
                    return {
                        "code": 0,
                        "msg": "duplicate_no_change",
                        "action": "duplicate",
                        "data": {"record": {"record_id": record_id}},
                    }

        # 3. 无匹配 → 新建
        result = await self.create_raw(fields=fields, app_token=app, table_id=tbl)
        result["action"] = "created"
        return result

    @staticmethod
    def _extract_text(field_val):
        """统一提取飞书富文本字段中的纯文本。"""
        if isinstance(field_val, list) and len(field_val) > 0:
            return field_val[0].get("text", "")
        return str(field_val) if field_val is not None else ""

    async def write_conclusion(self, record_id: str, conclusion: str) -> Dict:
        """CS Bot 读取修复方案+建议回复后，写入结论"""
        token = await self._token()
        url = f"{self.base_url}/apps/{self.app_token}/tables/{self.table_id}/records/{record_id}"
        async with aiohttp.ClientSession() as s:
            async with s.put(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={"fields": {"结论": conclusion}},
            ) as r:
                return await r.json()

    async def search_records(
        self,
        filter_str: str = "",
        app_token: str = None,
        table_id: str = None,
    ) -> List[Dict]:
        """按 filter 条件查询记录，返回 fields + record_id 列表"""
        token = await self._token()
        app = app_token or self.app_token
        tbl = table_id or self.table_id
        url = f"{self.base_url}/apps/{app}/tables/{tbl}/records/search"
        payload: Dict = {"page_size": 500}
        if filter_str:
            payload["filter"] = filter_str
        async with aiohttp.ClientSession() as s:
            async with s.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            ) as r:
                data = await r.json()
                items = data.get("data", {}).get("items", [])
                return [{"record_id": i.get("record_id"), "fields": i.get("fields", {})} for i in items]

    async def update_record_fields(
        self,
        record_id: str,
        fields: Dict,
        app_token: str = None,
        table_id: str = None,
    ) -> Dict:
        """按 record_id 更新指定字段"""
        token = await self._token()
        app = app_token or self.app_token
        tbl = table_id or self.table_id
        url = f"{self.base_url}/apps/{app}/tables/{tbl}/records/{record_id}"
        async with aiohttp.ClientSession() as s:
            async with s.put(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={"fields": fields},
            ) as r:
                return await r.json()

    async def delete_record(
        self,
        record_id: str,
        app_token: str = None,
        table_id: str = None,
    ) -> Dict:
        """按 record_id 删除记录"""
        token = await self._token()
        app = app_token or self.app_token
        tbl = table_id or self.table_id
        url = f"{self.base_url}/apps/{app}/tables/{tbl}/records/{record_id}"
        async with aiohttp.ClientSession() as s:
            async with s.delete(url, headers={"Authorization": f"Bearer {token}"}) as r:
                return await r.json()