"""飞书消息发送封装。调用飞书 OpenAPI"""
import json
import time
from typing import Dict, Any, Optional
import httpx


class FeishuIntegration:
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        chat_id_map: Optional[Dict[str, str]] = None,
        user_id_map: Optional[Dict[str, str]] = None,
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.chat_id_map = chat_id_map or {}
        self.user_id_map = user_id_map or {}
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def _get_tenant_access_token(self) -> str:
        """获取 tenant_access_token，带过期缓存"""
        now = time.time()
        if self._token and now < self._token_expires_at - 60:
            return self._token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=10,
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"获取飞书 token 失败: {data}")

            self._token = data["tenant_access_token"]
            self._token_expires_at = now + data.get("expire", 7200)
            return self._token

    def _resolve_chat_id(self, chat_id: str) -> str:
        """将内部群标识映射为真实飞书 chat_id（oc_xxx）"""
        return self.chat_id_map.get(chat_id, chat_id)

    def _resolve_user_ids(self, at_users: Optional[list]) -> list:
        """将内部用户标识映射为真实飞书 user_id（ou_xxx）"""
        if not at_users:
            return []
        return [self.user_id_map.get(u, u) for u in at_users]

    async def send_text(
        self,
        chat_id: str,
        text: str,
        at_users: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        发送文本消息，支持 @ 人。

        Args:
            chat_id: 群聊 ID（或内部标识，需提前配置 chat_id_map）
            text: 文本内容
            at_users: 要 @ 的用户列表，元素为飞书 user_id 或内部标识
        """
        token = await self._get_tenant_access_token()
        real_chat_id = self._resolve_chat_id(chat_id)
        resolved_users = self._resolve_user_ids(at_users)

        # 飞书文本消息通过 <at> 标签实现 @
        if resolved_users:
            at_tags = "".join([f'<at user_id="{uid}"></at>' for uid in resolved_users])
            text = f"{at_tags} {text}"

        body = {
            "receive_id": real_chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        }

        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=headers,
                params={"receive_id_type": "chat_id"},
                json=body,
                timeout=10,
            )
            result = resp.json()
            if result.get("code") != 0:
                print(f"[FeishuIntegration] send_text 失败: {result}")
            return result

    async def send_card(
        self,
        chat_id: str,
        card_markdown: str,
        at_users: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        发送消息卡片，支持 @ 人。

        Args:
            chat_id: 群聊 ID（或内部标识，需提前配置 chat_id_map）
            card_markdown: 卡片中的 markdown 内容
            at_users: 要 @ 的用户列表
        """
        token = await self._get_tenant_access_token()
        real_chat_id = self._resolve_chat_id(chat_id)
        resolved_users = self._resolve_user_ids(at_users)

        # 在卡片内容中嵌入 @ 标签
        card_content = card_markdown
        if resolved_users:
            at_tags = " ".join([f'<at user_id="{uid}"></at>' for uid in resolved_users])
            card_content = f"{at_tags}\n\n{card_content}"

        card_data = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "通知"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": card_content,
                    }
                }
            ],
        }

        body = {
            "receive_id": real_chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card_data, ensure_ascii=False),
        }

        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers=headers,
                params={"receive_id_type": "chat_id"},
                json=body,
                timeout=10,
            )
            result = resp.json()
            if result.get("code") != 0:
                print(f"[FeishuIntegration] send_card 失败: {result}")
            return result
