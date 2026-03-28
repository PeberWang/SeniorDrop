# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 飞书多维表格管理
创建和管理资料表、心得表
"""

import httpx
import json
from typing import Dict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.feishu_service import FeishuService


class BitableManager:
    """多维表格管理器"""
    
    def __init__(self):
        self.feishu = FeishuService()
        self.app_token = None
    
    async def create_ppe_bitable(self) -> Dict:
        """
        创建PPE云端智能大礼包的多维表格
        包含3个数据表：资料表、心得表、修订表
        """
        
        print("📊 创建PPE云端智能大礼包多维表格...")
        
        # 1. 创建多维表格
        bitable = await self.feishu.create_bitable("PPE云端智能大礼包")
        self.app_token = bitable['app']['app_token']
        default_table_id = bitable['app']['default_table_id']
        
        print(f"✅ 多维表格创建成功")
        print(f"   App Token: {self.app_token}")
        print(f"   访问链接: {bitable['app']['url']}")
        
        # 2. 配置资料表（重命名默认表）
        print("\n📋 配置资料表...")
        await self._setup_materials_table(default_table_id)
        
        # 3. 创建心得表
        print("\n📋 创建心得表...")
        experiences_table = await self._create_experiences_table()
        
        # 4. 创建修订表
        print("\n📋 创建修订表...")
        revisions_table = await self._create_revisions_table()
        
        # 5. 保存配置
        config = {
            "app_token": self.app_token,
            "tables": {
                "materials": default_table_id,
                "experiences": experiences_table,
                "revisions": revisions_table
            },
            "url": bitable['app']['url']
        }
        
        config_path = os.path.join(os.path.dirname(__file__), "feishu_bitable_config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 多维表格配置完成！")
        print(f"📁 配置已保存到 {config_path}")
        print(f"🔗 访问链接: {bitable['app']['url']}")
        
        return config
    
    async def _setup_materials_table(self, table_id: str):
        """配置资料表字段"""
        
        fields = [
            ("资料ID", 1),      # 文本
            ("资料名称", 1),    # 文本
            ("原始文件名", 1),  # 文本
            ("贡献者", 1),      # 文本
            ("年级", 3),        # 单选
            ("课程", 3),        # 单选
            ("资料类型", 3),    # 单选
            ("推荐理由", 1),    # 文本
            ("文件链接", 15),   # URL
            ("上传时间", 5),    # 日期
            ("审核状态", 3),    # 单选
        ]
        
        for field_name, field_type in fields:
            await self.feishu.create_bitable_field(
                self.app_token, table_id, field_name, field_type
            )
        
        print(f"   ✅ 资料表字段配置完成（{len(fields)}个字段）")
    
    async def _create_experiences_table(self) -> str:
        """创建心得表"""
        
        url = f"{self.feishu.base_url}/bitable/v1/apps/{self.app_token}/tables"
        headers = await self.feishu._get_headers()
        
        data = {
            "table": {
                "name": "心得体会"
            }
        }
        
        response = await self.feishu.client.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            # 检查返回数据结构
            if "data" in result:
                if "table" in result["data"]:
                    table_id = result["data"]["table"]["table_id"]
                elif "table_id" in result["data"]:
                    table_id = result["data"]["table_id"]
                else:
                    print(f"   调试信息: {result}")
                    return None
            else:
                print(f"   调试信息: {result}")
                return None
            
            # 创建字段
            fields = [
                ("心得ID", 1),
                ("作者", 1),
                ("年级", 3),
                ("课程", 3),
                ("成绩", 1),
                ("心得内容", 1),
                ("提取信息", 1),
                ("提交时间", 5),
                ("审核状态", 3),
                ("审核人", 1),
            ]
            
            for field_name, field_type in fields:
                await self.feishu.create_bitable_field(
                    self.app_token, table_id, field_name, field_type
                )
            
            print(f"   ✅ 心得表创建完成（{len(fields)}个字段）")
            return table_id
        else:
            raise Exception(f"创建心得表失败: {result.get('msg')}")
    
    async def _create_revisions_table(self) -> str:
        """创建修订表"""
        
        url = f"{self.feishu.base_url}/bitable/v1/apps/{self.app_token}/tables"
        headers = await self.feishu._get_headers()
        
        data = {
            "table": {
                "name": "修订记录"
            }
        }
        
        response = await self.feishu.client.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("code") == 0:
            # 检查返回数据结构
            if "data" in result:
                if "table" in result["data"]:
                    table_id = result["data"]["table"]["table_id"]
                elif "table_id" in result["data"]:
                    table_id = result["data"]["table_id"]
                else:
                    print(f"   调试信息: {result}")
                    return None
            else:
                print(f"   调试信息: {result}")
                return None
            
            # 创建字段
            fields = [
                ("修订ID", 1),
                ("提议者", 1),
                ("课程", 3),
                ("修订类型", 3),
                ("修订内容", 1),
                ("修订理由", 1),
                ("状态", 3),
                ("审批人", 1),
                ("审批意见", 1),
                ("提交时间", 5),
                ("审批时间", 5),
            ]
            
            for field_name, field_type in fields:
                await self.feishu.create_bitable_field(
                    self.app_token, table_id, field_name, field_type
                )
            
            print(f"   ✅ 修订表创建完成（{len(fields)}个字段）")
            return table_id
        else:
            raise Exception(f"创建修订表失败: {result.get('msg')}")
    
    async def close(self):
        """关闭连接"""
        await self.feishu.close()


async def main():
    """主函数"""
    
    print("=" * 60)
    print("   创建PPE云端智能大礼包 - 飞书多维表格")
    print("=" * 60)
    
    manager = BitableManager()
    
    try:
        config = await manager.create_ppe_bitable()
        
        print("\n" + "=" * 60)
        print("   多维表格创建成功！")
        print("=" * 60)
        
        await manager.close()
        
    except Exception as e:
        print(f"\n创建失败: {e}")
        await manager.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
