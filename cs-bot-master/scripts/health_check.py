#!/usr/bin/env python3
"""检查环境变量、API 连通性"""
import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

async def check():
    required = ["KIMI_API_KEY", "FEISHU_APP_ID", "FEISHU_APP_SECRET", "BITABLE_APP_TOKEN", "BITABLE_TABLE_ID"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"❌ 缺失环境变量: {missing}")
        exit(1)
    
    # 测试 Kimi API
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.getenv("KIMI_API_KEY"), base_url="https://api.moonshot.cn/v1")
    try:
        await client.models.list()
        print("✅ Kimi API 连通")
    except Exception as e:
        print(f"❌ Kimi API 失败: {e}")
        exit(1)
    
    print("✅ 全部通过")

if __name__ == "__main__":
    asyncio.run(check())