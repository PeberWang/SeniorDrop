# -*- coding: utf-8 -*-
"""
测试多维表格API访问
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from services.feishu_service import FeishuService


async def test_bitable_access():
    """测试多维表格访问"""
    
    # 多维表格信息
    APP_TOKEN = "BE36bJd65aOFjMs1NqvcxSnIn7f"
    TABLE_ID = "tblTD0jKzXTXFI4b"
    
    print("Testing bitable access...")
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
        
        test_fields = {
            "资料名称": "API测试记录",
            "课程名称": "世界经济概论",
            "资料类型": "PPT",
            "年级": "22级",
            "贡献者": "小劳（API测试）",
            "备注": "这是一条API测试记录，可以删除"
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
            
        except Exception as e:
            error_msg = str(e)
            print(f"FAILED: {error_msg}")
            
            # 判断错误类型
            if "field" in error_msg.lower() or "字段" in error_msg:
                print("\nPossible causes:")
                print("   - Field name mismatch")
                print("   - Single select option does not exist")
                print("   - Please check bitable field configuration")
            elif "permission" in error_msg.lower() or "权限" in error_msg:
                print("\nPossible causes:")
                print("   - App not added as bitable collaborator")
                print("   - Please follow these steps:")
                print("   1. Open the bitable")
                print("   2. Click 'Share' button (top right)")
                print("   3. Add app as collaborator (with edit permission)")
            else:
                print(f"\nError details: {error_msg}")
        
    except Exception as e:
        print(f"Test failed: {e}")
    
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(test_bitable_access())
