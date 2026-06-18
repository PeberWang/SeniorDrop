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
    sorted_courses = sorted(courses, key=lambda c: (c.semester, c.type))
    return [
        B.heading(f"{year}学年课程学习指南", 1),
        B.text(f"本文档汇集了 {year} 各门课程的学习资料与学长学姐的高分心得，共 {len(courses)} 门课程。"),
        B.divider(),
        B.heading("课程导航", 2),
        B.nav_table(sorted_courses),
    ]


class Pipeline:
    """部署流程集合"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.rollback_manager = RollbackManager()

    # ── 知识库构建流程（学年文档 + 内嵌 nav 表） ─────────────────────────

    @log_operation("wiki_pipeline")
    async def wiki_pipeline(self, space_id: str = None, space_name: str = None,
                            year_filter: str = None) -> Dict[str, Any]:
        logger.info("开始知识库构建流程", year_filter=year_filter)
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
            years = [year_filter] if year_filter else WIKI_YEAR_NODES
            year_data: Dict[str, Any] = {}
            for year in years:
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
                    await feishu.write_mixed_blocks(obj_token, blocks, index=-1)
                    logger.info("学年文档内容写入完成", year=year, blocks=len(blocks))

            # 3. 保存部署状态（合并写入：保留 app_token / course_to_doc_map 等已有字段，避免跨学年运行时覆盖丢失）
            state = read_json(_STATE_FILE) or {}
            state["space_id"] = space_id
            if app_token:
                state["app_token"] = app_token
            state.setdefault("year_nodes", {}).update(year_data)
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

            sorted_courses = sorted(courses, key=lambda c: (c.semester, c.type))
            new_table = B.nav_table(sorted_courses)
            await feishu.create_descendant_tree(obj_token, new_table, index=table_idx or -1)
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

            # 持久化 doc_url 映射到 deploy_state，让 link 命令可独立运行
            state = read_json(_STATE_FILE) or {}
            state["course_to_doc_map"] = course_to_doc_map
            write_json(_STATE_FILE, state)

            # 追加学年总论（仅全量运行；limit != None 视为测试模式，跳过）
            if not limit:
                for year, node_info in (state.get("year_nodes") or {}).items():
                    obj_token = node_info.get("obj_token") if node_info else None
                    if obj_token:
                        try:
                            await doc.replace_year_overview(obj_token, year, get_courses_by_year(year))
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
    async def link_pipeline(self, course_to_doc_map: Dict[str, str],
                            year_filter: str = None) -> Dict[str, Any]:
        """回填文档链接到学年导航表：GET 定位旧表 → DELETE 删除 → POST 新表含链接。

        替代原逐行 bitable search+update 模式，每学年仅 3 次 API 调用。
        """
        # link 可独立运行：未显式传 map 时，从 deploy_state 读最近一次 docs 生成的映射
        if not course_to_doc_map:
            state_map = (read_json(_STATE_FILE) or {}).get("course_to_doc_map") or {}
            course_to_doc_map = state_map
        if not course_to_doc_map:
            return {"status": "skipped", "reason": "未提供文档映射"}
        feishu = FeishuAdapter(self.settings)
        state = read_json(_STATE_FILE) or {}
        results, errors = [], []
        years = [year_filter] if year_filter else WIKI_YEAR_NODES
        try:
            for year in years:
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
                sorted_courses = sorted(courses, key=lambda c: (c.semester, c.type))
                new_table = B.nav_table(sorted_courses)

                # 3. DELETE 旧表 → POST 新表
                await feishu.delete_blocks(obj_token, table_idx, table_idx + 1)
                await feishu.create_descendant_tree(obj_token, new_table, index=table_idx)
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

    # ── 管理表初始化流程 ────────────────────────────────────────────────────

    @log_operation("init_bitable_pipeline")
    async def init_bitable_pipeline(self, app_name: str = "PPE大礼包管理表") -> Dict[str, Any]:
        """创建管理 bitable 应用 + 资料管理表 + 心得管理表，返回 app_token 和 URL。"""
        logger.info("开始创建管理 bitable", app_name=app_name)
        feishu = FeishuAdapter(self.settings)
        sync = SyncService(feishu, self.settings.course_db_dir)
        try:
            app = await feishu.create_bitable_app(app_name)
            app_token = app["app_token"]
            table_ids = await sync.ensure_tables(app_token)
            logger.info("管理 bitable 创建完成", app_token=app_token, url=app["url"])
            return {"app_token": app_token, "url": app["url"], "tables": table_ids}
        finally:
            await feishu.close()

    @log_operation("grant_bitable_pipeline")
    async def grant_bitable_pipeline(self, app_token: str, member_type: str,
                                     member_id: str, perm: str = "full_access") -> Dict[str, Any]:
        """给 bitable 添加协作者（解决应用是 owner 时人没 UI 权限的问题）。"""
        logger.info("开始添加 bitable 协作者", app_token=app_token,
                    member_type=member_type, member_id=member_id, perm=perm)
        feishu = FeishuAdapter(self.settings)
        try:
            result = await feishu.add_doc_member(
                token=app_token, doc_type="bitable",
                member_type=member_type, member_id=member_id,
                perm=perm, notify=True,
            )
            logger.info("协作者添加完成", **result)
            return result
        finally:
            await feishu.close()

    @log_operation("open_bitable_pipeline")
    async def open_bitable_pipeline(self, app_token: str,
                                    link_share_entity: str = "anyone_editable") -> Dict[str, Any]:
        """设置 bitable 链接分享权限（不需要加协作者，凭链接即可编辑）。"""
        logger.info("开始设置 bitable 链接分享", app_token=app_token,
                    link_share_entity=link_share_entity)
        feishu = FeishuAdapter(self.settings)
        try:
            result = await feishu.open_doc_public(
                token=app_token, doc_type="bitable",
                link_share_entity=link_share_entity,
            )
            logger.info("链接分享设置完成", **result)
            return result
        finally:
            await feishu.close()

    @log_operation("fix_bitable_pipeline")
    async def fix_bitable_pipeline(self, app_token: str) -> Dict[str, Any]:
        """给已存在 bitable 的单选字段补上选项（不删数据）。"""
        logger.info("开始修复 bitable 单选选项", app_token=app_token)
        feishu = FeishuAdapter(self.settings)
        try:
            svc = SyncService(feishu, self.settings.course_db_dir)
            return await svc.fix_single_select_options(app_token)
        finally:
            await feishu.close()

    # ── OSS 归档流程 ────────────────────────────────────────────────────────

    @log_operation("archive_pipeline")
    async def archive_pipeline(self, app_token: str,
                               purge_immediately: bool = False) -> Dict[str, Any]:
        """飞书附件 → OSS 归档：扫资料表附件字段，上传 OSS，回填 URL，删原件。"""
        import os
        from libs.cloud import get_drive
        from services.archive_service import ArchiveService
        from services.sync_service import MATERIALS_TABLE_NAME

        logger.info("开始 OSS 归档", app_token=app_token, purge_immediately=purge_immediately)
        feishu = FeishuAdapter(self.settings)
        cloud = get_drive(self.settings)
        try:
            # 拿资料表 table_id
            tables = await feishu.get_bitable_tables(app_token)
            name_to_id = {t["name"]: t["table_id"] for t in tables}
            table_id = name_to_id.get(MATERIALS_TABLE_NAME)
            if not table_id:
                return {"status": "error",
                        "message": f"未找到 {MATERIALS_TABLE_NAME}，请先 init-bitable"}

            svc = ArchiveService(feishu, cloud, self.settings)
            return await svc.archive_all(app_token, table_id, purge_immediately=purge_immediately)
        finally:
            await feishu.close()

    @log_operation("purge_archived_pipeline")
    async def purge_archived_pipeline(self, app_token: str,
                                      older_than_days: int = 7) -> Dict[str, Any]:
        """清理归档超 7 天的飞书原件（安全期机制）。"""
        from libs.cloud import get_drive
        from services.archive_service import ArchiveService
        from services.sync_service import MATERIALS_TABLE_NAME

        logger.info("开始安全期清理", older_than_days=older_than_days)
        feishu = FeishuAdapter(self.settings)
        cloud = get_drive(self.settings)
        try:
            tables = await feishu.get_bitable_tables(app_token)
            name_to_id = {t["name"]: t["table_id"] for t in tables}
            table_id = name_to_id.get(MATERIALS_TABLE_NAME)
            if not table_id:
                return {"status": "error",
                        "message": f"未找到 {MATERIALS_TABLE_NAME}"}
            svc = ArchiveService(feishu, cloud, self.settings)
            return await svc.purge_archived(app_token, table_id, older_than_days)
        finally:
            await feishu.close()
