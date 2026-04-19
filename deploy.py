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
    python deploy.py --mode cleanup      # 清理空记录、冗余字段、空节点
    python deploy.py --mode sync          # 增量同步课程记录（不覆盖用户修改）

    环境变量：
        MATERIALS_BASE           资料包路径（绝对或相对于项目根目录）
        COURSE_REFORM_NOTES_DIR  课程教改笔记路径
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


async def deploy_tables(feishu: FeishuService, wiki: WikiBuilder = None, incremental: bool = True) -> dict:
    """部署多维表格

    Args:
        feishu: 飞书服务实例
        wiki: 知识库构建器（可选）
        incremental: 是否增量更新（默认True）
    """
    mode_str = "增量更新" if incremental else "全量覆盖"
    print(f"\n{'=' * 60}")
    print(f"   📊 步骤2: 创建多维表格（{mode_str}）")
    print("=" * 60)

    table_svc = TableService(feishu)
    space_id = wiki.space_id if wiki else None
    year_node_map = wiki.year_node_map if wiki else None
    result = await table_svc.create_all_tables(space_id=space_id, year_node_map=year_node_map)

    # 填充课程记录
    print(f"\n{'=' * 60}")
    print(f"   📝 步骤3: 填充课程记录（{mode_str}）")
    print("=" * 60)
    await table_svc.populate_all_tables(wiki_builder=wiki, incremental=incremental)

    return result


async def deploy_docs(feishu: FeishuService, wiki: WikiBuilder, limit: int = 1) -> int:
    """部署云文档"""
    print("\n" + "=" * 60)
    print("   📄 步骤4: 生成并上传课程文档")
    print("=" * 60)

    llm = LLMService()
    doc_gen = DocGenerator(feishu, llm)

    # 生成文档
    success_count = await doc_gen.generate_all_course_docs(limit=limit, wiki_builder=wiki)

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


async def deploy_sync():
    """增量同步课程记录（不覆盖用户手动修改的字段）"""
    print("=" * 60)
    print("   🔄 PPE云端智能大礼包 - 增量同步")
    print("=" * 60)

    feishu = FeishuService()

    try:
        # 加载已有的 wiki 结构
        wiki = WikiBuilder(feishu)
        wiki_loaded = wiki.load_from_local()

        table_svc = TableService(feishu)
        await table_svc.populate_all_tables(
            wiki_builder=wiki if wiki_loaded else None,
            incremental=True
        )

    finally:
        await feishu.close()


async def deploy_cleanup():
    """清理部署残留"""
    print("=" * 60)
    print("   🧹 PPE云端智能大礼包 - 清理模式")
    print("=" * 60)

    feishu = FeishuService()

    try:
        # 1. 清理多维表格空记录
        print("\n📋 清理多维表格空记录...")
        try:
            config_path = os.path.join(os.path.dirname(__file__), "ppe_demo", "bitable_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                tables = json.load(f)

            for year, table_info in tables.items():
                app_token = table_info.get("app_token")
                table_id = table_info.get("table_id")
                if not app_token or not table_id:
                    continue

                records = await feishu.list_bitable_records(app_token, table_id, page_size=500)
                deleted = 0
                for record in records:
                    fields = record.get("fields", {})
                    is_empty = True
                    for value in fields.values():
                        if isinstance(value, list):
                            if len(value) > 0 and value != [None]:
                                is_empty = False
                                break
                        elif value and value != 0:
                            is_empty = False
                            break
                    if is_empty:
                        try:
                            await feishu.delete_bitable_record(app_token, table_id, record["record_id"])
                            deleted += 1
                        except Exception:
                            pass
                if deleted:
                    print(f"  ✅ [{year}] 清理了 {deleted} 条空记录")
                else:
                    print(f"  ℹ️ [{year}] 无空记录")
        except FileNotFoundError:
            print("  ⚠️ 未找到 bitable_config.json，跳过表格清理")

        # 2. 清理知识库空节点
        print("\n📂 查找知识库空节点...")
        try:
            wiki = WikiBuilder(feishu)
            if not wiki.load_from_local():
                print("  ⚠️ 未找到本地知识库配置，跳过节点清理")
            else:
                nodes = await feishu.list_wiki_nodes(wiki.space_id)
                empty_nodes = []
                for node in nodes:
                    node_name = node.get("node_token", "")
                    title = node.get("title", "Untitled document")
                    if title == "" or title == "Untitled document":
                        empty_nodes.append(node)

                if empty_nodes:
                    print(f"  ⚠️ 发现 {len(empty_nodes)} 个空/未命名节点:")
                    for n in empty_nodes:
                        print(f"    - {n.get('node_token', '?')} ({n.get('title', 'Untitled document')})")
                    print("\n  ⚠️ 飞书API暂不支持删除知识库节点，请手动在客户端清理：")
                    print(f"     https://nkuyouth.feishu.cn/wiki/space/{wiki.space_id}")
                else:
                    print("  ✅ 无空/未命名节点")
        except Exception as e:
            print(f"  ⚠️ 查找节点失败: {e}")

        # 3. 清理默认冗余字段
        print("\n🔧 清理多维表格默认冗余字段...")
        try:
            config_path = os.path.join(os.path.dirname(__file__), "ppe_demo", "bitable_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                tables = json.load(f)

            from ppe_demo.config import BITABLE_COURSE_FIELDS
            custom_names = {f[0] for f in BITABLE_COURSE_FIELDS}

            for year, table_info in tables.items():
                app_token = table_info.get("app_token")
                table_id = table_info.get("table_id")
                if not app_token or not table_id:
                    continue

                fields = await feishu.list_bitable_fields(app_token, table_id)
                deleted = 0
                for field in fields:
                    fname = field.get("field_name", "")
                    if fname not in custom_names:
                        try:
                            await feishu.delete_bitable_field(app_token, table_id, field["field_id"])
                            deleted += 1
                        except Exception:
                            pass
                if deleted:
                    print(f"  ✅ [{year}] 清理了 {deleted} 个默认字段")
                else:
                    print(f"  ℹ️ [{year}] 无冗余字段")
        except FileNotFoundError:
            print("  ⚠️ 未找到 bitable_config.json，跳过字段清理")
        except Exception as e:
            print(f"  ⚠️ 字段清理失败: {e}")

        print("\n" + "=" * 60)
        print("   ✅ 清理完成！")
        print("=" * 60)

    finally:
        await feishu.close()


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

        # 2. 创建多维表格
        await deploy_tables(feishu, wiki)

        # 3. 生成文档（全量）
        await deploy_docs(feishu, wiki, limit=None)

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

        elif mode == "cleanup":
            await deploy_cleanup()

        elif mode == "sync":
            await deploy_sync()

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
        choices=["full", "wiki", "tables", "docs", "upload", "link", "cleanup", "sync"],
        default="full",
        help="部署模式"
    )

    args = parser.parse_args()

    # 运行部署
    asyncio.run(deploy_mode(args.mode))


if __name__ == "__main__":
    main()
