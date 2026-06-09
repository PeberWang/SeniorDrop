# -*- coding: utf-8 -*-
"""PPE云端智能大礼包 - 文档服务（6段课程文档：概述/难点/老师/资料/感悟/贡献者 + 学年总论）"""

import asyncio
import structlog
from pathlib import Path
from typing import Dict, List, Optional, Any

from jinja2 import Environment, FileSystemLoader

from libs.feishu import FeishuAdapter
from libs.feishu import blocks as B
from libs.llm_adapter import LLMAdapter
from config.course_schema import CourseData

logger = structlog.get_logger()

_TEMPLATE_DIR = Path(__file__).parent.parent / "config" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))


def _course_doc_blocks(course: CourseData, sections: Dict[str, str]) -> List:
    """CourseData + LLM sections → Block 列表（6段结构：概述/难点/老师/资料/感悟/贡献者）。"""
    bk = []
    bk.append(B.heading(f"{course.name} 学习指南", 1))
    bk.append(B.text(
        f"授课老师：{course.teacher or '未知'} | "
        f"开课学期：{course.semester or '未知'} | "
        f"考试形式：{course.exam or '未知'}"
    ))
    bk.append(B.divider())

    # Sections 1-3: LLM 基于心得生成
    bk.append(B.heading("课程内容概述", 2))
    bk.append(B.text(sections.get("overview") or "（待完善）"))

    bk.append(B.heading("学习难点与应对策略", 2))
    bk.append(B.text(sections.get("difficulty") or "（待完善）"))

    bk.append(B.heading("老师教学风格与偏好", 2))
    bk.append(B.text(sections.get("teacher_pref") or "（待同学补充）"))

    # Section 4: 推荐资料（原生表格，含 OSS/飞书下载链接）
    bk.append(B.heading("推荐资料", 2))
    if course.materials:
        material_headers = ["资料名称", "类型", "贡献者", "推荐理由", "下载"]
        material_rows = []
        for m in course.materials:
            link_text = m.file_link if m.file_link else "（暂无）"
            material_rows.append([
                m.name,
                m.material_type or "资料",
                m.contributor or "",
                m.recommendation_reason or "",
                link_text,
            ])
        bk.append(B.table(material_headers, material_rows, header_row=True,
                         column_widths=[200, 80, 100, 250, 250]))
    else:
        bk.append(B.text("（暂无收录资料）"))

    # Section 5: 学长学姐感悟（LLM 基于 reflections + materials 阐发）
    bk.append(B.heading("学长学姐感悟", 2))
    bk.append(B.text(sections.get("reflections_synthesis") or "（暂无感悟，欢迎分享你对这门课的理解）"))

    # Section 6: 贡献者（原生表格）
    bk.append(B.heading("贡献者", 2))
    if course.contributors:
        contr_headers = ["贡献者", "贡献内容"]
        contr_rows = [[c.name, c.contribution or "资料与心得贡献"] for c in course.contributors]
        bk.append(B.table(contr_headers, contr_rows, header_row=True,
                         column_widths=[150, 650]))
    else:
        bk.append(B.text("（本文档由 PPE 大礼包自动生成）"))

    return bk


class DocService:
    """文档服务"""

    def __init__(self, feishu: FeishuAdapter, llm: LLMAdapter):
        self.feishu = feishu
        self.llm = llm

    async def generate_year_overview(self, year: str, courses: List[CourseData]) -> str:
        """LLM 生成学年总论（plain text）。"""
        tmpl = _jinja_env.get_template("year_overview.j2")
        prompt = tmpl.render(year=year, courses=courses)
        return await self.llm.generate_completion(prompt=prompt, max_tokens=1500)

    async def generate_course_guide(self, course: CourseData) -> Dict[str, str]:
        """LLM 生成4字段课程指南（JSON mode：overview/difficulty/teacher_pref/reflections_synthesis）。"""
        tmpl = _jinja_env.get_template("course_guide_v3.j2")
        prompt = tmpl.render(course=course)
        return await self.llm.generate_with_json(prompt=prompt, max_tokens=4000)

    async def build_course_doc(self, course: CourseData, folder_token: str = "") -> str:
        """建独立 docx，写6段内容，返回 doc_url。"""
        doc_info = await self.feishu.create_docx(
            title=f"{course.name} 学习指南", folder_token=folder_token
        )
        doc_id = doc_info["doc_id"]
        doc_url = doc_info.get("url") or f"https://feishu.cn/docx/{doc_id}"

        try:
            sections = await self.generate_course_guide(course)
        except Exception as e:
            logger.warning("课程指南生成失败，使用占位内容", course=course.name, error=str(e))
            sections = {}

        blocks = _course_doc_blocks(course, sections)
        # 分离普通块（text/heading/divider）和表格块（block_type=31）
        # 表格必须通过 descendant API 创建，children API 不支持嵌套结构
        regular = [b for b in blocks if b.block_type != 31]
        table_blocks = [b for b in blocks if b.block_type == 31]
        idx = await self.feishu.append_blocks(doc_id, regular, index=0)
        for tb in table_blocks:
            idx = await self.feishu.create_descendant(doc_id, tb, index=idx)
        logger.info("课程文档写入完成", course=course.name, doc_id=doc_id,
                    blocks=len(regular), tables=len(table_blocks))
        return doc_url

    async def append_year_overview(self, obj_token: str, year: str, courses: List[CourseData]) -> None:
        """LLM 生成学年总论，追加到学年文档末尾（index=9999 自动追加到最后）。"""
        text = await self.generate_year_overview(year, courses)
        blocks = [B.divider(), B.heading("学年概述", 2), B.text(text)]
        await self.feishu.append_blocks(obj_token, blocks, index=9999)
        logger.info("学年总论追加完成", year=year)

    async def generate_all_course_guides(
        self,
        space_id: str = None,
        courses: List[CourseData] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """批量生成课程文档，返回 {results: [{course_name, url}], ...}。"""
        results, errors = [], []
        processed = 0
        for course in (courses or []):
            if limit and processed >= limit:
                break
            try:
                doc_url = await self.build_course_doc(course)
                results.append({"course_name": course.name, "url": doc_url})
                processed += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error("课程文档生成失败", course=course.name, error=str(e))
                errors.append({"course_name": course.name, "error": str(e)})

        return {
            "total_courses": len(courses or []),
            "processed": processed,
            "success_count": len(results),
            "error_count": len(errors),
            "results": results,
            "errors": errors,
        }
