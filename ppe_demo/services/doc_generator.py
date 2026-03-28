# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 文档生成服务
"""

import os
import sys
from datetime import datetime
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import CourseDocument, save_json
from config import DATA_DIR, OUTPUT_DIR
from services.llm_service import LLMService
from services.upload_service import UploadService
from services.experience_service import ExperienceService


class DocGenerator:
    """课程文档生成器"""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.upload_service = UploadService()
        self.experience_service = ExperienceService()
        self.output_dir = OUTPUT_DIR / "course_docs"
        self.output_dir.mkdir(exist_ok=True)
    
    async def generate_course_doc(self, course_info: dict) -> str:
        """
        为某门课程生成完整文档
        
        Args:
            course_info: 课程信息（从courses.json读取）
        
        Returns:
            生成的文档路径
        """
        course_name = course_info["course_name"]
        teacher = course_info["teacher"]
        exam_type = course_info.get("exam_type", "闭卷")
        
        print(f"\n📝 生成课程文档: {course_name}（{teacher}）")
        
        # 1. 获取该课程的心得体会
        experiences = self.experience_service.get_experiences_by_course(course_name)
        print(f"  - 找到 {len(experiences)} 条心得体会")
        
        # 2. 获取该课程的资料
        materials = self.upload_service.get_materials_by_course(course_name)
        print(f"  - 找到 {len(materials)} 个资料")
        
        # 3. 调用LLM生成文档内容
        print(f"  - 调用AI生成文档...")
        doc_content = await self.llm_service.generate_course_doc(
            course_name, teacher, exam_type, experiences, materials
        )
        
        # 4. 构建课程文档对象
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
        
        # 5. 保存为JSON
        json_path = self.output_dir / f"{course_name}.json"
        save_json([course_doc.to_dict()], json_path)
        print(f"  ✅ JSON已保存: {json_path}")
        
        # 6. 生成Markdown文档
        md_content = self._generate_markdown(course_doc)
        md_path = self.output_dir / f"{course_name}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"  ✅ Markdown已保存: {md_path}")
        
        return str(md_path)
    
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
    
    def _generate_markdown(self, doc: CourseDocument) -> str:
        """生成Markdown格式的课程文档"""
        
        # 生成资料列表
        material_sections = []
        for m_type, items in doc.material_list.items():
            items_text = "\n".join([
                f"  - {item['name']}（{item['contributor']}推荐：{item['recommendation'][:30]}...）"
                for item in items
            ])
            material_sections.append(f"**{m_type}**：\n{items_text}")
        
        materials_text = "\n\n".join(material_sections) if material_sections else "暂无资料"
        
        # 生成贡献者表格
        contributor_rows = ["| 贡献者 | 年级 | 贡献 |", "|--------|------|------|"]
        for c in doc.contributors:
            contributions = "；".join([f"{item['type']}（{item['detail'][:20]}...）" for item in c['contributions'][:2]])
            contributor_rows.append(f"| {c['name']} | {c['grade']} | {contributions} |")
        
        contributors_table = "\n".join(contributor_rows) if len(doc.contributors) > 0 else "暂无贡献者"
        
        # 生成完整文档
        md = f"""# {doc.course_name}

**授课老师**：{doc.teacher}  
**考试形式**：{doc.exam_type}  
**生成时间**：{doc.generated_time}

---

## 一、课程内容概述

{doc.overview}

---

## 二、学习难点

{self._format_list(doc.difficulties)}

---

## 三、老师偏好

{doc.teacher_preferences}

---

## 四、资料分类列表

{materials_text}

---

## 五、资料串讲

{doc.material_guide}

---

## 六、贡献者列表

{contributors_table}

---

*本文档由PPE云端智能大礼包系统自动生成*
"""
        
        return md
    
    def _format_list(self, items: List[str]) -> str:
        """格式化列表"""
        if not items:
            return "暂无信息"
        return "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])
    
    async def generate_all_course_docs(self, courses: List[dict]):
        """生成所有课程的文档"""
        print(f"\n🚀 开始生成 {len(courses)} 门课程的文档...")
        
        for i, course in enumerate(courses, 1):
            print(f"\n[{i}/{len(courses)}]", end="")
            await self.generate_course_doc(course)
        
        print(f"\n\n✅ 所有课程文档生成完成！")
        print(f"📁 保存位置: {self.output_dir}")
        
        await self.llm_service.close()
