# -*- coding: utf-8 -*-
"""飞书 Docx 原生表格操作 Mixin — create_descendant / list_top_blocks / delete_blocks。

从 docx.py 中分离，保持每文件 <=100 行约束。通过 FeishuAdapter 多重继承组合。
"""

from typing import Dict, List

from lark_oapi.api.docx.v1 import (
    Block,
    CreateDocumentBlockDescendantRequest,
    CreateDocumentBlockDescendantRequestBody,
    ListDocumentBlockRequest,
    BatchDeleteDocumentBlockChildrenRequest,
    BatchDeleteDocumentBlockChildrenRequestBody,
)
from libs.exceptions import FeishuAPIException


class DocxTableMixin:
    """Docx 原生表格专用操作 — 需与 FeishuAdapter 组合使用（self.client 可用）。"""

    async def create_descendant(self, doc_id: str, block: Block, index: int = 0) -> int:
        """通过 descendant API 创建嵌套块（表格等），返回下一个空闲 index。

        与 append_blocks 的区别：append_blocks 只能创建平级子块；
        create_descendant 可一次创建完整嵌套树（表格→行→单元格→文本）。
        """
        body = (CreateDocumentBlockDescendantRequestBody.builder()
                .children_id(doc_id)
                .descendants([block])
                .index(index)
                .build())
        req = (CreateDocumentBlockDescendantRequest.builder()
               .document_id(doc_id).block_id(doc_id)
               .request_body(body)
               .build())
        resp = await self.client.docx.v1.document_block_descendant.acreate(req)
        if not resp.success():
            raise FeishuAPIException(f"创建嵌套块失败: {resp.msg}", error_code=str(resp.code))
        return index + 1

    async def list_top_blocks(self, doc_id: str, page_size: int = 50) -> List[Dict]:
        """列出文档顶层块，返回 [{block_id, block_type, parent_id}, ...] 简化列表。"""
        req = (ListDocumentBlockRequest.builder()
               .document_id(doc_id).page_size(page_size).build())
        resp = await self.client.docx.v1.document_block.alist(req)
        if not resp.success():
            raise FeishuAPIException(f"列出文档块失败: {resp.msg}", error_code=str(resp.code))
        items = resp.data.items or []
        return [
            {"block_id": item.block_id, "block_type": item.block_type,
             "parent_id": item.parent_id}
            for item in items
        ]

    async def delete_blocks(self, doc_id: str, start_index: int, end_index: int) -> None:
        """按 index 范围 [start, end) 删除文档根级块。"""
        body = (BatchDeleteDocumentBlockChildrenRequestBody.builder()
                .start_index(start_index).end_index(end_index).build())
        req = (BatchDeleteDocumentBlockChildrenRequest.builder()
               .document_id(doc_id).block_id(doc_id)
               .request_body(body).build())
        resp = await self.client.docx.v1.document_block_children.abatch_delete(req)
        if not resp.success():
            raise FeishuAPIException(f"批量删除块失败: {resp.msg}", error_code=str(resp.code))
