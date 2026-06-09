# -*- coding: utf-8 -*-
"""飞书 docx 块构建器 —— 纯函数，返回 lark-oapi Block 对象（无副作用、不调 API）。

block_type 编号（飞书 docx）：2 正文 / 3-5 标题h1-h3 / 12 无序列表 / 22 分割线 /
  18 内嵌多维表格 / 31 表格 / 32 表格行 / 33 表格单元格。
"""

import uuid

from lark_oapi.api.docx.v1 import (
    Block, Text, TextElement, TextRun, Divider, Bitable,
    Table, TableProperty, TableCell,
)

_HEADING_BUILDER = {1: ("heading1", 3), 2: ("heading2", 4), 3: ("heading3", 5)}


def _text_model(content: str) -> Text:
    """单 run 的 Text 内容模型，供正文 / 标题 / 列表复用。"""
    return (Text.builder()
            .elements([TextElement.builder()
                       .text_run(TextRun.builder().content(content).build())
                       .build()])
            .build())


def text(content: str) -> Block:
    """正文段落。"""
    return Block.builder().block_type(2).text(_text_model(content)).build()


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
    return (Block.builder()
            .block_type(18)
            .bitable(Bitable.builder()
                     .token(f"{app_token}_{table_id}")
                     .view_type(view_type)
                     .build())
            .build())


# ------------------------------------------------------------------
# 原生表格构建器（block_type=31，通过 descendant API 创建）
# ------------------------------------------------------------------

def _cell_block(text_content: str, block_id: str) -> Block:
    """构建单个表格单元格 Block（block_type=33，含正文子块）。"""
    text_block = Block.builder().block_type(2).block_id(uuid.uuid4().hex) \
        .text(_text_model(text_content)).build()
    return (Block.builder()
            .block_type(33)
            .block_id(block_id)
            .table_cell(TableCell.builder().build())
            .children([text_block])
            .build())


def table(headers: list, rows: list, header_row: bool = True,
          column_widths: list = None) -> Block:
    """构建 docx 原生表格块（block_type=31），通过 descendant API 写入文档。

    headers: 列标题文本列表
    rows: 数据行，每行是文本列表（与 headers 等长）
    header_row: 首行是否渲染为表头样式
    column_widths: 可选列宽列表（像素），如 [200, 300, 150]

    返回的 Block 可直接传给 DocxTableMixin.create_descendant()。
    """
    ncols = len(headers)
    all_rows = [headers] + rows
    table_block_id = uuid.uuid4().hex
    cell_ids: list[str] = []
    row_blocks: list[Block] = []

    for row_data in all_rows:
        row_cells: list[Block] = []
        for cell_text in row_data:
            cid = uuid.uuid4().hex
            cell_ids.append(cid)
            row_cells.append(_cell_block(str(cell_text), cid))
        row_block = (Block.builder()
                     .block_type(32)
                     .block_id(uuid.uuid4().hex)
                     .children(row_cells)
                     .build())
        row_blocks.append(row_block)

    prop = TableProperty.builder().column_size(ncols).row_size(len(all_rows))
    if header_row:
        prop = prop.header_row(True)
    if column_widths:
        prop = prop.column_width(column_widths)

    return (Block.builder()
            .block_type(31)
            .block_id(table_block_id)
            .table(Table.builder().property(prop.build()).cells(cell_ids).build())
            .children(row_blocks)
            .build())


def nav_table(courses) -> Block:
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
