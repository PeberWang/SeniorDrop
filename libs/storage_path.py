# -*- coding: utf-8 -*-
"""三层储存 key 命名规范 — 纯函数，无副作用。

阿里云 OSS 存原始资料和 OCR 全文，key 遵循统一命名以便检索。
"""


def raw_material_key(course_name: str, filename: str) -> str:
    """资料原件 OSS key：raw/{课程名}/{文件名}"""
    safe_course = course_name.replace(" ", "_")
    return f"raw/{safe_course}/{filename}"


def ocr_text_key(material_name: str) -> str:
    """OCR 全文 OSS key：ocr/{资料名}_ocr.md"""
    safe_name = material_name.replace(" ", "_")
    return f"ocr/{safe_name}_ocr.md"


def summary_key(material_name: str) -> str:
    """LLM 摘要本地/飞书文件名：{资料名}.md（用于 summary_dir）"""
    safe_name = material_name.replace(" ", "_")
    return f"{safe_name}.md"
