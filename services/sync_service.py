# -*- coding: utf-8 -*-
"""表单采集同步服务 — 从 bitable 管理表拉取已批准记录，合并到 data/db/*.json。"""

import structlog
from collections import defaultdict
from typing import Dict, Any, List

from libs.feishu import FeishuAdapter
from libs.data_adapter import read_course_db, write_course_db, read_index
from config.course_schema import (
    CourseData, Material, Insight, Contributor,
    COURSES_BY_YEAR,
    COURSE_TABLE_FIELDS, MATERIALS_TABLE_FIELDS, INSIGHTS_TABLE_FIELDS,
    SINGLE_SELECT_OPTIONS,
    WIKI_YEAR_NODES,
)

logger = structlog.get_logger()

COURSE_TABLE_NAME = "课程主数据表"
MATERIALS_TABLE_NAME = "资料管理表"
INSIGHTS_TABLE_NAME = "心得管理表"


class SyncService:
    """将已批准的 bitable 表单记录同步到本地 data/db/*.json。"""

    def __init__(self, feishu: FeishuAdapter, db_dir: str):
        self.feishu = feishu
        self.db_dir = db_dir

    async def ensure_tables(self, app_token: str) -> Dict[str, str]:
        """确保资料/心得管理表存在且字段正确，返回 {"materials": tid, "insights": tid}。"""
        tables = await self.feishu.get_bitable_tables(app_token)
        name_to_id = {t["name"]: t["table_id"] for t in tables}

        result = {}
        for name, fields_def in [(COURSE_TABLE_NAME, COURSE_TABLE_FIELDS),
                                  (MATERIALS_TABLE_NAME, MATERIALS_TABLE_FIELDS),
                                  (INSIGHTS_TABLE_NAME, INSIGHTS_TABLE_FIELDS)]:
            if name in name_to_id:
                tid = name_to_id[name]
            else:
                info = await self.feishu.create_bitable_table(app_token, name)
                tid = info["table_id"]

            existing = await self.feishu.list_bitable_fields(app_token, tid)
            existing_names = {f["field_name"] for f in existing}
            new_fields = self._enrich_with_options(
                [(fn, ft) for fn, ft in fields_def if fn not in existing_names]
            )
            if new_fields:
                await self.feishu.create_bitable_fields(app_token, tid, new_fields)
            result[name] = tid

        return {"course": result[COURSE_TABLE_NAME],
                "materials": result[MATERIALS_TABLE_NAME],
                "insights": result[INSIGHTS_TABLE_NAME]}

    @staticmethod
    def _aggregate_contributors(course: Dict[str, Any],
                                course_materials: List[Dict[str, Any]]) -> None:
        """从 materials 聚合贡献者到 course.contributors[]（去重 + 自动生成 contribution）。

        - 已在 contributors[] 的不重复加
        - contributor 已含届别（如 '22级小赵'）则直接用；否则拼 grade（'22级' + '牧远' → '22级牧远'）
        - contribution 文本格式："贡献了 N 份资料（类型1、类型2）"
        """
        existing = {c.get("name") for c in course.get("contributors", [])}
        stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "types": set(), "grade": "", "raw": ""})
        for m in course_materials:
            raw_name = (m.get("贡献者") or "").strip()
            if not raw_name:
                continue
            grade = (m.get("届别") or "").strip()
            key = f"{grade}|{raw_name}" if grade else raw_name
            # 一条 bitable 记录可能含多个附件（多附件共享理由方案 A），count 按附件数算
            attachments = m.get("文件附件", []) or []
            if not isinstance(attachments, list):
                attachments = [attachments] if attachments else []
            stats[key]["count"] += len(attachments) if attachments else 1
            stats[key]["raw"] = raw_name
            stats[key]["grade"] = grade
            if m.get("资料类型"):
                stats[key]["types"].add(m["资料类型"])

        for s in stats.values():
            if "级" in s["raw"]:
                full_name = s["raw"]
            elif s["grade"]:
                full_name = f"{s['grade']}{s['raw']}"
            else:
                full_name = s["raw"]
            if not full_name or full_name in existing:
                continue
            types_str = "、".join(sorted(t for t in s["types"] if t)) or "多种类型"
            contribution = f"贡献了 {s['count']} 份资料（{types_str}）"
            course.setdefault("contributors", []).append(
                Contributor(name=full_name, contribution=contribution).model_dump()
            )
            existing.add(full_name)

    @staticmethod
    def _enrich_with_options(fields_def):
        """给单选字段（type=3）附加 property.options。"""
        result = []
        for name, ftype in fields_def:
            fd = {"field_name": name, "type": ftype}
            if ftype == 3 and name in SINGLE_SELECT_OPTIONS:
                opts = SINGLE_SELECT_OPTIONS[name]
                fd["property"] = {
                    "options": [{"name": o, "color": i % 54} for i, o in enumerate(opts)]
                }
            result.append(fd)
        return result

    async def fix_single_select_options(self, app_token: str) -> Dict[str, Any]:
        """给已存在 bitable 表里的单选字段补上选项（不删数据）。"""
        updated = []
        for table_name, _ in [
            (COURSE_TABLE_NAME, COURSE_TABLE_FIELDS),
            (MATERIALS_TABLE_NAME, MATERIALS_TABLE_FIELDS),
            (INSIGHTS_TABLE_NAME, INSIGHTS_TABLE_FIELDS),
        ]:
            tables = await self.feishu.get_bitable_tables(app_token)
            name_to_id = {t["name"]: t["table_id"] for t in tables}
            tid = name_to_id.get(table_name)
            if not tid:
                logger.warning("表不存在，跳过", table=table_name)
                continue

            existing = await self.feishu.list_bitable_fields(app_token, tid)
            for f in existing:
                if f["type"] != 3:
                    continue
                opts = SINGLE_SELECT_OPTIONS.get(f["field_name"])
                if not opts:
                    continue
                field_def = {
                    "field_name": f["field_name"],
                    "type": 3,
                    "property": {
                        "options": [{"name": o, "color": i % 54}
                                    for i, o in enumerate(opts)]
                    },
                }
                await self.feishu.update_bitable_field(
                    app_token, tid, f["field_id"], field_def
                )
                updated.append({"table": table_name, "field": f["field_name"],
                                "n_options": len(opts)})
                logger.info("字段选项已更新", table=table_name,
                            field=f["field_name"], n=len(opts))
        return {"updated_fields": updated, "count": len(updated)}

    async def sync(self, app_token: str) -> Dict[str, Any]:
        """主入口：拉取已批准记录 → 按年级+课程合并到 data/db/*.json。

        边界规则（严格遵守）：
        - 仅向 materials[]/insights[] 数组追加新项，绝不修改/删除已有项
        - 绝不动 teacher/type/exam/semester 等基本字段（管理员 UI 改动具有最高优先级）
        - 新贡献者自动追加到 contributors[]（gap 待补，见 production-checklist）
        """
        table_ids = await self.ensure_tables(app_token)

        materials_raw = await self.feishu.list_bitable_records(app_token, table_ids["materials"])
        insights_raw = await self.feishu.list_bitable_records(app_token, table_ids["insights"])

        approved_materials = [r["fields"] for r in materials_raw
                              if r["fields"].get("审核状态") == "已通过"]
        approved_insights = [r["fields"] for r in insights_raw
                             if r["fields"].get("审核状态") == "已通过"]

        # 按课程名分组（用课程名反查 year；bitable 的"年级"是贡献者年级不是学年）
        m_by_course = defaultdict(list)
        for m in approved_materials:
            cn = m.get("课程", "")
            if cn:
                m_by_course[cn].append(m)

        i_by_course = defaultdict(list)
        for ins in approved_insights:
            cn = ins.get("课程", "")
            if cn:
                i_by_course[cn].append(ins)

        all_course_names = set(m_by_course.keys()) | set(i_by_course.keys())
        updated, skipped = 0, 0

        # 课程→year 映射：过渡期从本地 db index.json 读（bitable 课程主数据表尚未填充）
        # TODO(production): bitable 课程主数据表填充后改回读 bitable
        index = read_index(self.db_dir)
        year_to_course_names = defaultdict(set)
        for meta in index:
            name = meta.get("name")
            year = meta.get("year")
            if name and year:
                year_to_course_names[year].add(name)

        for year in WIKI_YEAR_NODES:
            year_course_names = year_to_course_names.get(year, set())
            relevant = all_course_names & year_course_names
            if not relevant:
                continue
            records = read_course_db(self.db_dir, year)
            name_map = {r["name"]: r for r in records}

            for course_name in relevant:
                if course_name not in name_map:
                    logger.warning("课程不在 data/db 中，跳过", year=year, course=course_name)
                    skipped += 1
                    continue
                course = name_map[course_name]

                for m in m_by_course.get(course_name, []):
                    # 多附件展开：一条记录 → N 个 Material，共享同一段推荐理由
                    base = {
                        "material_type": m.get("资料类型", ""),
                        "contributor": m.get("贡献者", ""),
                        "grade": m.get("届别", ""),
                        "recommendation_reason": m.get("推荐理由", ""),
                        "summary": m.get("资料摘要", ""),
                        "review_status": "已通过",
                    }
                    attachments = m.get("文件附件", []) or []
                    if not isinstance(attachments, list):
                        attachments = [attachments]

                    existing_names = {x.get("name") for x in course.get("materials", [])}
                    if not attachments:
                        # 无附件记录：用「资料名称」字段占位
                        name = m.get("资料名称", "")
                        if name and name not in existing_names:
                            material = Material(name=name,
                                                file_link=m.get("文件链接", ""), **base)
                            course.setdefault("materials", []).append(material.model_dump())
                        continue

                    # 有附件：每个附件一个 Material
                    # demo: file_link 暂用飞书附件 url，归档逻辑上线后替换为 OSS 预签名 URL
                    for att in attachments:
                        name = att.get("name", "")
                        if not name or name in existing_names:
                            continue
                        material = Material(name=name,
                                            file_link=att.get("url", ""), **base)
                        course.setdefault("materials", []).append(material.model_dump())
                        existing_names.add(name)

                for ins in i_by_course.get(course_name, []):
                    existing_contents = {x.get("content") for x in course.get("insights", [])}
                    if ins.get("心得内容", "") and ins["心得内容"] not in existing_contents:
                        course.setdefault("insights", []).append(Insight(
                            author=ins.get("作者", ""),
                            grade=ins.get("届别", ""),
                            score=ins.get("成绩", ""),
                            content=ins["心得内容"],
                        ).model_dump())

                # 聚合贡献者：把 materials 里出现的新贡献者加到 contributors[]
                self._aggregate_contributors(course, m_by_course.get(course_name, []))

                updated += 1

            write_course_db(self.db_dir, year, records)
            logger.info("学年同步完成", year=year, courses=len(records))

        return {"updated_courses": updated, "skipped": skipped,
                "materials_found": len(approved_materials),
                "insights_found": len(approved_insights)}
