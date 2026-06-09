# -*- coding: utf-8 -*-
"""
编排层：子流程定义。串联 services，零业务逻辑。
"""

import asyncio
import structlog
from typing import Dict, List, Optional, Any

from libs.feishu import FeishuAdapter
from libs.llm_adapter import LLMAdapter
from libs.feishu import blocks as B
from libs.data_adapter import read_json, write_json
from libs.operation_log import log_operation
from services.wiki_service import WikiService
from services.doc_service import DocService
from services.material_service import MaterialService
from services.perm_service import PermService
from services.sync_service import SyncService
from config.course_schema import get_courses_by_year, get_all_courses, WIKI_YEAR_NODES
from config.settings import Settings
from glue.rollback import RollbackManager

logger = structlog.get_logger()
_STATE_FILE = "data/deploy_state.json"


def _year_content_blocks(year: str, courses: list) -> List:
    """学年文档内容：标题 + 简介 + 原生课程导航表（学习指南链接待 link 步骤回填）。"""
    return [
        B.heading(f"{year}学年课程学习指南", 1),
        B.text(f"本文档汇集了 {year} 各门课程的学习资料与学长学姐的高分心得，共 {len(courses)} 门课程。"),
        B.divider(),
        B.heading("课程导航", 2),
        B.nav_table(courses),
    ]


class Pipeline:
    """部署流程集合"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.rollback_manager = RollbackManager()

    # ── 知识库构建流程（学年文档 + 内嵌 nav 表） ─────────────────────────

    @log_operation("wiki_pipeline")
    async def wiki_pipeline(self, space_id: str = None, space_name: str = None) -> Dict[str, Any]:
        logger.info("开始知识库构建流程")
        feishu = FeishuAdapter(self.settings)
        wiki = WikiService(feishu)
        app_token = self.settings.bitable_app_token

        try:
            # 1. 找/建知识空间
            if not space_id:
                sn = space_name or self.settings.wiki_space_name
                existing = await wiki.get_space_by_name(sn)
                if existing["space_id"]:
                    space_id = existing["space_id"]
                else:
                    result = await wiki.create_space(sn)
                    space_id = result["space_id"]
                    self.rollback_manager.record_wiki_space(space_id, sn)

            # 2. 学年节点 → 原生表格内容（无需 bitable）
            year_data: Dict[str, Any] = {}
            for year in WIKI_YEAR_NODES:
                courses = get_courses_by_year(year)
                if not courses:
                    continue

                node = await wiki.build_year_nodes(space_id, [year])
                node_info = node[year]
                obj_token = node_info["obj_token"]
                year_data[year] = {**node_info}
                self.rollback_manager.record_wiki_node(node_info["node_id"], year, space_id)

                if obj_token:
                    blocks = _year_content_blocks(year, courses)
                    # 分离普通块和表格块（表格通过 descendant API 创建）
                    regular = [b for b in blocks if b.block_type != 31]
                    tables = [b for b in blocks if b.block_type == 31]
                    idx = await feishu.append_blocks(obj_token, regular, index=0)
                    for tb in tables:
                        idx = await feishu.create_descendant(obj_token, tb, index=idx)
                    logger.info("学年文档内容写入完成", year=year, blocks=len(regular), tables=len(tables))

            # 3. 保存部署状态（供 doc 步骤使用）
            state = {"space_id": space_id, "app_token": app_token or "", "year_nodes": year_data}
            write_json(_STATE_FILE, state)

            await feishu.close()
            logger.info("知识库构建完成", space_id=space_id, years=len(year_data))
            return {"space_id": space_id, "year_nodes": year_data}

        except Exception as e:
            logger.error("知识库构建失败", error=str(e))
            await feishu.close()
            raise

    # ── 多维表格独立流程（--mode tables）───────────────────────────────────

    @log_operation("table_pipeline")
    async def table_pipeline(self, app_token: str, year: str, courses: list) -> Dict[str, Any]:
        """重建学年文档中的原生课程导航表（替代旧的 bitable 建表+挂载）。"""
        logger.info("开始课程导航表构建", year=year)
        feishu = FeishuAdapter(self.settings)
        state = read_json(_STATE_FILE) or {}
        year_nodes = state.get("year_nodes", {})
        obj_token = (year_nodes.get(year) or {}).get("obj_token")
        if not obj_token:
            await feishu.close()
            return {"status": "skipped", "reason": "学年文档不存在，请先运行 --mode wiki"}
        try:
            # 定位并删除旧导航表
            top_blocks = await feishu.list_top_blocks(obj_token)
            table_idx = None
            for i, blk in enumerate(top_blocks):
                if blk["block_type"] == 31:
                    table_idx = i
                    break
            if table_idx is not None:
                await feishu.delete_blocks(obj_token, table_idx, table_idx + 1)

            new_table = B.nav_table(courses)
            await feishu.create_descendant(obj_token, new_table, index=table_idx or 1)
            logger.info("原生课程导航表已重建", year=year, courses=len(courses))
            return {"year": year, "courses": len(courses), "status": "ok"}
        finally:
            await feishu.close()

    # ── 课程文档生成流程（WP5 实现）─────────────────────────────────────────

    @log_operation("doc_pipeline")
    async def doc_pipeline(self, space_id: str = None, courses: list = None, limit: int = None) -> Dict[str, Any]:
        logger.info("开始文档生成流程", limit=limit)
        feishu = FeishuAdapter(self.settings)
        llm = LLMAdapter(self.settings)
        doc = DocService(feishu, llm)
        state = read_json(_STATE_FILE) or {}
        all_courses = courses or get_all_courses()
        try:
            result = await doc.generate_all_course_guides(
                space_id=state.get("space_id") or space_id,
                courses=all_courses, limit=limit
            )
            course_to_doc_map = {item["course_name"]: item["url"] for item in result.get("results", []) if item.get("url")}

            # 追加学年总论（仅全量运行；limit != None 视为测试模式，跳过）
            if not limit:
                for year, node_info in (state.get("year_nodes") or {}).items():
                    obj_token = node_info.get("obj_token") if node_info else None
                    if obj_token:
                        try:
                            await doc.append_year_overview(obj_token, year, get_courses_by_year(year))
                        except Exception as e:
                            logger.warning("学年总论追加失败，跳过", year=year, error=str(e))

            await feishu.close(); await llm.close()
            return {"result": result, "course_to_doc_map": course_to_doc_map}
        except Exception as e:
            logger.error("文档生成失败", error=str(e))
            await feishu.close(); await llm.close()
            raise

    # ── 资料上传流程 ─────────────────────────────────────────────────────────

    @log_operation("material_pipeline")
    async def material_pipeline(self, app_token: str = None) -> Dict[str, Any]:
        import os
        from libs.cloud import get_drive
        config_path = "data/materials.json"
        if not os.path.exists(config_path):
            return {"status": "skipped", "reason": "data/materials.json 不存在"}
        feishu = FeishuAdapter(self.settings)
        cloud = get_drive(self.settings)
        material = MaterialService(feishu, cloud=cloud, settings=self.settings)
        try:
            result = await material.upload_materials_from_config(config_path)
            result["material_manifests"] = material.get_material_manifests()
            return result
        finally:
            await feishu.close()

    # ── 权限配置流程 ─────────────────────────────────────────────────────────

    async def perm_pipeline(self, space_id: str, app_token: str, table_id: str = "") -> Dict[str, Any]:
        feishu = FeishuAdapter(self.settings)
        perm = PermService(feishu)
        try:
            result = await perm.set_default_permissions(space_id, app_token, table_id)
            return {"status": "completed", "result": result}
        finally:
            await feishu.close()

    # ── 文档链接回填流程 ─────────────────────────────────────────────────────

    @log_operation("link_pipeline")
    async def link_pipeline(self, course_to_doc_map: Dict[str, str]) -> Dict[str, Any]:
        """回填文档链接到学年导航表：GET 定位旧表 → DELETE 删除 → POST 新表含链接。

        替代原逐行 bitable search+update 模式，每学年仅 3 次 API 调用。
        """
        if not course_to_doc_map:
            return {"status": "skipped", "reason": "未提供文档映射"}
        feishu = FeishuAdapter(self.settings)
        state = read_json(_STATE_FILE) or {}
        results, errors = [], []
        try:
            for year in WIKI_YEAR_NODES:
                year_nodes = state.get("year_nodes", {})
                obj_token = (year_nodes.get(year) or {}).get("obj_token")
                if not obj_token:
                    continue

                # 1. 列出顶层块，定位导航表（block_type=31）
                top_blocks = await feishu.list_top_blocks(obj_token)
                table_idx = None
                for i, blk in enumerate(top_blocks):
                    if blk["block_type"] == 31:
                        table_idx = i
                        break

                if table_idx is None:
                    logger.warning("未找到学年文档中的导航表", year=year)
                    continue

                # 2. 构建含链接的新导航表
                courses = get_courses_by_year(year)
                for c in courses:
                    if c.name in course_to_doc_map:
                        c.doc_url = course_to_doc_map[c.name]
                new_table = B.nav_table(courses)

                # 3. DELETE 旧表 → POST 新表
                await feishu.delete_blocks(obj_token, table_idx, table_idx + 1)
                await feishu.create_descendant(obj_token, new_table, index=table_idx)
                results.append({"year": year, "updated": len(courses)})
                logger.info("导航表链接回填完成", year=year, courses=len(courses))
        finally:
            await feishu.close()
        return {"success_count": len(results), "error_count": len(errors),
                "results": results, "errors": errors}

    # ── 表单同步流程 ─────────────────────────────────────────────────────────

    @log_operation("sync_form_pipeline")
    async def sync_form_pipeline(self, app_token: str) -> Dict[str, Any]:
        """从 bitable 管理表拉取已批准记录，合并到 data/db/*.json。"""
        logger.info("开始表单数据同步")
        feishu = FeishuAdapter(self.settings)
        try:
            svc = SyncService(feishu, self.settings.course_db_dir)
            return await svc.sync(app_token)
        finally:
            await feishu.close()
