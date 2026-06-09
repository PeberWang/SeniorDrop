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
from config.course_schema import get_all_courses, get_courses_by_year
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
    """部署参数"""
    mode: str
    limit: Optional[int] = None
    incremental: bool = False
    course_to_doc_map: Optional[Dict[str, str]] = None
    space_id: Optional[str] = None
    import_config: Optional[str] = None


async def _deploy_wiki(settings: Settings) -> Dict[str, Any]:
    logger.info("开始部署知识库")
    pipeline = Pipeline(settings)
    # 先查找已有空间，避免创建时触发需要 user_access_token 的权限检查
    feishu = FeishuAdapter(settings)
    from services.wiki_service import WikiService
    wiki = WikiService(feishu)
    existing = await wiki.get_space_by_name(settings.wiki_space_name)
    await feishu.close()
    if existing["space_id"]:
        logger.info("找到已有知识空间，直接使用", space_id=existing["space_id"])
        return await pipeline.wiki_pipeline(space_id=existing["space_id"], space_name=None)
    return await pipeline.wiki_pipeline(space_id=None, space_name=settings.wiki_space_name)


async def _deploy_tables(settings: Settings) -> Dict[str, Any]:
    logger.info("开始独立部署多维表格（全量）")
    app_token = await _resolve_app_token(settings)
    pipeline = Pipeline(settings)
    course_data = CourseDataService(settings)
    all_results = []
    for year in ["大一", "大二", "大三", "大四"]:
        courses = await course_data.get_by_year(year, app_token)
        if courses:
            result = await pipeline.table_pipeline(app_token=app_token, year=year, courses=courses)
            all_results.append(result)
    return {"results": all_results}


async def _deploy_docs(settings: Settings, limit: int = None) -> Dict[str, Any]:
    logger.info("开始部署云文档", limit=limit)
    pipeline = Pipeline(settings)
    course_data = CourseDataService(settings)
    app_token = await _resolve_app_token(settings)
    all_courses = await course_data.get_all(app_token)
    result = await pipeline.doc_pipeline(space_id=None, courses=all_courses, limit=limit)
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


async def _deploy_links(settings: Settings, course_to_doc_map: Dict[str, str] = None) -> Dict[str, Any]:
    logger.info("开始关联表格与文档")
    pipeline = Pipeline(settings)
    return await pipeline.link_pipeline(course_to_doc_map=course_to_doc_map)


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


async def _deploy_full(settings: Settings) -> Dict[str, Any]:
    logger.info("开始完整部署")
    rollback_manager = RollbackManager()
    feishu = FeishuAdapter(settings)
    try:
        wiki_result = await _deploy_wiki(settings)
        if wiki_result.get("status") == "error":
            raise Exception(f"知识库创建失败: {wiki_result.get('message')}")
        space_id = wiki_result["space_id"]
        rollback_manager.record_wiki_space(space_id, settings.wiki_space_name)

        table_result = await _deploy_tables(settings)
        doc_result = await _deploy_docs(settings, limit=None)
        material_result = await _deploy_materials(settings)
        link_result = await _deploy_links(settings, doc_result.get("course_to_doc_map", {}))

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
    "wiki": lambda s, a: _deploy_wiki(s),
    "tables": lambda s, a: _deploy_tables(s),
    "docs": lambda s, a: _deploy_docs(s, limit=a.limit),
    "upload": lambda s, a: _deploy_materials(s),
    "link": lambda s, a: _deploy_links(s, course_to_doc_map=a.course_to_doc_map),
    "ocr": lambda s, a: _deploy_ocr(s),
    "catalog": lambda s, a: _deploy_catalog(s),
    "sync-form": lambda s, a: _deploy_sync_form(s),
    "full": lambda s, a: _deploy_full(s),
    "sync": lambda s, a: _deploy_sync(s),
}


async def deploy_mode(settings: Settings, args: DeployArgs) -> Dict[str, Any]:
    """按模式调度部署"""
    handler = _MODE_HANDLERS.get(args.mode)
    if not handler:
        logger.error("未知的部署模式", mode=args.mode)
        return {"status": "error", "message": f"未知的部署模式: {args.mode}"}
    return await handler(settings, args)
