# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 飞书API测试脚本
"""

import httpx
import json
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FEISHU_APP_ID, FEISHU_APP_SECRET

if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
    print("❌ 请先在 .env 文件中配置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    sys.exit(1)

print("=" * 60)
print("   飞书API连接测试")
print("=" * 60)

print("\n步骤1: 获取 tenant_access_token...")

url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"

headers = {"Content-Type": "application/json"}
data = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}

try:
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get("code") == 0:
                token = result["tenant_access_token"]
                expire = result["expire"]
                
                print("✅ 获取 tenant_access_token 成功！")
                print(f"Token: {token[:20]}...")
                print(f"有效期: {expire} 秒")
                
                print("\n步骤2: 测试权限...")
                wiki_url = "https://open.feishu.cn/open-apis/wiki/v2/spaces"
                wiki_headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
                
                wiki_response = client.get(wiki_url, headers=wiki_headers)
                if wiki_response.status_code == 200:
                    wiki_result = wiki_response.json()
                    print("✅ 知识库权限正常")
                else:
                    print(f"⚠️ 知识库权限测试失败: {wiki_response.status_code}")
                
                print("\n" + "=" * 60)
                print("   ✅ 飞书API连接测试成功！")
                print("=" * 60)
            else:
                print(f"❌ 获取token失败: {result.get('msg')}")
        else:
            print(f"❌ 请求失败: {response.status_code}")
except Exception as e:
    print(f"❌ 测试失败: {e}")
