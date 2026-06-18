# -*- coding: utf-8 -*-
"""PPE云端智能大礼包 - 文档服务（课程文档：基本信息/课程概述/推荐资料/资料串讲/贡献者）"""

import asyncio
import re
import structlog
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from jinja2 import Environment, FileSystemLoader

from libs.feishu import FeishuAdapter
from libs.feishu import blocks as B
from libs.llm_adapter import LLMAdapter
from config.course_schema import CourseData, material_display_name

logger = structlog.get_logger()

_TEMPLATE_DIR = Path(__file__).parent.parent / "config" / "prompts"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))

_PLACEHOLDER_RE = re.compile(r'\[\[([^\]]+)\]\]')


def _parse_synthesis_to_runs(text: str, materials) -> List[Tuple[str, Optional[str]]]:
    """解析 LLM 输出的 material_synthesis，把 [[展示名]] 替换为 (展示名, file_link) text_run。

    其余纯文本段为 (text, None)。输出供 B.text_runs() 生成一个含多个 text_run 的段落 block，
    让资料名以可点击超链接形式嵌入串讲正文。
    """
    link_map = {material_display_name(m): m.file_link
                for m in materials if getattr(m, "file_link", "")}
    parts = _PLACEHOLDER_RE.split(text)
    runs: List[Tuple[str, Optional[str]]] = []
    for i, part in enumerate(parts):
        if not part:
            continue
        if i % 2 == 1:
            # 奇数索引：捕获组内容（占位符里的展示名）
            link = link_map.get(part)
            runs.append((part, link if link else None))
        else:
            # 偶数索引：普通文本段
            runs.append((part, None))
    return runs


def _course_doc_blocks(course: CourseData, sections: Dict[str, str]) -> List:
    """CourseData + LLM sections → Block 列表。

    结构（2026-06-19 用户重塑）：
      [text 授课老师|学期|考试] → [divider] →
      [h2 课程概述][text overview] →
      [h2 推荐资料][table [资料名称, Download]] →
      [h2 资料串讲][text_runs 多 run 含资料名超链接] →
      [h2 贡献者][table [贡献者, 贡献内容]]

    删了 H1（docx title 已是 "xxx 学习指南"）；三段（概述/难点/老师）融合为"课程概述"；
    资料表精简为 2 列（名称预改名 + Download 超链接）；推荐理由体现在"资料串讲"里。
    """
    bk = []
    bk.append(B.text(
        f"授课老师：{course.teacher or '未知'} | "
        f"开课学期：{course.semester or '未知'} | "
        f"考试形式：{course.exam or '未知'}"
    ))
    bk.append(B.divider())

    # 课程概述（融合三维度：基本内容 / 难点 / 老师风格）
    bk.append(B.heading("课程概述", 2))
    bk.append(B.text(sections.get("overview") or "（待完善）"))

    # 推荐资料（2 列：预改名后的资料名称 + Download 超链接）
    bk.append(B.heading("推荐资料", 2))
    if course.materials:
        headers = ["资料名称", "Download"]
        rows = []
        for m in course.materials:
            display = material_display_name(m)
            download_cell = ("Download", m.file_link) if m.file_link else "（暂无）"
            rows.append([display, download_cell])
        bk.append(B.table(headers, rows, header_row=True,
                         column_widths=[450, 120]))
    else:
        bk.append(B.text("（暂无收录资料）"))

    # 资料串讲（解析 [[占位符]] 为多 text_run，资料名嵌入超链接）
    bk.append(B.heading("资料串讲", 2))
    synthesis = sections.get("material_synthesis") or "（暂无串讲，欢迎贡献）"
    runs = _parse_synthesis_to_runs(synthesis, course.materials)
    bk.append(B.text_runs(runs))

    # 贡献者（原生表格，届别+姓名 完整署名）
    bk.append(B.heading("贡献者", 2))
    if course.contributors:
        contr_headers = ["贡献者", "贡献内容"]
        contr_rows = [[c.name, c.contribution or "资料与心得贡献"] for c in course.contributors]
        bk.append(B.table(contr_headers, contr_rows, header_row=True,
                         column_widths=[200, 600]))
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
        """LLM 生成课程指南（JSON mode：overview + material_synthesis）。

        预计算 materials_info 给模板：含展示名（用于 [[占位符]]）+ 完整贡献者署名（届别+姓名）。
        """
        tmpl = _jinja_env.get_template("course_guide_v3.j2")
        materials_info = []
        for m in course.materials:
            contributor_full = (m.contributor or "").strip()
            if "级" not in contributor_full and (m.grade or "").strip():
                contributor_full = f"{m.grade.strip()}{contributor_full}"
            if not contributor_full:
                contributor_full = "匿名"
            materials_info.append({
                "display_name": material_display_name(m),
                "contributor_full": contributor_full,
                "material_type": m.material_type or "资料",
                "recommendation_reason": m.recommendation_reason or "",
            })
        prompt = tmpl.render(course=course, materials_info=materials_info)
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
        # 写入混合块（普通 Block 用 append；BlockTree 表格用 descendant_tree）
        await self.feishu.write_mixed_blocks(doc_id, blocks, index=-1)
        logger.info("课程文档写入完成", course=course.name, doc_id=doc_id,
                    blocks=len(blocks))
        return doc_url

    async def replace_year_overview(self, obj_token: str, year: str, courses: List[CourseData]) -> None:
        """LLM 生成学年总论，替换学年文档里的旧总论块（准确覆写）。

        旧块识别：找 heading block（block_type=4，text 含「学年概述」），连同前置 divider + 后置 text 一并删除。
        未找到旧块时直接 append（首次创建场景）。确保重跑 docs 时不会追加第二份总论。
        """
        text = await self.generate_year_overview(year, courses)
        new_blocks = [B.divider(), B.heading("学年概述", 2), B.text(text)]

        top_blocks = await self.feishu.list_top_blocks(obj_token)
        heading_idx = None
        for i, blk in enumerate(top_blocks):
            if blk.get("block_type") != 4:
                continue
            text_data = blk.get("text") or {}
            elements = text_data.get("elements") or []
            content = "".join(e.get("text_run", {}).get("content", "") for e in elements)
            if "学年概述" in content:
                heading_idx = i
                break

        if heading_idx is not None and heading_idx > 0 and heading_idx + 1 < len(top_blocks):
            # 删除 [divider, heading, text] 三个连续块
            await self.feishu.delete_blocks(obj_token, heading_idx - 1, heading_idx + 2)
            logger.info("已删除旧学年总论块", year=year, start_idx=heading_idx - 1)

        await self.feishu.append_blocks(obj_token, new_blocks, index=9999)
        logger.info("学年总论替换完成", year=year)

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
