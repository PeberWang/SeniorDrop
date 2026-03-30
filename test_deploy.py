# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 测试部署脚本
用于验证核心功能
"""
import sys
import os
import asyncio

# 添加 ppe_demo 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ppe_demo"))

from ppe_demo.services.feishu_service import FeishuService


async def test_list_spaces():
    """测试列出知识空间"""
    print("\n[TEST] 列出知识空间...")
    feishu = FeishuService()

    try:
        spaces = await feishu.list_wiki_spaces()
        print(f"[OK] 找到 {len(spaces)} 个知识空间:")
        for space in spaces:
            print(f"  - {space['name']}: {space['space_id']}")
        return spaces
    except Exception as e:
        print(f"[ERROR] {e}")
        return []
    finally:
        await feishu.close()


async def test_create_doc():
    """测试创建云文档"""
    print("\n[TEST] 创建云文档...")
    feishu = FeishuService()

    try:
        # 创建文档
        doc = await feishu.create_document("测试文档-PPE大礼包")
        doc_id = doc["document_id"]
        print(f"[OK] 文档创建成功: {doc_id}")

        # 写入内容
        blocks = [
            FeishuService.create_heading_block("测试标题", level=1),
            FeishuService.create_text_block("这是一段测试文本。"),
            FeishuService.create_divider_block(),
            FeishuService.create_heading_block("列表测试", level=2),
        ]
        blocks.extend(FeishuService.create_bullet_list_block(["项目1", "项目2", "项目3"]))

        await feishu.create_blocks(doc_id, blocks)
        print(f"[OK] 内容写入成功")

        # 返回文档ID
        return doc_id
    except Exception as e:
        print(f"[ERROR] {e}")
        return None
    finally:
        await feishu.close()


async def main():
    print("=" * 60)
    print("   PPE云端智能大礼包 - 核心功能测试")
    print("=" * 60)

    # 测试1: 列出知识空间
    spaces = await test_list_spaces()

    # 测试2: 创建云文档
    doc_id = await test_create_doc()

    print("\n" + "=" * 60)
    print("   测试完成")
    print("=" * 60)

    if spaces and doc_id:
        print("\n[OK] 核心功能测试通过！")
        print(f"\n[INFO] 文档访问链接:")
        print(f"  https://nkuyouth.feishu.cn/docx/{doc_id}")
        print("\n[NEXT] 可以运行完整部署:")
        print("  python deploy.py --mode full")
    else:
        print("\n[WARN] 部分测试失败，请检查日志")


if __name__ == "__main__":
    asyncio.run(main())
