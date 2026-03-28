# -*- coding: utf-8 -*-
"""
测试多维表格API访问（使用正确的字段名）
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.feishu_service import FeishuService


async def test_bitable_access():
    """测试多维表格访问"""
    
    # 多维表格信息
    APP_TOKEN = "BE36bJd65aOFjMs1NqvcxSnIn7f"
    TABLE_ID = "tblTD0jKzXTXFI4b"
    
    print("Testing bitable access with correct field names...")
    print(f"App Token: {APP_TOKEN}")
    print(f"Table ID: {TABLE_ID}")
    
    service = FeishuService()
    
    try:
        # 1. 获取token
        print("\n1. Getting tenant_access_token...")
        token = await service.get_tenant_access_token()
        print(f"Token obtained: {token[:20]}...")
        
        # 2. 尝试添加一条测试记录
        print("\n2. Trying to add test record...")
        
        # 使用正确的字段名
        test_fields = {
            "资料名称": "API测试记录-世界经济概论PPT",
            "课程": "世界经济概论",
            "资料类型": "PPT",
            "年级": "22级",
            "贡献者": "小劳（API测试）",
            "推荐理由": "这是一条API测试记录，用于验证字段映射是否正确",
            "文件链接": {
                "text": "测试链接",
                "link": "https://feishu.cn"
            },
            "上传时间": int(datetime.now().timestamp() * 1000)  # 毫秒时间戳
        }
        
        try:
            result = await service.add_bitable_record(
                app_token=APP_TOKEN,
                table_id=TABLE_ID,
                fields=test_fields
            )
            print(f"SUCCESS: Test record added!")
            print(f"   Record ID: {result['record']['record_id']}")
            print("\nBitable API access is working!")
            print("You can check the record in your bitable:")
            print(f"  https://fcnv1mrzetzi.feishu.cn/base/{APP_TOKEN}?table={TABLE_ID}")
            
        except Exception as e:
            error_msg = str(e)
            print(f"FAILED: {error_msg}")
            
            # 如果是单选选项不存在，尝试不包含单选字段
            if "option" in error_msg.lower() or "选项" in error_msg:
                print("\nTrying without single select fields...")
                
                test_fields_simple = {
                    "资料名称": "API测试记录（简化版）",
                    "贡献者": "小劳（API测试）",
                    "推荐理由": "测试记录-简化版"
                }
                
                try:
                    result = await service.add_bitable_record(
                        app_token=APP_TOKEN,
                        table_id=TABLE_ID,
                        fields=test_fields_simple
                    )
                    print(f"SUCCESS: Simple record added!")
                    print(f"   Record ID: {result['record']['record_id']}")
                    print("\nNote: Single select fields need options configured first")
                    
                except Exception as e2:
                    print(f"Still failed: {e2}")
            
    except Exception as e:
        print(f"Test failed: {e}")
    
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(test_bitable_access())
