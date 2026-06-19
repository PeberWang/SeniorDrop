# -*- coding: utf-8 -*-
"""bitable 三张表的同步与门控服务。

设计要点：
- bitable 是唯一真相源，本地不再持久化 CourseData。
- sync() 是运行时聚合：扫三张表 → 派生 in-memory CourseData 列表。
- 双层门控位置 1（sync 层）：资料表/心得表中存在但主数据表无的 → 跳过 + 警告。
  门控位置 2（docs 层）在 CourseDataService.get_all/get_by_year 内实现。
- sync 后回填主数据表「资料数量」+「最后更新」字段。

边界规则：
- 绝不动 teacher/type/exam/semester 等基本字段（管理员 UI 改动具有最高优先级）
- 只更新派生字段：资料数量、最后更新
"""

import structlog
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, List

from libs.feishu import FeishuAdapter
from config.course_schema import (
    COURSE_TABLE_FIELDS, MATERIALS_TABLE_FIELDS, INSIGHTS_TABLE_FIELDS,
    SINGLE_SELECT_OPTIONS,
)
from config.settings import Settings

logger = structlog.get_logger()

COURSE_TABLE_NAME = "课程主数据表"
MATERIALS_TABLE_NAME = "资料管理表"
INSIGHTS_TABLE_NAME = "心得管理表"

# 飞书附件字段（type 17）的 record 值格式
# [{"file_token": "boxcnXXX", "name": "x.pdf", "size": 12345, "type": "stream"}]


def _normalize_str(val: Any) -> str:
    """值归一化为去空白 str。NaN/None → ""。"""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in {"nan", "none", "null"}:
        return ""
    return s


def _read_course_table(file_path: str) -> List[Dict[str, Any]]:
    """读 Excel/CSV/TSV 课程清单（GBK/UTF-8 自动识别 + 分隔符 sniff）。

    支持形态：
      - 真 .xlsx（PK 头）→ openpyxl
      - 文本（含被错存为 .xlsx 但实际是 TSV/CSV 的文件）→ 自动 sniff
    """
    import csv
    import io
    import os
    from pathlib import Path
    import pandas as pd

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"课程清单文件不存在: {file_path}")

    # 真 xlsx：PK 头 → openpyxl
    with open(path, "rb") as f:
        head = f.read(2)
    if head == b"PK":
        df = pd.read_excel(path, engine="openpyxl")
        return df.where(pd.notna(df), "").to_dict("records")

    # 否则按文本格式处理
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise RuntimeError(f"无法识别文件编码（试过 utf-8/gbk/gb18030）：{file_path}")

    # sniff 分隔符
    first_line = text.split("\n", 1)[0]
    try:
        dialect = csv.Sniffer().sniff(first_line, delimiters="\t,;|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = "\t"  # 默认 Tab

    df = pd.read_csv(io.StringIO(text), delimiter=delimiter, dtype=str)
    df = df.where(pd.notna(df), "")
    return df.to_dict("records")


async def _batch_delete_records(feishu: FeishuAdapter, app_token: str,
                                 table_id: str, page_size: int = 500) -> int:
    """清空表所有记录（按 page_size 分批 batch_delete），返回删除条数。"""
    from lark_oapi.api.bitable.v1 import (
        BatchDeleteAppTableRecordRequest,
        BatchDeleteAppTableRecordRequestBody,
        ListAppTableRecordRequest,
    )
    deleted = 0
    while True:
        list_req = (ListAppTableRecordRequest.builder()
                    .app_token(app_token).table_id(table_id).page_size(page_size).build())
        resp = await feishu.client.bitable.v1.app_table_record.alist(list_req)
        if not resp.success():
            raise RuntimeError(f"列出记录失败: {resp.msg}")
        items = resp.data.items or []
        if not items:
            break
        record_ids = [r.record_id for r in items if r.record_id]
        if not record_ids:
            break
        del_req = (BatchDeleteAppTableRecordRequest.builder()
                   .app_token(app_token).table_id(table_id)
                   .request_body(BatchDeleteAppTableRecordRequestBody.builder()
                                 .records(record_ids).build()).build())
        await feishu.client.bitable.v1.app_table_record.abatch_delete(del_req)
        deleted += len(record_ids)
        if len(items) < page_size:
            break
    return deleted


def _select_text(field_val: Any) -> str:
    """飞书单选/富文本字段值归一化为 str。"""
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
    return _select_text(course_field)


class SyncService:
    """bitable 三张表的同步与门控。"""

    def __init__(self, feishu: FeishuAdapter, settings: Settings = None):
        self.feishu = feishu
        self.settings = settings

    async def ensure_tables(self, app_token: str) -> Dict[str, str]:
        """确保三张管理表存在且字段正确，返回 {course, materials, insights} table_id 映射。"""
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
        """运行时聚合 bitable 三张表 + 双层门控位置 1。

        返回：
            {
                "course_count": 主数据表课程总数,
                "synced_courses": 有效聚合 CourseData 的课程数,
                "skipped_materials": 因主数据表无对应课程被跳过的资料数,
                "skipped_insights": 因主数据表无对应课程被跳过的心得数,
                "warnings": [str],
                "updated_metadata": 更新了「资料数量」「最后更新」的课程数,
            }
        """
        table_ids = await self.ensure_tables(app_token)
        course_tid = table_ids["course"]
        materials_tid = table_ids["materials"]
        insights_tid = table_ids["insights"]

        # 1. 课程主数据表 → {课程名: record_id}（门控基准）
        course_records = await self.feishu.list_bitable_records(app_token, course_tid)
        course_meta: Dict[str, Dict[str, Any]] = {}
        for r in course_records:
            f = r.get("fields") or {}
            name = _select_text(f.get("课程名称"))
            if name:
                course_meta[name] = {"record_id": r.get("record_id", ""), "fields": f}

        if not course_meta:
            logger.warning("课程主数据表为空，sync 无所事事。请先 seed-course 录入课程。")
            return {"course_count": 0, "synced_courses": 0,
                    "skipped_materials": 0, "skipped_insights": 0,
                    "warnings": ["课程主数据表为空"], "updated_metadata": 0}

        # 2. 资料管理表 → 按课程分组（仅审核通过）
        material_records = await self.feishu.list_bitable_records(app_token, materials_tid)
        materials_by_course: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        skipped_materials = 0
        warnings: List[str] = []
        for r in material_records:
            f = r.get("fields") or {}
            if _select_text(f.get("审核状态")) != "已通过":
                continue
            cn = _extract_course_name(f.get("课程"))
            if not cn:
                continue
            if cn not in course_meta:
                # 门控位置 1：课程主数据表无此课 → 跳过
                skipped_materials += 1
                msg = f"资料表记录[r={r.get('record_id', '')[:10]}] 课程「{cn}」不在主数据表，跳过。请管理员在 bitable UI 课程主数据表加该课后重跑 sync。"
                if msg not in warnings:
                    warnings.append(msg)
                continue
            materials_by_course[cn].append(f)

        # 3. 心得管理表 → 按课程分组（仅审核通过）
        insight_records = await self.feishu.list_bitable_records(app_token, insights_tid)
        insights_by_course: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        skipped_insights = 0
        for r in insight_records:
            f = r.get("fields") or {}
            if _select_text(f.get("审核状态")) != "已通过":
                continue
            cn = _extract_course_name(f.get("课程"))
            if not cn:
                continue
            if cn not in course_meta:
                skipped_insights += 1
                msg = f"心得表记录[r={r.get('record_id', '')[:10]}] 课程「{cn}」不在主数据表，跳过。"
                if msg not in warnings:
                    warnings.append(msg)
                continue
            insights_by_course[cn].append(f)

        # 4. 更新主数据表派生字段：「资料数量」+「最后更新」
        now_ms = int(datetime.now().timestamp() * 1000)
        updated_metadata = 0
        for name, meta in course_meta.items():
            mat_count = len(materials_by_course.get(name, []))
            update_fields: Dict[str, Any] = {
                "资料数量": mat_count,
                "最后更新": now_ms,
            }
            await self.feishu.update_bitable_record(
                app_token, course_tid, meta["record_id"], update_fields
            )
            updated_metadata += 1

        for w in warnings:
            logger.warning("sync 跳过", reason=w)

        logger.info("sync 完成",
                    course_count=len(course_meta),
                    skipped_materials=skipped_materials,
                    skipped_insights=skipped_insights,
                    updated_metadata=updated_metadata)

        return {
            "course_count": len(course_meta),
            "synced_courses": len(course_meta),
            "skipped_materials": skipped_materials,
            "skipped_insights": skipped_insights,
            "warnings": warnings,
            "updated_metadata": updated_metadata,
        }

    async def reset_all_records(self, app_token: str) -> Dict[str, Any]:
        """清空三张管理表所有记录（保留表结构 + 字段定义）。

        危险操作：不可逆。仅用于首次部署 / 重置 demo。
        """
        table_ids = await self.ensure_tables(app_token)
        result = {}
        for label, tid in table_ids.items():
            count = await _batch_delete_records(self.feishu, app_token, tid)
            result[label] = count
            logger.info("表记录已清空", table=label, deleted=count)
        return {"deleted": result, "total": sum(result.values())}

    async def add_course(self, app_token: str, *, name: str, semester: str,
                          course_type: str, exam: str, teacher: str = "") -> Dict[str, Any]:
        """往课程主数据表录一条课程。已存在（按课程名匹配）则覆盖基本字段。

        基本字段以管理员录入为最高优先级：seed-course 写入即生效，sync 不动这些字段。
        """
        table_ids = await self.ensure_tables(app_token)
        course_tid = table_ids["course"]

        fields = {
            "课程名称": name,
            "授课老师": teacher,
            "开课学期": semester,
            "课程类型": course_type,
            "考试形式": exam,
        }
        # 查重：按「课程名称」精确匹配
        existing = await self.feishu.search_bitable_record(
            app_token, course_tid, "课程名称", name
        )
        if existing:
            await self.feishu.update_bitable_record(
                app_token, course_tid, existing["record_id"], fields
            )
            logger.info("课程已更新（覆盖基本字段）", name=name, record_id=existing["record_id"])
            return {"action": "update", "name": name, "record_id": existing["record_id"]}

        add_result = await self.feishu.add_bitable_record(app_token, course_tid, fields)
        logger.info("课程已添加", name=name, record_id=add_result["record_id"])
        return {"action": "insert", "name": name, "record_id": add_result["record_id"]}

    async def add_material_record(self, app_token: str, *, course_name: str,
                                    contributor: str, grade: str, material_type: str,
                                    reason: str, file_token: str, file_name: str,
                                    review_status: str = "已通过") -> Dict[str, Any]:
        """往资料管理表加一条记录（管理员批量录入 raw 资料用）。

        字段映射：
          - 贡献者 / 届别 / 课程 / 资料类型 / 推荐理由（学生填表字段）
          - 文件附件（飞书附件字段 type 17，值 = [{file_token, name, size, type}]）
          - 审核状态（默认已通过，因为是管理员录入）
        """
        table_ids = await self.ensure_tables(app_token)
        materials_tid = table_ids["materials"]

        fields = {
            "贡献者": contributor,
            "届别": grade,
            "课程": course_name,
            "资料类型": material_type,
            "推荐理由": reason,
            "审核状态": review_status,
            "文件附件": [{"file_token": file_token, "name": file_name,
                         "type": "stream"}],
        }
        result = await self.feishu.add_bitable_record(app_token, materials_tid, fields)
        logger.info("资料记录已添加", course=course_name, file=file_name,
                    record_id=result["record_id"])
        return {"record_id": result["record_id"], "course": course_name, "file": file_name}

    async def import_courses_from_table(self, app_token: str, file_path: str,
                                          default_type: str = "专业必修课") -> Dict[str, Any]:
        """从 Excel/CSV/TSV 批量导入课程到主数据表。

        自动识别格式：
          - 真 .xlsx（PK 头）→ openpyxl
          - 文本格式（GBK/UTF-8 自动检测 + Tab/逗号/分号 分隔符 sniff）

        列名映射（兼容多种命名）：
          - "名称" / "课程名称" / "name" → 课程名称
          - "学期" / "开课学期" / "semester" → 开课学期
          - "授课老师" / "教师" / "teacher" → 授课老师
          - "考核方式" / "考试形式" / "exam" → 考试形式
          - "类型" / "课程类型" / "type" → 课程类型（缺失用 default_type）
        """
        records = _read_course_table(file_path)
        logger.info("课程清单读取完成", file=file_path, rows=len(records))

        results, errors = [], []
        for r in records:
            try:
                name = _normalize_str(r.get("名称") or r.get("课程名称") or r.get("name"))
                semester = _normalize_str(r.get("学期") or r.get("开课学期") or r.get("semester"))
                teacher = _normalize_str(r.get("授课老师") or r.get("教师") or r.get("teacher"))
                exam = _normalize_str(r.get("考核方式") or r.get("考试形式") or r.get("exam"))
                course_type = _normalize_str(r.get("类型") or r.get("课程类型") or r.get("type")) or default_type
                if not name or not semester:
                    logger.warning("课程数据缺字段，跳过", row=r)
                    continue
                result = await self.add_course(
                    app_token, name=name, semester=semester,
                    course_type=course_type, exam=exam, teacher=teacher,
                )
                results.append(result)
            except Exception as e:
                logger.error("课程导入失败", row=r, error=str(e))
                errors.append({"row": r, "error": str(e)})

        logger.info("批量导入课程完成", total=len(records),
                    success=len(results), failed=len(errors))
        return {
            "total": len(records),
            "success": len(results),
            "failed": len(errors),
            "results": results[:10],
            "errors": errors[:5],
        }
