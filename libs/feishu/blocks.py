# -*- coding: utf-8 -*-
"""飞书 docx 块构建器 —— 纯函数，返回 lark-oapi Block 对象或 BlockTree（无副作用、不调 API）。

block_type 编号（飞书 docx，2026-06 FAQ 验证）：
  2 正文 / 3-5 标题h1-h3 / 12 无序列表 / 13 有序列表 / 22 分割线 /
  31 表格（property + cells） / 32 表格单元格（直接挂 table 下，无 row 概念）。

注意：早期代码用三层（table→row→cell, 32=行 33=单元格），与飞书 API 实际结构不符，
会触发 1770041 schema mismatch。FAQ 标准是两层（table→cell, 32=单元格）。
"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from lark_oapi.api.docx.v1 import (
    Block, Text, TextElement, TextRun, TextElementStyle, Link, Divider, Bitable,
)

_HEADING_BUILDER = {1: ("heading1", 3), 2: ("heading2", 4), 3: ("heading3", 5)}


@dataclass
class BlockTree:
    """嵌套块的完整 descendant 树（如原生表格）。

    调用方遇到 BlockTree 时用 create_descendant_tree 写入；
    普通 Block 仍用 append_blocks。write_mixed_blocks 自动分发。
    """
    top_id: str                       # 顶层 block_id（descendants 中的根，作为 children_id）
    descendants: List[Dict[str, Any]] = field(default_factory=list)  # FAQ 格式 dict 列表


def _text_run_model(content: str, link: Optional[str] = None) -> TextRun:
    """构造单个 text_run。link 非空时挂 text_element_style.link（飞书 docx 超链接标准结构）。"""
    builder = TextRun.builder().content(content)
    if link:
        style = (TextElementStyle.builder()
                 .link(Link.builder().url(link).build()).build())
        builder = builder.text_element_style(style)
    return builder.build()


def _text_model(content: str, link: Optional[str] = None) -> Text:
    """单 run 的 Text 内容模型，供正文 / 标题 / 列表复用。"""
    return (Text.builder()
            .elements([TextElement.builder()
                       .text_run(_text_run_model(content, link)).build()])
            .build())


def _text_model_runs(runs: List[Tuple[str, Optional[str]]]) -> Text:
    """多 run 的 Text 内容模型 —— 一个段落 block 含多个 text_run（部分带 link）。
    用于资料串讲段落：纯文本段 (text, None) + 资料名 (name, file_link) 交替。
    """
    elements = [TextElement.builder().text_run(_text_run_model(c, l)).build()
                for c, l in runs if c]
    return Text.builder().elements(elements).build()


def text(content: str, link: Optional[str] = None) -> Block:
    """正文段落（可选超链接，整段同链）。"""
    return Block.builder().block_type(2).text(_text_model(content, link)).build()


def text_runs(runs: List[Tuple[str, Optional[str]]]) -> Block:
    """正文段落（多 run，部分带 link）。用于串讲嵌入资料名超链接。"""
    return Block.builder().block_type(2).text(_text_model_runs(runs)).build()


def heading(content: str, level: int = 1) -> Block:
    """标题（level 1/2/3 → h1/h2/h3）。"""
    field, block_type = _HEADING_BUILDER.get(level, _HEADING_BUILDER[1])
    builder = Block.builder().block_type(block_type)
    builder = getattr(builder, field)(_text_model(content))
    return builder.build()


def bullet(content: str) -> Block:
    """无序列表项。"""
    return Block.builder().block_type(12).bullet(_text_model(content)).build()


def divider() -> Block:
    """分割线。"""
    return Block.builder().block_type(22).divider(Divider.builder().build()).build()


def bitable_embed(app_token: str, table_id: str, view_type: int = 1) -> Block:
    """内嵌多维表格块（block_type=18）。token 格式 {app_token}_{table_id}；view_type 1=表格视图。

    已废弃：block_type=18 在所有参数组合下均失败（错误码 1770001），
    请使用 table() 原生表格替代。此函数保留作为 fallback 参考。
    """
    from lark_oapi.api.docx.v1 import Bitable as BitableModel
    return (Block.builder()
            .block_type(18)
            .bitable(BitableModel.builder()
                     .token(f"{app_token}_{table_id}")
                     .view_type(view_type)
                     .build())
            .build())


# ------------------------------------------------------------------
# 原生表格构建器（block_type=31 + 32=cell，按 2026-06 FAQ 验证的两层结构）
# ------------------------------------------------------------------

def table(headers: list, rows: list, header_row: bool = True,
          column_widths: list = None) -> BlockTree:
    """构建 docx 原生表格（两层结构：table → cell），返回 BlockTree。

    headers: 列标题文本列表（同时也是第一行）
    rows: 数据行，每行是文本列表（与 headers 等长）
    header_row: 首行是否渲染为表头样式
    column_widths: 可选列宽列表（像素），如 [200, 300, 150]

    返回的 BlockTree 通过 DocxTableMixin.create_descendant_tree() 一次性写入文档。
    """
    ncols = len(headers)
    all_rows = [headers] + rows
    table_block_id = uuid.uuid4().hex
    cell_ids: List[str] = []
    descendants: List[Dict[str, Any]] = []

    for row_data in all_rows:
        for cell_data in row_data:
            # cell_data: str 或 (text, link) 元组（Download 列用元组埋超链接）
            if isinstance(cell_data, tuple):
                cell_text, cell_link = cell_data[0], cell_data[1]
            else:
                cell_text, cell_link = str(cell_data), None
            cid = uuid.uuid4().hex
            tid = uuid.uuid4().hex
            cell_ids.append(cid)
            # cell block（block_type=32，table 直接子节点）
            descendants.append({
                "block_id": cid,
                "block_type": 32,
                "table_cell": {},
                "children": [tid],
            })
            # cell 内的正文 block（支持 link：text_element_style.link.url）
            text_run: Dict[str, Any] = {"content": cell_text}
            if cell_link:
                text_run["text_element_style"] = {"link": {"url": cell_link}}
            descendants.append({
                "block_id": tid,
                "block_type": 2,
                "text": {"elements": [{"text_run": text_run}]},
                "children": [],
            })

    # table block（顶层，descendants[0]）
    property_dict: Dict[str, Any] = {
        "row_size": len(all_rows),
        "column_size": ncols,
    }
    if header_row:
        property_dict["header_row"] = True
    if column_widths:
        property_dict["column_width"] = column_widths

    table_block = {
        "block_id": table_block_id,
        "block_type": 31,
        "table": {"property": property_dict},
        "children": cell_ids,
    }
    descendants.insert(0, table_block)

    return BlockTree(top_id=table_block_id, descendants=descendants)


def nav_table(courses) -> BlockTree:
    """课程导航表（学年文档内嵌），含课程名称/教师/学期/类型/考试/资料数/学习指南。"""
    headers = ["课程名称", "授课老师", "开课学期", "课程类型", "考试形式", "资料数量", "学习指南"]
    rows = []
    for c in courses:
        rows.append([
            c.name,
            c.teacher or "",
            c.semester or "",
            c.type or "",
            c.exam or "",
            str(c.material_count),
            c.doc_url or "（待生成）",
        ])
    return table(headers, rows, header_row=True,
                 column_widths=[180, 120, 120, 100, 100, 80, 200])
