# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 统一部署入口
一键部署知识库、多维表格、云文档、资料上传

用法：
    python deploy.py --mode full          # 完整部署（知识库+表格+文档+资料）
    python deploy.py --mode wiki          # 仅创建知识库结构
    python deploy.py --mode tables        # 仅创建多维表格
    python deploy.py --mode docs          # 仅生成并上传文档
    python deploy.py --mode upload        # 仅上传资料
    python deploy.py --mode link          # 仅关联表格与文档链接
"""

import sys
import os
import argparse
import asyncio

# 添加 ppe_demo 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ppe_demo"))

from ppe_demo.services.feishu_service import FeishuService
from ppe_demo.services.wiki_builder import WikiBuilder
from ppe_demo.services.table_service import TableService
from ppe_demo.services.doc_generator import DocGenerator
from ppe_demo.services.link_service import LinkService
from ppe_demo.services.llm_service import LLMService


async def deploy_wiki(feishu: FeishuService) -> dict:
    """部署知识库结构"""
    print("\n" + "=" * 60)
    print("   📚 步骤1: 构建知识库结构")
    print("=" * 60)

    wiki = WikiBuilder(feishu)
    result = await wiki.build_all()
    return result


async def deploy_tables(feishu: FeishuService, wiki: WikiBuilder = None) -> dict:
    """部署多维表格"""
    print("\n" + "=" * 60)
    print("   📊 步骤2: 创建多维表格")
    print("=" * 60)

    table_svc = TableService(feishu)
    result = await table_svc.create_all_tables()

    # 填充课程记录
    print("\n" + "=" * 60)
    print("   📝 步骤3: 填充课程记录")
    print("=" * 60)
    await table_svc.populate_all_tables(wiki_builder=wiki)

    return result


async def deploy_docs(feishu: FeishuService, wiki: WikiBuilder, limit: int = 1) -> int:
    """部署云文档"""
    print("\n" + "=" * 60)
    print("   📄 步骤4: 生成并上传课程文档")
    print("=" * 60)

    llm = LLMService()
    doc_gen = DocGenerator(feishu, llm)

    # 生成文档
    success_count = await doc_gen.generate_all_course_docs(limit=limit)

    await llm.close()
    return success_count


async def deploy_upload(feishu: FeishuService) -> dict:
    """上传资料到飞书云空间"""
    print("\n" + "=" * 60)
    print("   📎 步骤5: 上传资料到飞书")
    print("=" * 60)

    print("⚠️ 当前 materials.json 为空，跳过资料上传")
    print("   如需上传真实资料，请先填充 materials.json")
    return {}


async def deploy_link(feishu: FeishuService, wiki: WikiBuilder) -> int:
    """关联表格与文档"""
    print("\n" + "=" * 60)
    print("   🔗 步骤6: 关联表格与文档")
    print("=" * 60)

    link_svc = LinkService(feishu, wiki)
    success_count = await link_svc.link_all_courses()
    return success_count


async def deploy_full():
    """完整部署流程"""
    print("=" * 60)
    print("   🚀 PPE云端智能大礼包 - 完整部署")
    print("=" * 60)

    feishu = FeishuService()

    try:
        # 1. 构建知识库
        wiki_result = await deploy_wiki(feishu)
        wiki = WikiBuilder(feishu)
        wiki.space_id = wiki_result["space_id"]
        wiki.year_node_map = wiki_result["year_nodes"]
        for key, value in wiki_result["course_nodes"].items():
            year, course = key.split("-", 1)
            wiki.node_map[(year, course)] = value

        # 2. 创建多维表格
        await deploy_tables(feishu, wiki)

        # 3. 生成文档（先只生成1门课程用于演示）
        await deploy_docs(feishu, wiki, limit=1)

        # 4. 上传资料（跳过，因为无真实资料）
        await deploy_upload(feishu)

        # 5. 关联链接
        await deploy_link(feishu, wiki)

        print("\n" + "=" * 60)
        print("   ✅ 完整部署完成！")
        print("=" * 60)
        print("\n📋 部署结果:")
        print(f"  - 知识空间ID: {wiki.space_id}")
        print(f"  - 学年节点: {len(wiki.year_node_map)}")
        print(f"  - 课程节点: {len(wiki.node_map)}")
        print(f"\n🌐 访问链接:")
        print(f"  - 知识库: https://nkuyouth.feishu.cn/wiki/space/{wiki.space_id}")

    except Exception as e:
        print(f"\n❌ 部署失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await feishu.close()


async def deploy_mode(mode: str):
    """按模式部署"""
    feishu = FeishuService()

    try:
        if mode == "wiki":
            await deploy_wiki(feishu)

        elif mode == "tables":
            await deploy_tables(feishu)

        elif mode == "docs":
            wiki = WikiBuilder(feishu)
            if not wiki.load_from_local():
                print("❌ 请先运行 --mode wiki 创建知识库结构")
                return
            await deploy_docs(feishu, wiki, limit=1)

        elif mode == "upload":
            await deploy_upload(feishu)

        elif mode == "link":
            wiki = WikiBuilder(feishu)
            if not wiki.load_from_local():
                print("❌ 请先运行 --mode wiki 创建知识库结构")
                return
            await deploy_link(feishu, wiki)

        elif mode == "full":
            await deploy_full()

    finally:
        await feishu.close()


def main():
    parser = argparse.ArgumentParser(
        description="PPE云端智能大礼包 - 统一部署工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python deploy.py --mode full          # 完整部署
    python deploy.py --mode wiki          # 仅创建知识库
    python deploy.py --mode docs          # 仅生成文档（需要先创建wiki）
    python deploy.py --mode link          # 仅关联链接（需要先创建wiki和tables）
        """
    )

    parser.add_argument(
        "--mode",
        choices=["full", "wiki", "tables", "docs", "upload", "link"],
        default="full",
        help="部署模式"
    )

    args = parser.parse_args()

    # 运行部署
    asyncio.run(deploy_mode(args.mode))


if __name__ == "__main__":
    main()
