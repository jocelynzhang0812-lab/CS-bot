"""飞书消息发送封装。实际调用 kitty-feishu skill 或飞书 OpenAPI"""
from typing import Dict, Any


class FeishuIntegration:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret

    async def send_text(self, chat_id: str, text: str) -> Dict[str, Any]:
        # TODO: 接入 kitty-feishu 或飞书 Bot API
        return {"chat_id": chat_id, "text": text, "status": "sent"}

    async def send_card(self, chat_id: str, card_markdown: str, at_users: list = None) -> Dict[str, Any]:
        # TODO: 接入飞书消息卡片 API
        return {"chat_id": chat_id, "card": card_markdown, "at": at_users or [], "status": "sent"}
        