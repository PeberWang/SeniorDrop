# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 关联服务
负责打通多维表格与知识库的链接
"""

import sys
import os
import json
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.feishu_service import FeishuService
from services.wiki_builder import WikiBuilder


class LinkService:
    """关联服务 - 打通多维表格与知识库

    功能：
    - 更新多维表格中"学习指南"字段为wiki URL
    - 批量关联所有课程的文档链接
    """

    def __init__(self, feishu: FeishuService, wiki: WikiBuilder):
        """初始化

        Args:
            feishu: FeishuService 实例
            wiki: WikiBuilder 实例
        """
        self.feishu = feishu
        self.wiki = wiki
        self.bitable_config: Dict[str, dict] = {}

    def load_bitable_config(self) -> bool:
        """从本地加载多维表格配置

        Returns:
            是否成功加载
        """
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "bitable_config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                self.bitable_config = json.load(f)
            print(f"✅ 加载多维表格配置成功")
            return True
        except FileNotFoundError:
            print(f"⚠️ 未找到 bitable_config.json")
            return False
        except Exception as e:
            print(f"❌ 加载配置失败: {e}")
            return False

    async def link_all_courses(self) -> int:
        """为所有课程关联文档链接

        Returns:
            成功关联的数量
        """
        if not self.bitable_config:
            self.load_bitable_config()

        if not self.wiki.space_id:
            if not self.wiki.load_from_local():
                print("❌ 请先构建知识库结构")
                return 0

        print("\n🔗 开始关联课程文档链接...")
        success_count = 0

        for year, table_info in self.bitable_config.items():
            app_token = table_info.get("app_token")
            table_id = table_info.get("table_id")

            if not app_token or not table_id:
                print(f"  ⚠️ [{year}] 缺少表格信息，跳过")
                continue

            print(f"\n  📋 [{year}]:")

            # 获取该学年所有课程记录
            try:
                records = await self.feishu.list_bitable_records(app_token, table_id)
            except Exception as e:
                print(f"    ❌ 获取记录失败: {e}")
                continue

            for record in records:
                record_id = record["record_id"]
                fields = record["fields"]
                course_name = fields.get("课程名称", "")

                if not course_name:
                    continue

                # 获取文档链接
                doc_url = self.wiki.get_doc_url(year, course_name)
                if not doc_url:
                    print(f"    ⚠️ {course_name} 无对应文档")
                    continue

                # 更新记录
                try:
                    await self.feishu.update_bitable_record(
                        app_token=app_token,
                        table_id=table_id,
                        record_id=record_id,
                        fields={"学习指南": doc_url}
                    )
                    print(f"    ✅ {course_name}")
                    success_count += 1
                except Exception as e:
                    print(f"    ❌ {course_name} 更新失败: {e}")

        print(f"\n✅ 关联完成！成功: {success_count}")
        return success_count

    async def link_single_course(
        self,
        year: str,
        course_name: str,
        doc_url: str
    ) -> bool:
        """关联单个课程的文档链接

        Args:
            year: 学年
            course_name: 课程名称
            doc_url: 文档URL

        Returns:
            是否成功
        """
        if not self.bitable_config:
            self.load_bitable_config()

        table_info = self.bitable_config.get(year)
        if not table_info:
            print(f"⚠️ 未找到 [{year}] 的表格配置")
            return False

        app_token = table_info["app_token"]
        table_id = table_info["table_id"]

        try:
            # 查找记录
            records = await self.feishu.list_bitable_records(app_token, table_id)
            record = None
            for r in records:
                if r["fields"].get("课程名称") == course_name:
                    record = r
                    break

            if not record:
                print(f"⚠️ 未找到课程 [{course_name}] 的记录")
                return False

            # 更新链接
            await self.feishu.update_bitable_record(
                app_token=app_token,
                table_id=table_id,
                record_id=record["record_id"],
                fields={"学习指南": doc_url}
            )
            print(f"✅ [{year}] {course_name} 链接已更新")
            return True

        except Exception as e:
            print(f"❌ 更新失败: {e}")
            return False
