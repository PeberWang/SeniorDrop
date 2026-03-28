# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 飞书服务
"""

import httpx
import json
from typing import Optional, Dict, List
import sys
import os
import io

# 修复Windows控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_BASE_URL


class FeishuService:
    """飞书API服务"""
    
    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self.base_url = FEISHU_BASE_URL
        self.tenant_access_token = None
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_tenant_access_token(self) -> str:
        """获取 tenant_access_token"""
        
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        response = await self.client.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            self.tenant_access_token = result["tenant_access_token"]
            return self.tenant_access_token
        else:
            raise Exception(f"获取token失败: {result.get('msg')}")
    
    async def _get_headers(self) -> dict:
        """获取请求头（包含token）"""
        if not self.tenant_access_token:
            await self.get_tenant_access_token()
        
        return {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }
    
    async def create_bitable(
        self,
        name: str,
        folder_token: Optional[str] = None
    ) -> Dict:
        """
        创建多维表格
        
        Args:
            name: 多维表格名称
            folder_token: 文件夹token（可选）
        
        Returns:
            创建结果，包含 app_token
        """
        
        url = f"{self.base_url}/bitable/v1/apps"
        
        headers = await self._get_headers()
        
        data = {
            "name": name
        }
        
        if folder_token:
            data["folder_token"] = folder_token
        
        response = await self.client.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            return result["data"]
        else:
            raise Exception(f"创建多维表格失败: {result.get('msg')}")
    
    async def add_bitable_record(
        self,
        app_token: str,
        table_id: str,
        fields: Dict
    ) -> Dict:
        """
        向多维表格添加记录
        
        Args:
            app_token: 多维表格token
            table_id: 数据表ID
            fields: 字段值（注意：字段必须已存在）
        
        Returns:
            添加的记录
        """
        
        url = f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        
        headers = await self._get_headers()
        
        data = {
            "fields": fields
        }
        
        response = await self.client.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            return result["data"]
        else:
            # 如果字段不存在，返回错误信息
            error_msg = result.get('msg', '未知错误')
            raise Exception(f"添加记录失败: {error_msg}")
    
    async def create_bitable_field(
        self,
        app_token: str,
        table_id: str,
        field_name: str,
        field_type: int = 1
    ) -> Dict:
        """
        创建多维表格字段
        
        Args:
            app_token: 多维表格token
            table_id: 数据表ID
            field_name: 字段名称
            field_type: 字段类型（1=文本, 2=数字, 3=单选, 4=多选, 5=日期, 7=复选框, 11=人员, 13=电话, 15=URL, 17=附件）
        
        Returns:
            创建的字段
        """
        
        url = f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        
        headers = await self._get_headers()
        
        data = {
            "field_name": field_name,
            "type": field_type
        }
        
        response = await self.client.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            return result["data"]
        else:
            raise Exception(f"创建字段失败: {result.get('msg')}")
    
    async def create_wiki_space(self, name: str) -> Dict:
        """
        创建知识库
        
        Args:
            name: 知识库名称
        
        Returns:
            创建结果，包含 space_id
        """
        
        url = f"{self.base_url}/wiki/v2/spaces"
        
        headers = await self._get_headers()
        
        data = {
            "name": name
        }
        
        response = await self.client.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            return result["data"]
        else:
            raise Exception(f"创建知识库失败: {result.get('msg')}")
    
    async def upload_file(
        self,
        file_path: str,
        parent_type: str = "bitable_file",
        parent_token: Optional[str] = None
    ) -> Dict:
        """
        上传文件到飞书云空间
        
        Args:
            file_path: 本地文件路径
            parent_type: 父对象类型
            parent_token: 父对象token
        
        Returns:
            上传结果，包含 file_token
        """
        
        url = f"{self.base_url}/drive/v1/medias/upload_all"
        
        headers = await self._get_headers()
        
        # 读取文件
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # 获取文件名
        file_name = os.path.basename(file_path)
        
        # 构建multipart/form-data
        files = {
            "file": (file_name, file_content),
            "file_name": (None, file_name),
            "parent_type": (None, parent_type),
        }
        
        if parent_token:
            files["parent_token"] = (None, parent_token)
        
        # 注意：上传文件时不使用 Content-Type: application/json
        headers_without_content_type = {
            "Authorization": headers["Authorization"]
        }
        
        response = await self.client.post(
            url,
            headers=headers_without_content_type,
            files=files
        )
        
        result = response.json()
        
        if result.get("code") == 0:
            return result["data"]
        else:
            raise Exception(f"上传文件失败: {result.get('msg')}")
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


# 测试代码
async def test_feishu_service():
    """测试飞书服务"""
    
    print("🧪 测试飞书服务...")
    
    service = FeishuService()
    
    try:
        # 1. 获取token
        print("\n1. 获取 tenant_access_token...")
        token = await service.get_tenant_access_token()
        print(f"✅ Token: {token[:20]}...")
        
        # 2. 创建多维表格
        print("\n2. 创建多维表格...")
        bitable = await service.create_bitable("PPE云端智能大礼包-测试")
        app_token = bitable['app']['app_token']
        table_id = bitable['app']['default_table_id']
        print(f"✅ 多维表格创建成功")
        print(f"   App Token: {app_token}")
        print(f"   Table ID: {table_id}")
        print(f"   访问链接: {bitable['app']['url']}")
        
        # 3. 创建字段
        print("\n3. 创建字段...")
        field = await service.create_bitable_field(
            app_token=app_token,
            table_id=table_id,
            field_name="资料名称",
            field_type=1  # 文本类型
        )
        print(f"✅ 字段创建成功: {field['field']['field_name']}")
        
        # 4. 添加测试记录
        print("\n4. 添加测试记录...")
        test_record = await service.add_bitable_record(
            app_token=app_token,
            table_id=table_id,
            fields={
                "资料名称": "测试资料"
            }
        )
        print(f"✅ 记录添加成功")
        print(f"   Record ID: {test_record['record']['record_id']}")
        
        print("\n✅ 飞书服务测试完成！")
        print(f"\n💡 提示：知识库创建失败可能是权限问题，需要检查wiki权限配置")
        print(f"\n📊 多维表格链接: {bitable['app']['url']}")
        
        print("\n✅ 飞书服务测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
    
    finally:
        await service.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_feishu_service())
