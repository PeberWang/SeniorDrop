# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 知识库服务
只创建 4 个学年 docx 节点，不创建 per-course 节点（课程通过内嵌表格导航）。
"""

import structlog
from typing import Dict, List

from libs.feishu import FeishuAdapter
from config.course_schema import WIKI_YEAR_NODES

logger = structlog.get_logger()


class WikiService:
    """知识库服务"""

    def __init__(self, feishu: FeishuAdapter):
        self.feishu = feishu

    async def get_space_by_name(self, space_name: str) -> Dict[str, str]:
        """查找已有知识空间，未找到返回空 space_id。"""
        spaces = await self.feishu.list_wiki_spaces()
        for space in spaces:
            if space.get("name") == space_name:
                logger.info("找到已有知识空间", space_id=space["space_id"])
                return {"space_id": space["space_id"]}
        logger.warning("未找到知识空间", space_name=space_name)
        return {"space_id": ""}

    async def create_space(self, space_name: str) -> Dict[str, str]:
        logger.info("创建知识空间", space_name=space_name)
        return await self.feishu.create_wiki_space(space_name)

    async def build_year_nodes(self, space_id: str, years: List[str] = None) -> Dict[str, Dict]:
        """在 space_id 下创建学年 docx 节点，返回 {年级: {node_id, obj_token, url}}。"""
        years = years or WIKI_YEAR_NODES
        results = {}
        for year in years:
            node = await self.feishu.create_wiki_node(space_id=space_id, parent_node_id="", title=year)
            results[year] = {"node_id": node["node_id"], "obj_token": node["obj_token"], "url": node["url"]}
            logger.info("学年节点创建成功", year=year, node_id=node["node_id"], obj_token=node["obj_token"])
        return results

    async def attach_bitable_to_year(self, space_id: str, year_node_id: str,
                                      year: str, bitable_token: str, table_id: str) -> Dict:
        """[已废弃] 在学年 wiki 节点下挂载 bitable shortcut 子节点。

        导航表已迁移到 docx 原生表格（block_type=31），不再需要此方法。
        保留作为 fallback。bitable 仍用于表单收集（sync-form）。
        """
        title = f"{year}课程导航"
        result = await self.feishu.create_wiki_bitable_node(
            space_id=space_id,
            parent_node_token=year_node_id,
            title=title,
            bitable_token=bitable_token,
        )
        logger.info("多维表格已挂载到知识库节点", year=year, table_id=table_id, wiki_node=result["node_id"])
        return result

    async def get_wiki_structure(self, space_id: str) -> Dict:
        try:
            info = await self.feishu.get_wiki_space_info(space_id)
            return {"space_id": space_id, "space_info": info}
        except Exception as e:
            logger.error("获取知识库结构失败", space_id=space_id, error=str(e))
            raise
