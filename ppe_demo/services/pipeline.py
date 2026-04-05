# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 主流水线
串联知识库构建、多维表格创建、文档生成等模块
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.feishu_service import FeishuService
from services.wiki_builder import WikiBuilder
from services.table_service import TableService


async def run_full_pipeline():
    """运行完整的构建流水线

    流程：
    1. 初始化飞书服务
    2. 构建知识库结构（空间→学年节点→课程节点）
    3. 创建多维表格（大一/大二/大三/大四）
    4. 填充课程记录并关联文档链接
    """
    print("=" * 60)
    print("   PPE云端智能大礼包 - 知识库构建流水线")
    print("=" * 60)

    feishu = FeishuService()

    try:
        # ── Step 1: 构建知识库（仅空间+学年节点） ──
        print("\n📚 Step 1: 构建知识库结构")
        print("-" * 40)
        wiki = WikiBuilder(feishu)
        await wiki.init_space()
        await wiki.build_year_nodes()

        # ── Step 2: 创建多维表格（直接在知识库节点下） ──
        print("\n📊 Step 2: 创建学年多维表格")
        print("-" * 40)
        table_svc = TableService(feishu)
        await table_svc.create_all_tables(
            space_id=wiki.space_id,
            year_node_map=wiki.year_node_map
        )

        # ── Step 3: 填充课程记录 ──
        print("\n📝 Step 3: 填充课程记录")
        print("-" * 40)
        await table_svc.populate_all_tables(wiki_builder=wiki)

        print("\n" + "=" * 60)
        print("   ✅ 流水线执行完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 流水线执行失败: {e}")
        raise
    finally:
        await feishu.close()


async def run_wiki_only():
    """仅构建知识库结构"""
    print("📚 仅构建知识库...")
    feishu = FeishuService()
    try:
        wiki = WikiBuilder(feishu)
        await wiki.build_all()
    finally:
        await feishu.close()


async def run_tables_only():
    """仅创建多维表格"""
    print("📊 仅创建多维表格...")
    feishu = FeishuService()
    try:
        table_svc = TableService(feishu)
        await table_svc.create_all_tables()
        await table_svc.populate_all_tables()
    finally:
        await feishu.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PPE云端智能大礼包 - 构建流水线")
    parser.add_argument(
        "--mode", choices=["all", "wiki", "tables"],
        default="all",
        help="运行模式：all=完整流水线, wiki=仅知识库, tables=仅多维表格"
    )
    args = parser.parse_args()

    if args.mode == "all":
        asyncio.run(run_full_pipeline())
    elif args.mode == "wiki":
        asyncio.run(run_wiki_only())
    elif args.mode == "tables":
        asyncio.run(run_tables_only())
