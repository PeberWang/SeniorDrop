# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 多维表格管理服务
负责创建学年多维表格、设置字段、添加课程记录
支持增量更新：只新增/变更课程，保护用户手动编辑的字段
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
    PROTECTED_FIELDS,
)


# 我们自定义定义的字段名，用于识别并删除飞书默认字段
CUSTOM_FIELD_NAMES = {f[0] for f in BITABLE_COURSE_FIELDS}


class TableService:
    """多维表格管理服务

    功能：
    - 在知识库学年节点下直接创建多维表格（obj_type: "bitable"）
    - 设置标准字段结构，删除飞书默认冗余字段
    - 批量添加课程记录，清理空行
    - 增量更新：对比已有记录，只新增/变更，保护用户手动编辑的字段
    """

    def __init__(self, feishu: FeishuService):
        self.feishu = feishu
        # {学年: {"app_token": ..., "table_id": ..., "url": ...}}
        self.tables: Dict[str, dict] = {}

    def load_config(self) -> bool:
        """从 bitable_config.json 加载已有表格配置

        Returns:
            是否成功加载
        """
        config_path = os.path.join(os.path.dirname(__file__), "..", "bitable_config.json")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.tables = json.load(f)
            return bool(self.tables)
        except (FileNotFoundError, json.JSONDecodeError):
            return False

    async def create_all_tables(
        self,
        space_id: str = None,
        year_node_map: Dict[str, str] = None
    ) -> Dict[str, dict]:
        """为所有学年在知识库节点下创建多维表格

        如果表格已存在（bitable_config.json 中有记录），则跳过创建，
        仅补全缺失的学年表格。

        Args:
            space_id: 知识空间ID
            year_node_map: {学年: node_token} 学年节点映射

        Returns:
            {学年: {"app_token": ..., "table_id": ..., "url": ...}}
        """
        print("📊 开始创建学年多维表格...")

        # 先加载已有配置
        self.load_config()

        for year in WIKI_YEAR_NODES:
            # 跳过已存在的表格
            if year in self.tables:
                print(f"  ⏭️ [{year}] 表格已存在，跳过创建")
                continue

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

    async def populate_all_tables(self, wiki_builder=None, incremental: bool = True) -> None:
        """向所有学年表格添加课程记录

        Args:
            wiki_builder: WikiBuilder 实例（可选，用于自动关联文档链接）
            incremental: 是否增量更新（默认True）
                - True: 对比已有记录，只新增缺失课程，保护用户手动编辑字段
                - False: 全量覆盖（清空后重新添加）
        """
        mode_str = "增量" if incremental else "全量"
        print(f"\n📝 开始填充课程记录（{mode_str}模式）...")

        # 确保加载了表格配置
        if not self.tables:
            self.load_config()

        for year, courses in COURSES_BY_YEAR.items():
            if year not in self.tables:
                print(f"  ⚠️ [{year}] 无对应表格，跳过")
                continue

            table_info = self.tables[year]
            print(f"\n  📋 [{year}]（{len(courses)}门课）:")

            if incremental:
                await self._populate_incremental(table_info, courses, wiki_builder)
            else:
                await self._populate_full(table_info, courses, wiki_builder)

            # 清理空行
            await self._clean_empty_records(
                table_info["app_token"],
                table_info["table_id"]
            )

        print("\n✅ 课程记录填充完成!")

    async def _populate_incremental(
        self,
        table_info: dict,
        courses: list,
        wiki_builder=None
    ) -> None:
        """增量填充：只新增缺失课程，更新变更课程，保护用户手动编辑字段"""
        app_token = table_info["app_token"]
        table_id = table_info["table_id"]

        # 读取已有记录，构建 课程名称 -> record 映射
        existing_records = {}
        try:
            records = await self.feishu.list_bitable_records(app_token, table_id, page_size=500)
            for record in records:
                fields = record.get("fields", {})
                name_val = fields.get("课程名称", "")
                # 处理飞书多选/文本字段格式
                if isinstance(name_val, list) and name_val:
                    name_val = name_val[0].get("text", str(name_val[0])) if isinstance(name_val[0], dict) else str(name_val[0])
                elif isinstance(name_val, str):
                    pass
                else:
                    name_val = str(name_val) if name_val else ""
                if name_val:
                    existing_records[name_val] = record
        except Exception as e:
            print(f"    ⚠️ 读取已有记录失败，回退到全量模式: {e}")
            await self._populate_full(table_info, courses, wiki_builder)
            return

        # 识别需要新增和更新的课程
        existing_names = set(existing_records.keys())
        course_names = {c["name"] for c in courses}

        new_courses = [c for c in courses if c["name"] not in existing_names]
        # 更新：config 中有且表格中也有的课程（检查是否有字段变更）
        common_courses = [c for c in courses if c["name"] in existing_names]
        # 删除多余的：表格中有但 config 中没有的课程暂不处理（可能是用户手动添加的）

        # 新增课程
        for course in new_courses:
            try:
                guide_url = ""
                if wiki_builder:
                    guide_url = wiki_builder.get_doc_url(course.get("semester", "")[:2], course["name"]) or ""
                await self._add_course_record(
                    app_token=app_token,
                    table_id=table_id,
                    course=course,
                    guide_url=guide_url
                )
                print(f"    ➕ 新增: {course['name']}")
            except Exception as e:
                print(f"    ❌ 新增失败 {course['name']}: {e}")

        # 更新已有课程（仅更新非保护字段，且仅当值有变化时）
        updated_count = 0
        for course in common_courses:
            record = existing_records[course["name"]]
            record_id = record["record_id"]
            existing_fields = record.get("fields", {})

            # 构建更新字段（排除保护字段）
            update_fields = {}
            new_field_values = {
                "授课老师": course.get("teacher", ""),
                "开课学期": course.get("semester", ""),
                "课程类型": course.get("type", "必修"),
                "考试形式": course.get("exam", ""),
            }

            for field_name, new_value in new_field_values.items():
                if field_name in PROTECTED_FIELDS:
                    continue
                old_value = existing_fields.get(field_name, "")
                # 标准化比较
                old_str = self._field_to_str(old_value)
                if old_str != new_value:
                    update_fields[field_name] = new_value

            # 更新学习指南链接（如果之前没有）
            if not existing_fields.get("学习指南") and wiki_builder:
                guide_url = wiki_builder.get_doc_url(course.get("semester", "")[:2], course["name"]) or ""
                if guide_url:
                    update_fields["学习指南"] = guide_url

            if update_fields:
                try:
                    await self.feishu.update_bitable_record(
                        app_token=app_token,
                        table_id=table_id,
                        record_id=record_id,
                        fields=update_fields
                    )
                    updated_count += 1
                    print(f"    🔄 更新: {course['name']}（{', '.join(update_fields.keys())}）")
                except Exception as e:
                    print(f"    ❌ 更新失败 {course['name']}: {e}")

        if not new_courses and updated_count == 0:
            print(f"    ✅ 无变化，所有课程已是最新")

    async def _populate_full(
        self,
        table_info: dict,
        courses: list,
        wiki_builder=None
    ) -> None:
        """全量填充：清空后重新添加所有课程"""
        app_token = table_info["app_token"]
        table_id = table_info["table_id"]

        for course in courses:
            try:
                guide_url = ""
                if wiki_builder:
                    guide_url = wiki_builder.get_doc_url(course.get("semester", "")[:2], course["name"]) or ""
                await self._add_course_record(
                    app_token=app_token,
                    table_id=table_id,
                    course=course,
                    guide_url=guide_url
                )
                print(f"    ✅ {course['name']}")
            except Exception as e:
                print(f"    ❌ {course['name']}: {e}")

    @staticmethod
    def _field_to_str(value) -> str:
        """将飞书字段值转为字符串用于比较"""
        if isinstance(value, list):
            if not value:
                return ""
            if isinstance(value[0], dict):
                return value[0].get("text", str(value[0]))
            return str(value[0])
        if value is None:
            return ""
        return str(value)

    async def update_guide_link(
        self,
        year: str,
        course_name: str,
        guide_url: str
    ) -> bool:
        """更新某门课程的学习指南链接"""
        if year not in self.tables:
            print(f"  ⚠️ [{year}] 无对应表格")
            return False

        table_info = self.tables[year]
        try:
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
        """创建单个学年的多维表格"""
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
                node = result["data"]["node"]
                obj_token = node["obj_token"]
                app_token = obj_token

                url = f"https://nkuyouth.feishu.cn/base/{app_token}"
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
                if field_name in CUSTOM_FIELD_NAMES:
                    continue
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
        """向表格添加一条课程记录"""
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
        """按课程名称查找记录"""
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
