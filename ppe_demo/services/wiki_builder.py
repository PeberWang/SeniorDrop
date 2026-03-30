# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 知识库构建服务
负责创建飞书知识库空间、学年节点、课程节点
"""

import sys
import os
import json
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.feishu_service import FeishuService
from config import WIKI_SPACE_NAME, WIKI_YEAR_NODES, COURSES_BY_YEAR


class WikiBuilder:
    """飞书知识库自动构建器

    功能：
    - 创建或复用知识空间
    - 创建"大一/大二/大三/大四"四个学年节点
    - 在每个学年节点下为每门课创建子节点（docx类型）
    """

    def __init__(self, feishu: FeishuService):
        """初始化

        Args:
            feishu: FeishuService 实例
        """
        self.feishu = feishu
        self.space_id: Optional[str] = None
        # 节点映射：{(学年, 课程名): {"node_token": ..., "obj_token": ...}}
        self.node_map: Dict[tuple, dict] = {}
        # 学年根节点映射：{学年: node_token}
        self.year_node_map: Dict[str, str] = {}

    async def init_space(self, force_create: bool = False) -> str:
        """创建或获取知识空间

        Args:
            force_create: 是否强制创建新空间（即使同名空间已存在）

        Returns:
            space_id
        """
        if self.space_id:
            return self.space_id

        # 先尝试查找现有空间
        print(f"\n🔍 查找知识空间 '{WIKI_SPACE_NAME}'...")
        spaces = await self.feishu.list_wiki_spaces()

        for space in spaces:
            if space["name"] == WIKI_SPACE_NAME:
                if not force_create:
                    self.space_id = space["space_id"]
                    print(f"  ✅ 找到现有空间，复用: {self.space_id}")
                    return self.space_id
                else:
                    print(f"  ⚠️ 空间已存在，将创建新空间...")

        # 未找到或强制创建
        try:
            result = await self.feishu.create_wiki_space(WIKI_SPACE_NAME)
            self.space_id = result["space"]["space_id"]
            print(f"  ✅ 知识空间创建成功: {self.space_id}")
        except Exception as e:
            print(f"  ❌ 创建知识空间失败: {e}")
            raise

        return self.space_id

    async def build_year_nodes(self) -> Dict[str, str]:
        """创建学年根节点

        Returns:
            {学年名称: node_token} 字典
        """
        if not self.space_id:
            await self.init_space()

        print(f"\n📚 创建学年节点...")
        for year_name in WIKI_YEAR_NODES:
            try:
                result = await self.feishu.create_wiki_node(
                    space_id=self.space_id,
                    title=year_name,
                    obj_type="docx"
                )
                token = result["data"]["node"]["node_token"]
                obj_token = result["data"]["node"]["obj_token"]
                self.year_node_map[year_name] = token
                print(f"  ✅ [{year_name}]: {token}")
            except Exception as e:
                print(f"  ❌ 创建学年节点 [{year_name}] 失败: {e}")

        return self.year_node_map

    async def build_course_nodes(self) -> Dict[tuple, dict]:
        """为每个学年的每门课程创建知识库子节点

        Returns:
            {(学年, 课程名): {"node_token": ..., "obj_token": ...}} 字典
        """
        if not self.year_node_map:
            await self.build_year_nodes()

        print(f"\n📖 创建课程节点...")
        for year_name, courses in COURSES_BY_YEAR.items():
            parent_token = self.year_node_map.get(year_name)
            if not parent_token:
                print(f"  ⚠️ 学年 [{year_name}] 无根节点，跳过课程创建")
                continue

            print(f"\n  📁 {year_name}（{len(courses)}门课）:")
            for course in courses:
                course_name = course["name"]
                try:
                    result = await self.feishu.create_wiki_node(
                        space_id=self.space_id,
                        title=course_name,
                        obj_type="docx",
                        parent_node_token=parent_token
                    )
                    node_token = result["data"]["node"]["node_token"]
                    obj_token = result["data"]["node"]["obj_token"]
                    self.node_map[(year_name, course_name)] = {
                        "node_token": node_token,
                        "obj_token": obj_token
                    }
                    print(f"    ✅ {course_name}: {node_token}")
                except Exception as e:
                    print(f"    ❌ {course_name} 失败: {e}")

        return self.node_map

    async def build_all(self) -> dict:
        """一键构建完整知识库结构

        Returns:
            {"space_id": ..., "year_nodes": ..., "course_nodes": ...}
        """
        print("🏗️ 开始构建知识库结构...")

        await self.init_space()
        await self.build_year_nodes()
        await self.build_course_nodes()

        print(f"\n✅ 知识库构建完成!")
        print(f"   空间ID: {self.space_id}")
        print(f"   学年节点: {len(self.year_node_map)}")
        print(f"   课程节点: {len(self.node_map)}")

        result = {
            "space_id": self.space_id,
            "year_nodes": self.year_node_map,
            "course_nodes": {
                f"{k[0]}-{k[1]}": v for k, v in self.node_map.items()
            }
        }

        # 保存到本地
        output_path = os.path.join(os.path.dirname(__file__), "..", "wiki_structure.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"   结构已保存: {output_path}")

        return result

    def get_course_node(self, year: str, course_name: str) -> Optional[dict]:
        """获取课程节点信息

        Args:
            year: 学年（大一/大二/大三/大四）
            course_name: 课程名称

        Returns:
            {"node_token": ..., "obj_token": ...} 或 None
        """
        return self.node_map.get((year, course_name))

    def get_doc_url(self, year: str, course_name: str) -> Optional[str]:
        """生成课程文档的飞书链接

        Args:
            year: 学年
            course_name: 课程名称

        Returns:
            飞书文档URL 或 None
        """
        node_info = self.get_course_node(year, course_name)
        if node_info and self.space_id:
            return f"https://nkuyouth.feishu.cn/wiki/{node_info['node_token']}"
        return None

    def load_from_local(self) -> bool:
        """从本地加载已保存的结构

        Returns:
            是否成功加载
        """
        try:
            output_path = os.path.join(os.path.dirname(__file__), "..", "wiki_structure.json")
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.space_id = data.get("space_id")
            self.year_node_map = data.get("year_nodes", {})

            # 重建 node_map
            for key, value in data.get("course_nodes", {}).items():
                year, course_name = key.split("-", 1)
                self.node_map[(year, course_name)] = value

            print(f"✅ 从本地加载知识库结构成功")
            print(f"   空间ID: {self.space_id}")
            print(f"   课程节点: {len(self.node_map)}")
            return True
        except FileNotFoundError:
            print(f"⚠️ 本地未找到 wiki_structure.json")
            return False
        except Exception as e:
            print(f"❌ 加载本地结构失败: {e}")
            return False
