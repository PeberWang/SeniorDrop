# -*- coding: utf-8 -*-
"""飞书云文档(Docx)模块 - 基于 lark-oapi SDK"""

import asyncio
from typing import Dict, Any, List
from lark_oapi.api.docx.v1 import (
    CreateDocumentRequest, CreateDocumentRequestBody,
    CreateDocumentBlockChildrenRequest, CreateDocumentBlockChildrenRequestBody,
    Block,
)
from libs.feishu.blocks import bitable_embed
from libs.exceptions import FeishuAPIException


class DocxMixin:
    """云文档操作"""

    async def create_docx(self, title: str, folder_token: str = "") -> Dict[str, str]:
        """在云空间创建独立文档（folder_token 为空则建在我的空间根目录）。"""
        builder = CreateDocumentRequestBody.builder().title(title)
        if folder_token:
            builder = builder.folder_token(folder_token)
        request = CreateDocumentRequest.builder().request_body(builder.build()).build()
        resp = await self.client.docx.v1.document.acreate(request)
        if not resp.success():
            raise FeishuAPIException(f"创建云文档[{title}]失败: {resp.msg}", error_code=str(resp.code))
        doc = resp.data.document
        doc_id = doc.document_id
        url = f"https://{self.settings.feishu_doc_host}/docx/{doc_id}"
        return {"doc_id": doc_id, "title": doc.title or title, "url": url}

    async def append_blocks(self, doc_id: str, blocks: List[Block], index: int = 0, batch_size: int = 50) -> int:
        """按批把块追加到文档（分批避免频率限制）。

        index = -1 表示末尾追加；其他值表示精确插入位置。
        返回下一个空闲 index（末尾追加模式保持 -1，避免后续 create_descendant_tree
        误用 N-1 把已写块往后挤、打乱 heading 与 table 的相对顺序）。
        """
        idx = index
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i + batch_size]
            body = (CreateDocumentBlockChildrenRequestBody.builder()
                    .children(batch).index(idx).build())
            request = (CreateDocumentBlockChildrenRequest.builder()
                       .document_id(doc_id).block_id(doc_id)
                       .request_body(body).build())
            resp = await self.client.docx.v1.document_block_children.acreate(request)
            if not resp.success():
                raise FeishuAPIException(f"写入文档块失败: {resp.msg}", error_code=str(resp.code))
            if idx != -1:
                idx += len(batch)
            if i + batch_size < len(blocks):
                await asyncio.sleep(0.5)
        return idx

    async def embed_bitable(self, doc_id: str, app_token: str, table_id: str,
                            index: int = 0, view_type: int = 1) -> Dict[str, Any]:
        """[已废弃] 在文档中内嵌多维表格（block_type=18）。

        block_type=18 在所有参数组合下均失败（错误码 1770001）。
        请使用 DocxTableMixin.create_descendant() + blocks.table() 原生表格替代。
        此方法保留作为 fallback 参考。
        """
        block = bitable_embed(app_token, table_id, view_type)
        body = (CreateDocumentBlockChildrenRequestBody.builder()
                .children([block]).index(index).build())
        request = (CreateDocumentBlockChildrenRequest.builder()
                   .document_id(doc_id).block_id(doc_id)
                   .request_body(body).build())
        resp = await self.client.docx.v1.document_block_children.acreate(request)
        if not resp.success():
            raise FeishuAPIException(f"内嵌多维表格失败: {resp.msg}", error_code=str(resp.code))
        return {"doc_id": doc_id, "index": index + 1}
