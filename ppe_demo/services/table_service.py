# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 多维表格管理服务
负责创建学年多维表格、设置字段、添加课程记录
"""

import sys
import os
import json
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.feishu_service import FeishuService
from config import (
    WIKI_YEAR_NODES,
    COURSES_BY_YEAR,
    BITABLE_COURSE_FIELDS,
)


# 我们自定义定义的字段名，用于识别并删除飞书默认字段
CUSTOM_FIELD_NAMES = {f[0] for f in BITABLE_COURSE_FIELDS}


class TableService:
    """多维表格管理服务

    功能：
    - 在知识库学年节点下直接创建多维表格（obj_type: "bitable"）
    - 设置标准字段结构，删除飞书默认冗余字段
    - 批量添加课程记录，清理空行
    """

    def __init__(self, feishu: FeishuService):
        """初始化

        Args:
            feishu: FeishuService 实例
        """
        self.feishu = feishu
        # {学年: {"app_token": ..., "table_id": ..., "url": ...}}
        self.tables: Dict[str, dict] = {}

    async def create_all_tables(
        self,
        space_id: str = None,
        year_node_map: Dict[str, str] = None
    ) -> Dict[str, dict]:
        """为所有学年在知识库节点下创建多维表格

        Args:
            space_id: 知识空间ID（用于直接在wiki节点下创建bitable）
            year_node_map: {学年: node_token} 学年节点映射

        Returns:
            {学年: {"app_token": ..., "table_id": ..., "url": ...}}
        """
        print("📊 开始创建学年多维表格...")

        for year in WIKI_YEAR_NODES:
            try:
                parent_token = year_node_map.get(year) if year_node_map else None
                result = await self._create_year_table(year, space_id, parent_token)
                print(f"  ✅ [{year}] 创建成功: {result['url']}")
            except Exception as e:
                print(f"  ❌ [{year}] 创建失败: {e}")

        # 保存配置
        config_path = os.path.join(os.path.dirname(__file__), "..", "bitable_config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.tables, f, ensure_ascii=False, indent=2)
        print(f"  💾 配置已保存: {config_path}")

        return self.tables

    async def populate_all_tables(self, wiki_builder=None) -> None:
        """向所有学年表格添加课程记录，并清理空行

        Args:
            wiki_builder: WikiBuilder 实例（可选，用于自动关联文档链接）
        """
        print("\n📝 开始填充课程记录...")

        for year, courses in COURSES_BY_YEAR.items():
            if year not in self.tables:
                print(f"  ⚠️ [{year}] 无对应表格，跳过")
                continue

            table_info = self.tables[year]
            print(f"\n  📋 [{year}]（{len(courses)}门课）:")

            for course in courses:
                try:
                    # 构建学习指南链接
                    guide_url = ""
                    if wiki_builder:
                        guide_url = wiki_builder.get_doc_url(year, course["name"]) or ""

                    await self._add_course_record(
                        app_token=table_info["app_token"],
                        table_id=table_info["table_id"],
                        course=course,
                        guide_url=guide_url
                    )
                    print(f"    ✅ {course['name']}")
                except Exception as e:
                    print(f"    ❌ {course['name']}: {e}")

            # 清理空行
            await self._clean_empty_records(
                table_info["app_token"],
                table_info["table_id"]
            )

        print("\n✅ 课程记录填充完成!")

    async def update_guide_link(
        self,
        year: str,
        course_name: str,
        guide_url: str
    ) -> bool:
        """更新某门课程的学习指南链接

        Args:
            year: 学年
            course_name: 课程名称
            guide_url: 文档链接

        Returns:
            是否成功
        """
        if year not in self.tables:
            print(f"  ⚠️ [{year}] 无对应表格")
            return False

        table_info = self.tables[year]
        try:
            # 查找记录
            records = await self._find_record_by_name(
                table_info["app_token"],
                table_info["table_id"],
                course_name
            )
            if records:
                record_id = records[0]["record_id"]
                await self.feishu.update_bitable_record(
                    app_token=table_info["app_token"],
                    table_id=table_info["table_id"],
                    record_id=record_id,
                    fields={"学习指南": guide_url}
                )
                print(f"  ✅ [{year}] {course_name} 链接已更新")
                return True
        except Exception as e:
            print(f"  ❌ 更新失败: {e}")
        return False

    # ── 内部方法 ──

    async def _create_year_table(
        self,
        year: str,
        space_id: str = None,
        parent_node_token: str = None
    ) -> dict:
        """创建单个学年的多维表格

        优先在知识库节点下直接创建（obj_type: "bitable"），
        否则回退到独立创建。

        Args:
            year: 学年名称（如"大一"）
            space_id: 知识空间ID
            parent_node_token: 学年节点的node_token

        Returns:
            {"app_token": ..., "table_id": ..., "url": ...}
        """
        table_name = f"PPE{year}课程表"
        app_token = None
        table_id = None
        url = None

        # 尝试在知识库节点下直接创建bitable
        if space_id and parent_node_token:
            try:
                result = await self.feishu.create_wiki_node(
                    space_id=space_id,
                    title=table_name,
                    obj_type="bitable",
                    parent_node_token=parent_node_token
                )
                # wiki节点创建成功后，需要从返回数据中获取app_token和table_id
                node = result["data"]["node"]
                obj_token = node["obj_token"]
                # obj_token即为bitable的app_token
                app_token = obj_token

                # 获取默认table_id
                url = f"https://nkuyouth.feishu.cn/base/{app_token}"
                # 需要通过API获取默认table_id
                tables_url = f"{self.feishu.base_url}/bitable/v1/apps/{app_token}/tables"
                headers = await self.feishu._get_headers()
                response = await self.feishu.client.get(tables_url, headers=headers)
                tables_result = response.json()
                if tables_result.get("code") == 0:
                    tables = tables_result["data"].get("items", [])
                    if tables:
                        table_id = tables[0]["table_id"]
                    else:
                        raise Exception("无法获取默认table_id")
                else:
                    raise Exception(f"获取表格列表失败: {tables_result.get('msg')}")

                print(f"    📌 在知识库节点下直接创建成功")
            except Exception as e:
                print(f"    ⚠️ 知识库节点创建失败({e})，回退到独立创建...")
                app_token = None

        # 回退：独立创建
        if not app_token:
            result = await self.feishu.create_bitable(table_name)
            app_token = result["app"]["app_token"]
            table_id = result["app"]["default_table_id"]
            url = result["app"]["url"]

        # 删除飞书默认冗余字段
        await self._clean_default_fields(app_token, table_id)

        # 创建自定义字段
        for field_name, field_type in BITABLE_COURSE_FIELDS:
            try:
                await self.feishu.create_bitable_field(
                    app_token, table_id, field_name, field_type
                )
            except Exception:
                pass  # 字段可能已存在

        self.tables[year] = {
            "app_token": app_token,
            "table_id": table_id,
            "url": url
        }

        return self.tables[year]

    async def _clean_default_fields(self, app_token: str, table_id: str) -> None:
        """删除飞书默认创建的冗余字段，只保留我们定义的字段"""
        try:
            fields = await self.feishu.list_bitable_fields(app_token, table_id)
            deleted = 0
            for field in fields:
                field_name = field.get("field_name", "")
                # 跳过我们自定义的字段和系统保留字段
                if field_name in CUSTOM_FIELD_NAMES:
                    continue
                # 删除非自定义的默认字段
                try:
                    await self.feishu.delete_bitable_field(
                        app_token, table_id, field["field_id"]
                    )
                    deleted += 1
                    print(f"    🧹 删除默认字段: {field_name}")
                except Exception:
                    pass
            if deleted:
                print(f"    🧹 共删除 {deleted} 个默认字段")
        except Exception as e:
            print(f"    ⚠️ 清理默认字段时出错: {e}")

    async def _clean_empty_records(
        self,
        app_token: str,
        table_id: str
    ) -> None:
        """清理多维表格中的空记录（所有字段均为空或只有默认值的记录）"""
        try:
            records = await self.feishu.list_bitable_records(app_token, table_id, page_size=500)
            deleted = 0
            for record in records:
                fields = record.get("fields", {})
                # 检查所有字段值是否为空
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
                        await self.feishu.delete_bitable_record(
                            app_token, table_id, record["record_id"]
                        )
                        deleted += 1
                    except Exception:
                        pass

            if deleted:
                print(f"    🧹 清理了 {deleted} 条空记录")
        except Exception as e:
            print(f"    ⚠️ 清理空记录时出错: {e}")

    async def _add_course_record(
        self,
        app_token: str,
        table_id: str,
        course: dict,
        guide_url: str = ""
    ) -> dict:
        """向表格添加一条课程记录

        Args:
            app_token: 多维表格token
            table_id: 数据表ID
            course: 课程信息字典
            guide_url: 学习指南链接

        Returns:
            添加的记录
        """
        fields = {
            "课程名称": course["name"],
            "授课老师": course.get("teacher", ""),
            "开课学期": course.get("semester", ""),
            "课程类型": course.get("type", "必修"),
            "考试形式": course.get("exam", ""),
            "资料数量": 0,
            "贡献者": "",
        }

        if guide_url:
            fields["学习指南"] = guide_url

        return await self.feishu.add_bitable_record(
            app_token=app_token,
            table_id=table_id,
            fields=fields
        )

    async def _find_record_by_name(
        self,
        app_token: str,
        table_id: str,
        course_name: str
    ) -> list:
        """按课程名称查找记录

        Args:
            app_token: 多维表格token
            table_id: 数据表ID
            course_name: 课程名称

        Returns:
            匹配的记录列表
        """
        url = (
            f"{self.feishu.base_url}"
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        )
        headers = await self.feishu._get_headers()

        params = {
            "filter": json.dumps({
                "conditions": [
                    {
                        "field_name": "课程名称",
                        "operator": "is",
                        "value": [course_name]
                    }
                ]
            })
        }

        response = await self.feishu.client.get(url, headers=headers, params=params)
        result = response.json()

        if result.get("code") == 0:
            return result["data"]["items"]
        return []
