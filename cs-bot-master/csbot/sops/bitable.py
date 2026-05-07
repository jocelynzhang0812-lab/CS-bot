"""飞书多维表格读写。CS Bot 只写 bug 类记录，轮询读 Feedback Bot 结论。"""
from typing import Dict, List, Optional
from dataclasses import dataclass
import aiohttp


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
    def __init__(self, app_token: str, table_id: str, feishu_app_id: str, feishu_secret: str):
        self.app_token = app_token
        self.table_id = table_id
        self.app_id = feishu_app_id
        self.secret = feishu_secret
        self.base_url = "https://open.feishu.cn/open-apis/bitable/v1"

    async def _token(self) -> str:
        """获取 tenant_access_token"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json={"app_id": self.app_id, "app_secret": self.secret}) as r:
                data = await r.json()
                return data["tenant_access_token"]

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