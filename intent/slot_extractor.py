"""
Layer 2 槽位提取器

提取字段：product, version, error_code, bot_id, symptom, reproduced
缺失字段填 null，不得猜测或捏造。
输出纯 JSON（不加 markdown 代码块）。
"""

import json
import re
from typing import Dict, Optional


SLOT_PROMPT = """你是一个槽位提取器。请从以下用户输入中提取结构化信息。

可提取字段：
- product: 产品名称（如 Kimi Claw、Kimi Code、Kimi API 等）
- version: 版本号（如 v2.6.3、1.0.0 等）
- error_code: 错误码（如 401、403、404、500 等）
- bot_id: Bot ID（通常是字母数字组合的字符串）
- symptom: 故障症状描述
- reproduced: 是否可复现（true / false / null）

规则：
- 字段值必须从用户输入中明确提取，不得猜测或捏造
- 未提及的字段值设为 null
- 只输出纯 JSON，不加 markdown 代码块，不加解释

用户输入：{user_input}

输出："""


class SlotExtractor:
    """槽位提取器。用 LLM 提取结构化字段，代码层做容错校验。"""

    VALID_SLOTS = {"product", "version", "error_code", "bot_id", "symptom", "reproduced"}

    def __init__(self, llm_client):
        self.llm = llm_client

    async def extract(self, user_input: str) -> Dict[str, Optional[str]]:
        """
        提取槽位。
        :return: {slot_name: value | null}
        """
        if not user_input or not user_input.strip():
            return {k: None for k in self.VALID_SLOTS}

        # 快速规则提取（不调用 LLM）
        fast_slots = self._fast_extract(user_input)

        # LLM 提取
        try:
            prompt = SLOT_PROMPT.format(user_input=user_input.strip())
            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                top_p=0.1,
            )
            raw = response.get("content", "").strip()

            # 清理 markdown 代码块
            raw = raw.replace("```json", "").replace("```", "").strip()

            # 解析 JSON
            slots = json.loads(raw)

            # 校验：只保留有效字段
            validated = {}
            for k in self.VALID_SLOTS:
                v = slots.get(k)
                # 空字符串、"null"、"None" 都转为 None
                if v in ("", "null", "None", "none", "NULL"):
                    v = None
                validated[k] = v

            # 合并快速规则提取的结果（规则层优先）
            for k, v in fast_slots.items():
                if v is not None:
                    validated[k] = v

            return validated

        except json.JSONDecodeError as e:
            print(f"[SlotExtractor] JSON 解析失败: {e}, raw='{raw[:200]}'")
            # 回退到规则提取结果
            result = {k: None for k in self.VALID_SLOTS}
            result.update(fast_slots)
            return result
        except Exception as e:
            print(f"[SlotExtractor] LLM 调用失败: {e}")
            result = {k: None for k in self.VALID_SLOTS}
            result.update(fast_slots)
            return result

    def _fast_extract(self, text: str) -> Dict[str, Optional[str]]:
        """基于正则的快速槽位提取。"""
        result = {k: None for k in self.VALID_SLOTS}
        lower = text.lower()

        # error_code: HTTP 状态码
        codes = re.findall(r'\b(4\d{2}|5\d{2})\b', text)
        if codes:
            result["error_code"] = codes[0]

        # version: vX.Y.Z 或 X.Y.Z
        versions = re.findall(r'[vV]?(\d+\.\d+(?:\.\d+)?)', text)
        if versions:
            result["version"] = versions[0] if versions[0].startswith("v") else versions[0]

        # bot_id: 常见 Bot ID 格式（字母数字组合，长度 8-32）
        bot_ids = re.findall(r'[a-zA-Z0-9_-]{8,32}', text)
        if bot_ids:
            # 过滤掉可能是版本号、时间戳的
            for bid in bot_ids:
                if not re.match(r'^\d+$', bid) and not re.match(r'^v?\d+\.\d+', bid):
                    result["bot_id"] = bid
                    break

        # product: 产品关键词
        products = {
            "kimi claw": "Kimi Claw",
            "kimi code": "Kimi Code",
            "kimi api": "Kimi API",
            "kimi websites": "Kimi Websites",
            "kimi docs": "Kimi Docs",
            "kimi sheets": "Kimi Sheets",
        }
        for kw, name in products.items():
            if kw in lower:
                result["product"] = name
                break

        # reproduced
        if any(w in lower for w in {"每次", "总是", "必现", "100%", "稳定复现"}):
            result["reproduced"] = True
        elif any(w in lower for w in {"偶尔", "有时", "随机", "不稳定", "不是每次"}):
            result["reproduced"] = False

        return result
