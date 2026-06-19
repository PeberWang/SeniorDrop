# -*- coding: utf-8 -*-
"""
课程数据服务 — 从飞书 bitable 三张表实时聚合 CourseData。

bitable 是唯一真相源，本地不再持久化课程数据。
三层聚合：
    1. 课程主数据表（基本字段：name/teacher/semester/type/exam）
    2. 资料管理表（审核通过的资料 → materials[]）
    3. 心得管理表（审核通过的心得 → insights[]）

符合架构规范：只调用 libs/ 层（FeishuAdapter），不直接依赖第三方 SDK。
"""

from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple

from libs.feishu import FeishuAdapter
from config.course_schema import (
    CourseData, Material, Insight, Contributor, WIKI_YEAR_NODES,
)
from config.settings import Settings

COURSE_TABLE_NAME = "课程主数据表"
MATERIALS_TABLE_NAME = "资料管理表"
INSIGHTS_TABLE_NAME = "心得管理表"


def _select_text(field_val: Any) -> str:
    """飞书单选/富文本字段值归一化为 str。

    可能形态：str / [{"text": "xx"}] / [{"name": "xx"}] / None
    """
    if not field_val:
        return ""
    if isinstance(field_val, str):
        return field_val
    if isinstance(field_val, list) and field_val:
        first = field_val[0]
        if isinstance(first, dict):
            return first.get("text") or first.get("name") or ""
        return str(first)
    return str(field_val)


def _extract_course_name(course_field: Any) -> str:
    """资料表/心得表「课程」字段（单选/关联）→ str。"""
    return _select_text(course_field)


def _derive_year(semester: str) -> str:
    """从「开课学期」前两字派生学年（'大一上' → '大一'）。"""
    return semester[:2] if len(semester) >= 2 else ""


class CourseDataService:
    """课程数据读取服务 — 从 bitable 三张表实时聚合。"""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def get_by_year(self, year: str, app_token: str) -> List[CourseData]:
        """读取某学年课程列表（运行时聚合 materials/insights/contributors）。"""
        all_courses = await self.get_all(app_token)
        return [c for c in all_courses if _derive_year(c.semester) == year]

    async def get_all(self, app_token: str) -> List[CourseData]:
        """读取全部课程（聚合三张表）。"""
        feishu = FeishuAdapter(self.settings)
        try:
            table_ids = await self._resolve_table_ids(feishu, app_token)
            if not table_ids.get("course"):
                return []

            # 1. 课程主数据表 → 基本字段
            course_records = await feishu.list_bitable_records(
                app_token, table_ids["course"]
            )
            courses: Dict[str, CourseData] = {}
            for r in course_records:
                f = r.get("fields") or {}
                name = (f.get("课程名称") or "").strip() if isinstance(f.get("课程名称"), str) \
                    else _select_text(f.get("课程名称"))
                if not name:
                    continue
                courses[name] = CourseData(
                    name=name,
                    teacher=_select_text(f.get("授课老师")),
                    semester=_select_text(f.get("开课学期")),
                    type=_select_text(f.get("课程类型")),
                    exam=_select_text(f.get("考试形式")),
                )

            if not courses:
                return []

            # 2. 资料管理表 → materials[]（仅审核通过）
            material_records = await feishu.list_bitable_records(
                app_token, table_ids["materials"]
            )
            materials_by_course: Dict[str, List[Material]] = defaultdict(list)
            for r in material_records:
                f = r.get("fields") or {}
                if _select_text(f.get("审核状态")) != "已通过":
                    continue
                cn = _extract_course_name(f.get("课程"))
                if not cn or cn not in courses:
                    continue  # 门控：课程主数据表无此课 → 跳过
                attachments = f.get("文件附件") or []
                if not isinstance(attachments, list):
                    attachments = [attachments] if attachments else []
                base = {
                    "material_type": _select_text(f.get("资料类型")),
                    "contributor": _select_text(f.get("贡献者")),
                    "grade": _select_text(f.get("届别")),
                    "recommendation_reason": _select_text(f.get("推荐理由")),
                    "summary": _select_text(f.get("资料摘要")),
                    "review_status": "已通过",
                }
                file_link = _extract_url(f.get("文件链接"))
                if attachments:
                    for att in attachments:
                        att_name = att.get("name") or ""
                        if not att_name:
                            continue
                        materials_by_course[cn].append(Material(
                            name=att_name,
                            file_link=file_link,
                            **base,
                        ))
                else:
                    name = _select_text(f.get("资料名称"))
                    if name:
                        materials_by_course[cn].append(Material(
                            name=name,
                            file_link=file_link,
                            **base,
                        ))

            # 3. 心得管理表 → insights[]（仅审核通过）
            insight_records = await feishu.list_bitable_records(
                app_token, table_ids["insights"]
            )
            insights_by_course: Dict[str, List[Insight]] = defaultdict(list)
            for r in insight_records:
                f = r.get("fields") or {}
                if _select_text(f.get("审核状态")) != "已通过":
                    continue
                cn = _extract_course_name(f.get("课程"))
                if not cn or cn not in courses:
                    continue
                content = _select_text(f.get("心得内容"))
                if not content:
                    continue
                insights_by_course[cn].append(Insight(
                    author=_select_text(f.get("作者")),
                    grade=_select_text(f.get("届别")),
                    score=_select_text(f.get("成绩")),
                    content=content,
                ))

            # 4. 聚合到 CourseData + 派生 contributors
            for name, course in courses.items():
                mats = materials_by_course.get(name, [])
                ins = insights_by_course.get(name, [])
                course.materials = mats
                course.insights = ins
                course.contributors = self._aggregate_contributors(mats, ins)

            return list(courses.values())
        finally:
            await feishu.close()

    @staticmethod
    async def _resolve_table_ids(feishu: FeishuAdapter, app_token: str) -> Dict[str, str]:
        """查 bitable 三张表的 table_id。"""
        tables = await feishu.get_bitable_tables(app_token)
        name_to_id = {t["name"]: t["table_id"] for t in tables}
        return {
            "course": name_to_id.get(COURSE_TABLE_NAME, ""),
            "materials": name_to_id.get(MATERIALS_TABLE_NAME, ""),
            "insights": name_to_id.get(INSIGHTS_TABLE_NAME, ""),
        }

    @staticmethod
    def _aggregate_contributors(
        materials: List[Material],
        insights: List[Insight],
    ) -> List[Contributor]:
        """聚合贡献者（合并 materials 贡献者 + insights 作者）。

        - 用 (grade, name) 做 key 合并同一个人的多重贡献（心得 + 资料）
        - 心得作者排前（按得分降序），资料贡献者排后
        - 心得作者姓名带得分后缀："22级小赵（98分）"
        - 贡献内容合并：例如 "贡献了 2 份资料（PPT、笔记）+ 1 篇高分心得"
        """
        stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,             # 资料数
            "types": set(),         # 资料类型
            "insight_count": 0,     # 心得数
            "score": "",            # 心得作者得分（取首条非空）
            "grade": "",
            "raw": "",
        })

        def _key(grade: str, name: str) -> str:
            return f"{grade}|{name}" if grade else name

        for m in materials:
            raw_name = (m.contributor or "").strip()
            if not raw_name:
                continue
            grade = (m.grade or "").strip()
            k = _key(grade, raw_name)
            stats[k]["count"] += 1
            stats[k]["raw"] = raw_name
            stats[k]["grade"] = grade
            if m.material_type:
                stats[k]["types"].add(m.material_type)

        for ins in insights:
            raw_name = (ins.author or "").strip()
            if not raw_name:
                continue
            grade = (ins.grade or "").strip()
            k = _key(grade, raw_name)
            stats[k]["raw"] = raw_name
            stats[k]["grade"] = grade
            stats[k]["insight_count"] += 1
            if not stats[k]["score"] and ins.score:
                stats[k]["score"] = ins.score.strip()

        def _score_to_num(score: str) -> float:
            if not score:
                return 0.0
            cleaned = "".join(c for c in score if c.isdigit() or c == ".")
            try:
                return float(cleaned) if cleaned else 0.0
            except (ValueError, TypeError):
                return 0.0

        def _build_base_name(s: Dict[str, Any]) -> str:
            if "级" in s["raw"]:
                return s["raw"]
            if s["grade"]:
                return f"{s['grade']}{s['raw']}"
            return s["raw"]

        # 排序：心得作者优先（按得分降序），其次资料贡献者
        sorted_stats = sorted(stats.values(), key=lambda s: (
            -1 if s["insight_count"] > 0 else 0,
            -_score_to_num(s["score"]),
            s["raw"],
        ))

        contributors: List[Contributor] = []
        seen = set()
        for s in sorted_stats:
            base_name = _build_base_name(s)
            if not base_name or base_name in seen:
                continue
            display_name = base_name
            if s["insight_count"] > 0 and s["score"]:
                display_name = f"{base_name}（{s['score']}）"
            parts = []
            if s["count"] > 0:
                types_str = "、".join(sorted(t for t in s["types"] if t)) or "多种类型"
                parts.append(f"贡献了 {s['count']} 份资料（{types_str}）")
            if s["insight_count"] > 0:
                parts.append(f"{s['insight_count']} 篇高分心得")
            contribution = " + ".join(parts) if parts else "资料与心得贡献"
            contributors.append(Contributor(
                name=display_name,
                contribution=contribution,
                score=s["score"],
            ))
            seen.add(base_name)
        return contributors


def _extract_url(url_field: Any) -> str:
    """飞书 URL 字段（type 15）→ str link。形态：{"text": "xx", "link": "https://..."}。"""
    if not url_field:
        return ""
    if isinstance(url_field, str):
        return url_field
    if isinstance(url_field, dict):
        return url_field.get("link") or url_field.get("text") or ""
    if isinstance(url_field, list) and url_field:
        first = url_field[0]
        if isinstance(first, dict):
            return first.get("link") or first.get("text") or ""
    return ""
