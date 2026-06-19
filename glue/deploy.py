# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 主部署流程
串联所有service，零业务逻辑
"""

import json
import os
import structlog
from typing import Dict, Optional, Any
from dataclasses import dataclass

from libs.feishu import FeishuAdapter
from services.material_service import MaterialService
from services.course_data_service import CourseDataService
from config.settings import Settings
from glue.rollback import RollbackManager
from glue.pipeline import Pipeline

logger = structlog.get_logger()

_DEPLOY_STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "deploy_state.json")


async def _resolve_app_token(settings: Settings) -> str:
    """解析 bitable app_token 多级来源，若无则自动创建。

    优先级：.env > deploy_state.json > API 自动创建
    """
    # 1. 优先 .env 手动配置
    if settings.bitable_app_token:
        return settings.bitable_app_token

    # 2. 查 deploy_state.json 缓存的 token
    if os.path.exists(_DEPLOY_STATE_PATH):
        try:
            with open(_DEPLOY_STATE_PATH, "r", encoding="utf-8") as f:
                cached = json.load(f).get("app_token", "")
            if cached:
                logger.info("从部署状态中恢复 app_token", token=cached[:20] + "...")
                return cached
        except Exception:
            pass

    # 3. 自动创建
    logger.info("未检测到 BITABLE_APP_TOKEN，正在自动创建多维表格应用...")
    feishu = FeishuAdapter(settings)
    try:
        result = await feishu.create_bitable_app("PPE课程数据")
        app_token = result["app_token"]
        _save_app_token(app_token)
        logger.info("多维表格应用已自动创建并保存", app_token=app_token)
        return app_token
    finally:
        await feishu.close()


def _save_app_token(app_token: str) -> None:
    """将 app_token 持久化到 deploy_state.json。"""
    state = {}
    if os.path.exists(_DEPLOY_STATE_PATH):
        try:
            with open(_DEPLOY_STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass
    state["app_token"] = app_token
    os.makedirs(os.path.dirname(_DEPLOY_STATE_PATH), exist_ok=True)
    with open(_DEPLOY_STATE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


@dataclass
class DeployArgs:
    """部署参数（统一承载所有 mode 所需字段，不同 mode 取自己关心的）"""
    mode: str
    limit: Optional[int] = None
    incremental: bool = False
    course_to_doc_map: Optional[Dict[str, str]] = None
    space_id: Optional[str] = None
    import_config: Optional[str] = None
    year_filter: Optional[str] = None
    # seed-course
    name: Optional[str] = None
    semester: Optional[str] = None
    course_type: Optional[str] = None
    exam: Optional[str] = None
    teacher: str = ""
    from_file: Optional[str] = None
    # seed-materials
    local_dir: str = ""
    course_name: str = ""
    contributor: str = "管理员"
    grade: str = ""
    material_type: str = "其他"
    reason: str = ""
    # archive
    purge_immediately: bool = False
    older_than_days: int = 7


async def _deploy_wiki(settings: Settings, year_filter: Optional[str] = None) -> Dict[str, Any]:
    logger.info("开始部署知识库", year_filter=year_filter)
    pipeline = Pipeline(settings)
    # 先查找已有空间，避免创建时触发需要 user_access_token 的权限检查
    feishu = FeishuAdapter(settings)
    from services.wiki_service import WikiService
    wiki = WikiService(feishu)
    existing = await wiki.get_space_by_name(settings.wiki_space_name)
    await feishu.close()
    if existing["space_id"]:
        logger.info("找到已有知识空间，直接使用", space_id=existing["space_id"])
        return await pipeline.wiki_pipeline(space_id=existing["space_id"], space_name=None,
                                            year_filter=year_filter)
    return await pipeline.wiki_pipeline(space_id=None, space_name=settings.wiki_space_name,
                                        year_filter=year_filter)


async def _deploy_tables(settings: Settings, year_filter: Optional[str] = None) -> Dict[str, Any]:
    logger.info("开始独立部署多维表格", year_filter=year_filter)
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    course_data = CourseDataService(settings)
    all_results = []
    years = [year_filter] if year_filter else ["大一", "大二", "大三", "大四"]
    for year in years:
        courses = await course_data.get_by_year(year, app_token)
        if courses:
            result = await pipeline.table_pipeline(app_token=app_token, year=year, courses=courses)
            all_results.append(result)
    return {"results": all_results}


async def _deploy_docs(settings: Settings, limit: int = None,
                       year_filter: Optional[str] = None) -> Dict[str, Any]:
    logger.info("开始部署云文档", limit=limit, year_filter=year_filter)
    pipeline = Pipeline(settings)
    result = await pipeline.doc_pipeline(space_id=None, courses=None,
                                          limit=limit, year_filter=year_filter)
    return result


async def _deploy_materials(settings: Settings) -> Dict[str, Any]:
    logger.info("开始部署资料")
    import os
    from libs.cloud import get_drive
    feishu = FeishuAdapter(settings)
    cloud = get_drive(settings)
    material_service = MaterialService(feishu, cloud=cloud, settings=settings)
    materials_path = os.path.join("data", "materials.json")
    if not os.path.exists(materials_path):
        return {"status": "error", "message": "资料配置文件不存在"}
    result = await material_service.upload_materials_from_config(materials_path)
    result["material_manifests"] = material_service.get_material_manifests()
    return result


async def _deploy_links(settings: Settings, course_to_doc_map: Dict[str, str] = None,
                        year_filter: Optional[str] = None) -> Dict[str, Any]:
    logger.info("开始关联表格与文档", year_filter=year_filter)
    pipeline = Pipeline(settings)
    return await pipeline.link_pipeline(course_to_doc_map=course_to_doc_map,
                                        year_filter=year_filter)


async def _deploy_sync(settings: Settings) -> Dict[str, Any]:
    """独立表格同步（全量重建）—— 现阶段等同 --mode tables。"""
    return await _deploy_tables(settings)


async def _deploy_ocr(settings: Settings) -> Dict[str, Any]:
    logger.info("开始 OCR 处理流程")
    from libs.cloud import get_drive
    from libs.llm_adapter import LLMAdapter
    from services.ocr_service import OcrService
    feishu = FeishuAdapter(settings)
    llm = LLMAdapter(settings)
    cloud = get_drive(settings)
    service = OcrService(feishu, llm, cloud, settings)
    try:
        return await service.process_all()
    finally:
        await feishu.close()
        await llm.close()


async def _deploy_catalog(settings: Settings) -> Dict[str, Any]:
    logger.info("开始目录构建流程")
    from services.catalog_service import CatalogService
    feishu = FeishuAdapter(settings)
    service = CatalogService(feishu, settings)
    try:
        return await service.build_and_upload()
    finally:
        await feishu.close()


async def _deploy_sync_form(settings: Settings) -> Dict[str, Any]:
    """从 bitable 管理表同步已批准的表单记录到 data/db/*.json。"""
    logger.info("开始表单数据同步")
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    return await pipeline.sync_form_pipeline(app_token)


async def _deploy_init_bitable(settings: Settings) -> Dict[str, Any]:
    """创建管理 bitable 应用（资料管理表 + 心得管理表），持久化 app_token。"""
    logger.info("开始创建管理 bitable")
    pipeline = Pipeline(settings)
    result = await pipeline.init_bitable_pipeline()
    _save_app_token(result["app_token"])
    logger.info("app_token 已持久化，请填到 .env 的 BITABLE_APP_TOKEN",
                app_token=result["app_token"], url=result.get("url"))
    logger.info("bitable URL（请发到飞书群保存，否则管理员找不到）", url=result.get("url"))
    return result


async def _deploy_grant_bitable(settings: Settings, member_type: str,
                                member_id: str, perm: str = "full_access") -> Dict[str, Any]:
    """给 bitable 添加协作者（解决应用是 owner 时人没法 UI 操作的问题）。"""
    logger.info("开始添加 bitable 协作者", member_type=member_type, member_id=member_id)
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    return await pipeline.grant_bitable_pipeline(app_token, member_type, member_id, perm)


async def _deploy_grant_wiki(settings: Settings, member_type: str,
                              member_id: str, perm_role: str = "admin") -> Dict[str, Any]:
    """给知识空间加成员（解决应用是 owner 时人没法 UI 编辑知识库的问题）。

    space_id 从 deploy_state.json 读（wiki 命令写入）。
    """
    logger.info("开始添加知识库成员", member_type=member_type,
                member_id=member_id, perm_role=perm_role)
    state = read_json(_DEPLOY_STATE_PATH) or {}
    space_id = state.get("space_id")
    if not space_id:
        return {"status": "error",
                "message": "deploy_state.json 中没有 space_id，请先跑 python deploy.py wiki"}
    pipeline = Pipeline(settings)
    return await pipeline.grant_wiki_pipeline(space_id, member_type, member_id, perm_role)


async def _deploy_open_bitable(settings: Settings,
                               link_share_entity: str = "anyone_editable") -> Dict[str, Any]:
    """设置 bitable 链接分享权限（凭链接即可访问，不需要协作者 ID）。"""
    logger.info("开始设置 bitable 链接分享", link_share_entity=link_share_entity)
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    return await pipeline.open_bitable_pipeline(app_token, link_share_entity)


async def _deploy_open_wiki(settings: Settings,
                             link_share_entity: str = "anyone_editable") -> Dict[str, Any]:
    """对 wiki 所有学年文档设置链接分享（凭链接即可访问/编辑，不需要协作者 ID）。"""
    logger.info("开始设置 wiki 链接分享", link_share_entity=link_share_entity)
    pipeline = Pipeline(settings)
    return await pipeline.open_wiki_pipeline(link_share_entity)


async def _deploy_fix_bitable(settings: Settings) -> Dict[str, Any]:
    """给已存在 bitable 的单选字段补上选项。"""
    logger.info("开始修复 bitable 单选选项")
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    return await pipeline.fix_bitable_pipeline(app_token)


async def _deploy_archive(settings: Settings, purge_immediately: bool = False) -> Dict[str, Any]:
    """飞书附件 → OSS 归档。"""
    logger.info("开始 OSS 归档", purge_immediately=purge_immediately)
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    return await pipeline.archive_pipeline(app_token, purge_immediately=purge_immediately)


async def _deploy_purge_archived(settings: Settings, older_than_days: int = 7) -> Dict[str, Any]:
    """清理归档超期的飞书原件。"""
    logger.info("开始安全期清理", older_than_days=older_than_days)
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    return await pipeline.purge_archived_pipeline(app_token, older_than_days=older_than_days)


async def _deploy_reset_bitable(settings: Settings) -> Dict[str, Any]:
    """清空 bitable 三张表所有记录（不可逆）。"""
    logger.warning("即将清空 bitable（不可逆）")
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    return await pipeline.reset_bitable_pipeline(app_token)


async def _deploy_seed_course(settings: Settings, *,
                                name: str = None, semester: str = None,
                                course_type: str = None, exam: str = None,
                                teacher: str = "",
                                from_file: str = None) -> Dict[str, Any]:
    """录课程到主数据表（单条参数或 --from-file 批量）。"""
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    return await pipeline.seed_course_pipeline(
        app_token, name=name, semester=semester,
        course_type=course_type, exam=exam, teacher=teacher,
        from_file=from_file,
    )


async def _deploy_seed_materials(settings: Settings, local_dir: str,
                                   course_name: str, *,
                                   contributor: str = "管理员",
                                   grade: str = "",
                                   material_type: str = "其他",
                                   reason: str = "") -> Dict[str, Any]:
    """批量录入 raw 学习资料。"""
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    return await pipeline.seed_materials_pipeline(
        app_token, local_dir, course_name,
        contributor=contributor, grade=grade,
        material_type=material_type, reason=reason,
    )


async def _deploy_ocr_materials(settings: Settings) -> Dict[str, Any]:
    """OCR + 摘要（OSS → PDF → OCR → 摘要 → 飞书 drive + 回填）。"""
    logger.info("开始 OCR 流程")
    pipeline = Pipeline(settings)
    return await pipeline.ocr_materials_pipeline()


async def _deploy_full(settings: Settings, year_filter: Optional[str] = None) -> Dict[str, Any]:
    logger.info("开始完整部署", year_filter=year_filter)
    rollback_manager = RollbackManager()
    feishu = FeishuAdapter(settings)
    try:
        wiki_result = await _deploy_wiki(settings, year_filter=year_filter)
        if wiki_result.get("status") == "error":
            raise Exception(f"知识库创建失败: {wiki_result.get('message')}")
        space_id = wiki_result["space_id"]
        rollback_manager.record_wiki_space(space_id, settings.wiki_space_name)

        table_result = await _deploy_tables(settings, year_filter=year_filter)
        doc_result = await _deploy_docs(settings, limit=None, year_filter=year_filter)
        material_result = await _deploy_materials(settings)
        link_result = await _deploy_links(settings, doc_result.get("course_to_doc_map", {}),
                                          year_filter=year_filter)

        logger.info("完整部署完成")
        return {
            "space_id": space_id,
            "wiki_result": wiki_result,
            "table_result": table_result,
            "doc_result": doc_result,
            "material_result": material_result,
            "link_result": link_result,
            "rollback_summary": rollback_manager.get_rollback_summary()
        }
    except Exception as e:
        logger.error("部署失败，开始回滚", error=str(e))
        rollback_result = await rollback_manager.rollback_all(feishu)
        await feishu.close()
        return {"status": "failed", "error": str(e), "rollback_result": rollback_result}
    finally:
        await feishu.close()


_MODE_HANDLERS = {
    "wiki": lambda s, a: _deploy_wiki(s, year_filter=a.year_filter),
    "tables": lambda s, a: _deploy_tables(s, year_filter=a.year_filter),
    "docs": lambda s, a: _deploy_docs(s, limit=a.limit, year_filter=a.year_filter),
    "upload": lambda s, a: _deploy_materials(s),
    "link": lambda s, a: _deploy_links(s, course_to_doc_map=a.course_to_doc_map,
                                        year_filter=a.year_filter),
    "ocr": lambda s, a: _deploy_ocr(s),
    "catalog": lambda s, a: _deploy_catalog(s),
    "sync-form": lambda s, a: _deploy_sync_form(s),
    "init-bitable": lambda s, a: _deploy_init_bitable(s),
    "fix-bitable": lambda s, a: _deploy_fix_bitable(s),
    "reset-bitable": lambda s, a: _deploy_reset_bitable(s),
    "seed-course": lambda s, a: _deploy_seed_course(
        s, name=a.name, semester=a.semester, course_type=a.course_type,
        exam=a.exam, teacher=a.teacher, from_file=a.from_file),
    "seed-materials": lambda s, a: _deploy_seed_materials(
        s, a.local_dir, a.course_name,
        contributor=a.contributor, grade=a.grade,
        material_type=a.material_type, reason=a.reason),
    "ocr-materials": lambda s, a: _deploy_ocr_materials(s),
    "archive-materials": lambda s, a: _deploy_archive(s, purge_immediately=a.purge_immediately),
    "purge-archived": lambda s, a: _deploy_purge_archived(s, older_than_days=a.older_than_days),
    "full": lambda s, a: _deploy_full(s, year_filter=a.year_filter),
    "sync": lambda s, a: _deploy_sync(s),
}


async def deploy_mode(settings: Settings, args: DeployArgs) -> Dict[str, Any]:
    """按模式调度部署"""
    handler = _MODE_HANDLERS.get(args.mode)
    if not handler:
        logger.error("未知的部署模式", mode=args.mode)
        return {"status": "error", "message": f"未知的部署模式: {args.mode}"}
    return await handler(settings, args)
