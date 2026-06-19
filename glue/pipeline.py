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
from services.course_data_service import CourseDataService
from config.course_schema import WIKI_YEAR_NODES
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

            # 2. 学年节点 → 原生表格内容（从 bitable 主数据表读课程）
            years = [year_filter] if year_filter else WIKI_YEAR_NODES
            year_data: Dict[str, Any] = {}
            course_svc = CourseDataService(self.settings)
            for year in years:
                courses = await course_svc.get_by_year(year, app_token)
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
            # 知识库 URL（飞书 wiki 空间访问入口）
            wiki_url = f"https://{self.settings.feishu_doc_host}/wiki/space/{space_id}"
            logger.info("知识库构建完成", space_id=space_id, years=len(year_data))
            logger.info("知识库 URL（请发到飞书群保存，否则管理员找不到）", url=wiki_url)
            return {"space_id": space_id, "url": wiki_url, "year_nodes": year_data}

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
    async def doc_pipeline(self, space_id: str = None, courses: list = None, limit: int = None,
                           year_filter: str = None) -> Dict[str, Any]:
        logger.info("开始文档生成流程", limit=limit, year_filter=year_filter)
        feishu = FeishuAdapter(self.settings)
        llm = LLMAdapter(self.settings)
        doc = DocService(feishu, llm)
        state = read_json(_STATE_FILE) or {}
        app_token = self.settings.bitable_app_token or state.get("app_token")
        if courses is None:
            if not app_token:
                await feishu.close(); await llm.close()
                return {"status": "error", "message": "缺少 app_token，无法读取 bitable 课程"}
            course_svc = CourseDataService(self.settings)
            all_courses = await course_svc.get_all(app_token)
            if year_filter:
                from services.course_data_service import _derive_year
                all_courses = [c for c in all_courses if _derive_year(c.semester) == year_filter]
                logger.info("按 year_filter 过滤后课程数", count=len(all_courses))
        else:
            all_courses = courses
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
            if not limit and app_token:
                course_svc = CourseDataService(self.settings)
                for year, node_info in (state.get("year_nodes") or {}).items():
                    obj_token = node_info.get("obj_token") if node_info else None
                    if obj_token:
                        try:
                            year_courses = await course_svc.get_by_year(year, app_token)
                            await doc.replace_year_overview(obj_token, year, year_courses)
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

                # 2. 构建含链接的新导航表（从 bitable 读课程）
                app_token = self.settings.bitable_app_token or state.get("app_token")
                if not app_token:
                    logger.warning("缺少 app_token，跳过 link 回填", year=year)
                    continue
                course_svc = CourseDataService(self.settings)
                courses = await course_svc.get_by_year(year, app_token)
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
        """运行时聚合 bitable 三张表 → in-memory CourseData 列表 + 双层门控。"""
        logger.info("开始表单数据同步")
        feishu = FeishuAdapter(self.settings)
        try:
            svc = SyncService(feishu, self.settings)
            return await svc.sync(app_token)
        finally:
            await feishu.close()

    # ── 管理表初始化流程 ────────────────────────────────────────────────────

    @log_operation("init_bitable_pipeline")
    async def init_bitable_pipeline(self, app_name: str = "PPE大礼包管理表") -> Dict[str, Any]:
        """创建管理 bitable 应用 + 资料管理表 + 心得管理表，返回 app_token 和 URL。"""
        logger.info("开始创建管理 bitable", app_name=app_name)
        feishu = FeishuAdapter(self.settings)
        sync = SyncService(feishu, self.settings)
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
        """给 bitable 添加协作者（解决应用是 owner 时人没 UI 权限的问题）。

        member_type 支持：email / mobile / openid / userid / departmentid
        （mobile 会自动转 openid，适合手机号注册的用户）。
        """
        logger.info("开始添加 bitable 协作者", app_token=app_token,
                    member_type=member_type, member_id=member_id, perm=perm)
        feishu = FeishuAdapter(self.settings)
        try:
            # mobile 需要先转 openid（drive API 不直接支持 mobile）
            actual_member_type = member_type
            actual_member_id = member_id
            if member_type == "mobile":
                actual_member_id = await feishu.resolve_to_openid(member_type, member_id)
                actual_member_type = "openid"
                logger.info("已将 mobile 解析为 openid",
                            original=member_id, openid=actual_member_id)

            result = await feishu.add_doc_member(
                token=app_token, doc_type="bitable",
                member_type=actual_member_type, member_id=actual_member_id,
                perm=perm, notify=True,
            )
            logger.info("协作者添加完成", **result)
            return result
        finally:
            await feishu.close()

    @log_operation("grant_wiki_pipeline")
    async def grant_wiki_pipeline(self, space_id: str, member_type: str,
                                   member_id: str, perm_role: str = "admin") -> Dict[str, Any]:
        """给知识空间加成员（解决应用是 owner 时人没法 UI 操作的问题）。

        member_type 支持：
        - email（自动转 openid）
        - mobile（自动转 openid，适合手机号注册的用户）
        - openid（直接用）
        - userid（直接用）
        - departmentid（部门 ID，直接用）

        perm_role 角色：
        - admin：管理员（可以编辑、添加成员、改设置）
        - editor：编辑者（可以编辑所有页面）
        - viewer：阅读者（只能看）
        """
        logger.info("开始添加知识库成员", space_id=space_id,
                    member_type=member_type, member_id=member_id, perm_role=perm_role)
        feishu = FeishuAdapter(self.settings)
        try:
            # wiki API 只接受 openid/userid/departmentid；email/mobile 需先转换
            actual_member_type = member_type
            actual_member_id = member_id
            if member_type in ("email", "mobile"):
                actual_member_id = await feishu.resolve_to_openid(member_type, member_id)
                actual_member_type = "openid"
                logger.info("已将 %s 解析为 openid", member_type,
                            original=member_id, openid=actual_member_id)
            elif member_type == "userid":
                actual_member_type = "userid"  # wiki API 原生支持

            results = await feishu.add_wiki_space_members(
                space_id, [{"member_type": actual_member_type, "member_id": actual_member_id,
                            "perm_role": perm_role}]
            )
            if results and results[0].get("status") == "added":
                logger.info("知识库成员已添加", member_id=member_id, perm_role=perm_role)
                return {"member_id": member_id, "perm_role": perm_role, "status": "added"}
            logger.warning("添加知识库成员可能失败", result=results[0] if results else None)
            return {"member_id": member_id, "perm_role": perm_role,
                    "status": results[0].get("status", "failed") if results else "failed"}
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

    @log_operation("open_wiki_pipeline")
    async def open_wiki_pipeline(self, link_share_entity: str = "anyone_editable") -> Dict[str, Any]:
        """对所有学年文档（docx）设置链接分享权限（凭链接即可访问/编辑）。

        注意：这是对 wiki 空间里每个学年文档单独设置，不是对整个 wiki 空间。
        飞书 wiki 空间本身没有「凭链接可编辑」开关，必须对每个页面单独开。
        """
        logger.info("开始设置 wiki 学年文档链接分享", link_share_entity=link_share_entity)
        state = read_json(_STATE_FILE) or {}
        year_nodes = state.get("year_nodes", {})
        if not year_nodes:
            return {"status": "error",
                    "message": "deploy_state.json 中没有 year_nodes，请先跑 python deploy.py wiki"}

        feishu = FeishuAdapter(self.settings)
        results, failed = [], []
        try:
            for year, info in year_nodes.items():
                obj_token = (info or {}).get("obj_token")
                if not obj_token:
                    continue
                try:
                    r = await feishu.open_doc_public(
                        token=obj_token, doc_type="docx",
                        link_share_entity=link_share_entity,
                    )
                    results.append({"year": year, "obj_token": obj_token, **r})
                    logger.info("学年文档链接分享已设置", year=year)
                except Exception as e:
                    failed.append({"year": year, "error": str(e)})
                    logger.warning("学年文档链接分享失败", year=year, error=str(e))

            return {"success_count": len(results), "failed_count": len(failed),
                    "results": results, "errors": failed}
        finally:
            await feishu.close()

    @log_operation("fix_bitable_pipeline")
    async def fix_bitable_pipeline(self, app_token: str) -> Dict[str, Any]:
        """给已存在 bitable 的单选字段补上选项（不删数据）。"""
        logger.info("开始修复 bitable 单选选项", app_token=app_token)
        feishu = FeishuAdapter(self.settings)
        try:
            svc = SyncService(feishu, self.settings)
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

    # ── 重置 + 录入流程（首次部署 / 重建 demo）─────────────────────────────

    @log_operation("reset_bitable_pipeline")
    async def reset_bitable_pipeline(self, app_token: str) -> Dict[str, Any]:
        """清空三张管理表所有记录（保留表结构 + 字段定义）。"""
        logger.warning("即将清空 bitable 所有记录（不可逆）", app_token=app_token)
        feishu = FeishuAdapter(self.settings)
        try:
            svc = SyncService(feishu, self.settings)
            return await svc.reset_all_records(app_token)
        finally:
            await feishu.close()

    @log_operation("seed_course_pipeline")
    async def seed_course_pipeline(self, app_token: str, *,
                                    name: str = None, semester: str = None,
                                    course_type: str = None, exam: str = None,
                                    teacher: str = "",
                                    from_file: str = None) -> Dict[str, Any]:
        """录课程到主数据表。支持单条参数或 --from-file 批量导入。"""
        feishu = FeishuAdapter(self.settings)
        try:
            svc = SyncService(feishu, self.settings)
            if from_file:
                return await svc.import_courses_from_table(app_token, from_file)
            if not (name and semester):
                return {"status": "error",
                        "message": "单条录入需要 --name 和 --semester 参数"}
            return await svc.add_course(
                app_token, name=name, semester=semester,
                course_type=course_type or "专业必修课",
                exam=exam or "其他", teacher=teacher,
            )
        finally:
            await feishu.close()

    @log_operation("seed_materials_pipeline")
    async def seed_materials_pipeline(self, app_token: str, local_dir: str,
                                       course_name: str, *,
                                       contributor: str = "管理员",
                                       grade: str = "",
                                       material_type: str = "其他",
                                       reason: str = "") -> Dict[str, Any]:
        """批量录入 raw 学习资料：扫本地文件夹 → 上传飞书 drive → 建资料表记录。"""
        from services.seed_materials_service import SeedMaterialsService
        logger.info("开始批量录入资料", dir=local_dir, course=course_name)
        feishu = FeishuAdapter(self.settings)
        try:
            sync = SyncService(feishu, self.settings)
            svc = SeedMaterialsService(feishu, sync)
            return await svc.seed_from_dir(
                app_token, local_dir, course_name,
                contributor=contributor, grade=grade,
                material_type=material_type, reason=reason,
            )
        finally:
            await feishu.close()

    @log_operation("ocr_materials_pipeline")
    async def ocr_materials_pipeline(self) -> Dict[str, Any]:
        """从资料表扫已归档资料 → 转 PDF（必要时） → GLM-OCR → LLM 摘要 → 回填 summary。"""
        from libs.cloud import get_drive
        from services.ocr_service import OcrService
        logger.info("开始 OCR + 摘要流程")
        feishu = FeishuAdapter(self.settings)
        llm = LLMAdapter(self.settings)
        cloud = get_drive(self.settings)
        try:
            svc = OcrService(feishu, llm, cloud, self.settings)
            return await svc.process_all()
        finally:
            await feishu.close()
            await llm.close()
