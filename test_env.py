# -*- coding: utf-8 -*-
"""
测试环境配置和基础功能
"""
import sys
import os
import asyncio

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ppe_demo"))

from ppe_demo.config import FEISHU_APP_ID, FEISHU_APP_SECRET, ZHIPU_API_KEY
from ppe_demo.services.feishu_service import FeishuService


async def test_auth():
    """测试飞书认证"""
    print("\n🧪 测试飞书认证...")
    feishu = FeishuService()

    try:
        token = await feishu.get_tenant_access_token()
        print(f"✅ Token获取成功: {token[:20]}...")
        return True
    except Exception as e:
        print(f"❌ Token获取失败: {e}")
        return False
    finally:
        await feishu.close()


def main():
    print("=" * 60)
    print("   PPE云端智能大礼包 - 环境测试")
    print("=" * 60)

    # 检查环境变量
    print("\n📋 检查环境变量:")
    print(f"  FEISHU_APP_ID: {'✅' if FEISHU_APP_ID else '❌'} {FEISHU_APP_ID[:10] if FEISHU_APP_ID else '未配置'}...")
    print(f"  FEISHU_APP_SECRET: {'✅' if FEISHU_APP_SECRET else '❌'} {'*' * 10 if FEISHU_APP_SECRET else '未配置'}")
    print(f"  ZHIPU_API_KEY: {'✅' if ZHIPU_API_KEY else '❌'} {ZHIPU_API_KEY[:10] if ZHIPU_API_KEY else '未配置'}...")

    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("\n❌ 缺少必要的环境变量，请检查 .env 文件")
        return

    # 测试认证
    success = asyncio.run(test_auth())

    if success:
        print("\n✅ 环境配置正常！可以开始部署。")
        print("\n💡 运行命令开始部署:")
        print("   python deploy.py --mode full")
    else:
        print("\n❌ 环境配置有问题，请检查飞书应用配置")


if __name__ == "__main__":
    main()
