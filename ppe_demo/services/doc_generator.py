# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 文档生成服务
生成飞书云文档并关联到知识库
"""

import os
import sys
import asyncio
import time
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import CourseDocument, save_json
from config import DATA_DIR, OUTPUT_DIR, COURSES_BY_YEAR
from services.feishu_service import FeishuService
from services.llm_service import LLMService
from services.upload_service import UploadService
from services.experience_service import ExperienceService


class DocGenerator:
    """课程文档生成器 - 飞书云文档版本"""

    def __init__(self, feishu: FeishuService, llm: LLMService):
        self.feishu = feishu
        self.llm = llm
        self.upload_service = UploadService()
        self.experience_service = ExperienceService()
        self.output_dir = OUTPUT_DIR / "course_docs"
        self.output_dir.mkdir(exist_ok=True)

    async def generate_course_doc(self, year: str, course_info: dict) -> str:
        """
        为某门课程生成飞书云文档

        Args:
            year: 学年（大一/大二/大三/大四）
            course_info: 课程信息（从config.py读取）

        Returns:
            生成的文档ID
        """
        course_name = course_info["name"]
        teacher = course_info.get("teacher", "")
        exam_type = course_info.get("exam", "闭卷")

        print(f"\n📝 生成课程文档: {course_name}（{teacher}）")

        # 1. 获取该课程的心得体会
        experiences = self.experience_service.get_experiences_by_course(course_name)
        print(f"  - 找到 {len(experiences)} 条心得体会")

        # 2. 获取该课程的资料
        materials = self.upload_service.get_materials_by_course(course_name)
        print(f"  - 找到 {len(materials)} 个资料")

        # 3. 调用LLM生成文档内容
        print(f"  - 调用AI生成文档内容...")
        doc_content = await self.llm.generate_course_doc(
            course_name, teacher, exam_type, experiences, materials
        )

        # 4. 创建飞书云文档
        print(f"  - 创建飞书云文档...")
        doc = await self.feishu.create_document(course_name)
        doc_id = doc["document_id"]
        print(f"    文档ID: {doc_id}")

        # 5. 构建文档块
        blocks = self._build_document_blocks(
            course_name, teacher, exam_type, doc_content, materials, experiences
        )

        # 6. 分批写入块内容（避免频率限制）
        print(f"  - 写入文档内容...")
        batch_size = 10  # 每批10个块
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i+batch_size]
            await self.feishu.create_blocks(doc_id, batch)
            if i + batch_size < len(blocks):
                await asyncio.sleep(0.5)  # 频率限制：每批间隔0.5秒

        # 7. 保存本地JSON备份
        course_doc = CourseDocument(
            course_name=course_name,
            teacher=teacher,
            exam_type=exam_type,
            overview=doc_content.get("overview", "暂无概述"),
            difficulties=doc_content.get("difficulties", []),
            teacher_preferences=doc_content.get("teacher_preferences", "暂无信息"),
            material_list=self._format_material_list(materials),
            material_guide=doc_content.get("material_guide", "暂无指导"),
            contributors=self._format_contributors(materials, experiences)
        )

        json_path = self.output_dir / f"{course_name}.json"
        save_json([course_doc.to_dict()], json_path)
        print(f"  ✅ JSON备份: {json_path}")

        return doc_id

    def _build_document_blocks(
        self,
        course_name: str,
        teacher: str,
        exam_type: str,
        doc_content: dict,
        materials: List[dict],
        experiences: List[dict]
    ) -> List[dict]:
        """构建飞书文档块结构

        V3文档结构：
        1. 课程内容概述
        2. 学习难点
        3. 老师偏好
        4. 资料分类列表
        5. 资料串讲
        6. 贡献者列表
        """
        blocks = []

        # 标题
        blocks.append(FeishuService.create_heading_block(course_name, level=1))
        blocks.append(FeishuService.create_text_block(f"授课老师：{teacher}  |  考试形式：{exam_type}"))
        blocks.append(FeishuService.create_divider_block())

        # 1. 课程内容概述
        blocks.append(FeishuService.create_heading_block("一、课程内容概述", level=2))
        overview = doc_content.get("overview", "暂无概述")
        # 分段处理
        for para in overview.split("\n\n"):
            if para.strip():
                blocks.append(FeishuService.create_text_block(para.strip()))
        blocks.append(FeishuService.create_divider_block())

        # 2. 学习难点
        blocks.append(FeishuService.create_heading_block("二、学习难点", level=2))
        difficulties = doc_content.get("difficulties", [])
        if difficulties:
            for i, diff in enumerate(difficulties, 1):
                blocks.append(FeishuService.create_text_block(f"{i}. {diff}"))
        else:
            blocks.append(FeishuService.create_text_block("暂无信息"))
        blocks.append(FeishuService.create_divider_block())

        # 3. 老师偏好
        blocks.append(FeishuService.create_heading_block("三、老师偏好", level=2))
        preferences = doc_content.get("teacher_preferences", "暂无信息")
        blocks.append(FeishuService.create_text_block(preferences))
        blocks.append(FeishuService.create_divider_block())

        # 4. 资料分类列表
        blocks.append(FeishuService.create_heading_block("四、资料分类列表", level=2))
        if materials:
            # 按类型分组
            material_by_type = {}
            for m in materials:
                m_type = m["material_type"]
                if m_type not in material_by_type:
                    material_by_type[m_type] = []
                material_by_type[m_type].append(m)

            for m_type, items in material_by_type.items():
                blocks.append(FeishuService.create_heading_block(f"【{m_type}】", level=3))
                for item in items:
                    name = item["standard_name"]
                    contributor = item["contributor"]
                    blocks.append(
                        FeishuService.create_text_block(f"• {name}（{contributor}推荐）")
                    )
        else:
            blocks.append(FeishuService.create_text_block("暂无资料"))
        blocks.append(FeishuService.create_divider_block())

        # 5. 资料串讲
        blocks.append(FeishuService.create_heading_block("五、资料串讲", level=2))
        guide = doc_content.get("material_guide", "暂无指导")
        for para in guide.split("\n\n"):
            if para.strip():
                blocks.append(FeishuService.create_text_block(para.strip()))
        blocks.append(FeishuService.create_divider_block())

        # 6. 贡献者列表
        blocks.append(FeishuService.create_heading_block("六、贡献者列表", level=2))
        contributors = self._format_contributors(materials, experiences)
        if contributors:
            for c in contributors:
                name = c["name"]
                grade = c["grade"]
                contributions = "；".join([
                    f"{item['type']}（{item['detail'][:30]}...）"
                    for item in c['contributions'][:2]
                ])
                blocks.append(
                    FeishuService.create_text_block(f"• **{name}**（{grade}）: {contributions}")
                )
        else:
            blocks.append(FeishuService.create_text_block("暂无贡献者"))

        # 页脚
        blocks.append(FeishuService.create_divider_block())
        blocks.append(
            FeishuService.create_text_block(
                f"本文档由PPE云端智能大礼包系统自动生成 · {datetime.now().strftime('%Y-%m-%d')}"
            )
        )

        return blocks

    def _format_material_list(self, materials: List[dict]) -> dict:
        """格式化资料列表（按类型分组）"""
        material_list = {}

        for m in materials:
            m_type = m["material_type"]
            if m_type not in material_list:
                material_list[m_type] = []

            material_list[m_type].append({
                "name": m["standard_name"],
                "contributor": m["contributor"],
                "recommendation": m["recommendation"]
            })

        return material_list

    def _format_contributors(self, materials: List[dict], experiences: List[dict]) -> List[dict]:
        """格式化贡献者列表"""
        contributors = {}

        # 统计资料上传
        for m in materials:
            name = m["contributor"]
            if name not in contributors:
                contributors[name] = {
                    "name": name,
                    "grade": m["grade"],
                    "contributions": []
                }

            contributors[name]["contributions"].append({
                "type": "资料上传",
                "detail": f"{m['material_type']}: {m['standard_name']}"
            })

        # 统计心得撰写
        for e in experiences:
            name = e["author"]
            if name not in contributors:
                contributors[name] = {
                    "name": name,
                    "grade": e["grade"],
                    "contributions": []
                }

            contributors[name]["contributions"].append({
                "type": "心得撰写",
                "detail": f"成绩 {e['score']} 分，分享了学习经验"
            })

        return list(contributors.values())

    async def generate_all_course_docs(self, limit: int = None) -> int:
        """生成所有课程的文档

        Args:
            limit: 限制生成数量（用于测试）

        Returns:
            成功生成的文档数量
        """
        print(f"\n🚀 开始生成课程文档...")
        success_count = 0
        total_count = 0

        for year, courses in COURSES_BY_YEAR.items():
            print(f"\n📚 {year}（{len(courses)}门课）:")

            for course in courses:
                if limit and total_count >= limit:
                    print(f"\n  ⚠️ 已达到限制数量 {limit}，停止生成")
                    return success_count

                total_count += 1
                try:
                    await self.generate_course_doc(year, course)
                    success_count += 1
                    await asyncio.sleep(1)  # 避免频率限制
                except Exception as e:
                    print(f"  ❌ {course['name']} 生成失败: {e}")

        print(f"\n✅ 文档生成完成！成功: {success_count}/{total_count}")
        return success_count
