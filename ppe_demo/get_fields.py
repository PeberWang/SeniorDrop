# -*- coding: utf-8 -*-
"""
查询多维表格字段列表（输出到文件）
"""

import asyncio
import sys
import os
import httpx
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BASE_URL


async def get_bitable_fields():
    """查询多维表格字段"""
    
    APP_TOKEN = "BE36bJd65aOFjMs1NqvcxSnIn7f"
    TABLE_ID = "tblTD0jKzXTXFI4b"
    
    print("Getting bitable fields...")
    
    # 获取token
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. 获取 tenant_access_token
        url = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
        response = await client.post(url, json={
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        })
        result = response.json()
        token = result["tenant_access_token"]
        
        # 2. 查询字段列表
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields"
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = await client.get(url, headers=headers)
        result = response.json()
        
        if result.get("code") == 0:
            fields = result["data"]["items"]
            
            # 保存到JSON文件
            output_file = "bitable_fields.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(fields, f, ensure_ascii=False, indent=2)
            
            print(f"Field list saved to: {output_file}")
            print(f"Total fields: {len(fields)}")
            
            # 打印字段名（用英文描述类型）
            print("\nField names:")
            for i, field in enumerate(fields, 1):
                field_name = field.get("field_name", "N/A")
                field_type = field.get("type", 0)
                
                type_map = {
                    1: "Text", 2: "Number", 3: "SingleSelect", 4: "MultiSelect",
                    5: "Date", 7: "Checkbox", 11: "User", 13: "Phone",
                    15: "URL", 17: "Attachment", 18: "Link", 19: "Formula",
                    20: "TwoWayLink", 21: "Location", 22: "Group",
                    23: "Barcode", 1001: "CreatedTime", 1002: "ModifiedTime",
                    1003: "CreatedBy", 1004: "ModifiedBy", 1005: "AutoNumber"
                }
                
                type_name = type_map.get(field_type, f"Type{field_type}")
                print(f"  {i}. [{type_name}] {field_name}")
            
            return fields
        
        else:
            print(f"Failed: {result.get('msg')}")
            return None


if __name__ == "__main__":
    asyncio.run(get_bitable_fields())
