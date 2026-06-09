# -*- coding: utf-8 -*-
"""PPE云端智能大礼包 - OCR 服务（三级存储链路）"""

import structlog
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from libs.feishu import FeishuAdapter
from libs.llm_adapter import LLMAdapter
from libs.cloud.base import CloudDriveAdapter
from libs.storage_path import raw_material_key, ocr_text_key, summary_key
from libs import ocr_adapter
from config.settings import Settings

logger = structlog.get_logger()


class OcrService:
    """三级存储链路：源文件 → 云盘 → OCR全文 → 云盘 → 摘要 → 飞书云盘。"""

    def __init__(self, feishu: FeishuAdapter, llm: LLMAdapter,
                 cloud: CloudDriveAdapter, settings: Settings):
        self.feishu = feishu
        self.llm = llm
        self.cloud = cloud
        self.settings = settings

    async def process_file(self, file_path: str, material_name: str) -> Dict[str, Any]:
        """处理单个 PDF：upload → OCR → upload OCR → summarize → upload summary。"""
        if not self.settings.glm_api_key:
            return {"status": "skipped", "reason": "未配置 GLM_API_KEY", "file": file_path}

        source_key = await self.cloud.upload(
            file_path, raw_material_key("", f"{material_name}.pdf"))
        logger.info("源文件已存入云盘", name=material_name, key=source_key)

        full_text = await ocr_adapter.run_ocr(
            file_path, self.settings.glm_api_key, self.settings.glm_ocr_url
        )

        self.settings.cloud_stub_dir.mkdir(parents=True, exist_ok=True)
        ocr_local = self.settings.cloud_stub_dir / ocr_text_key(material_name)
        ocr_local.write_text(full_text, encoding="utf-8")
        ocr_key = await self.cloud.upload(str(ocr_local), ocr_text_key(material_name))

        summary_text = await self.llm.summarize(full_text, title=material_name)

        self.settings.summary_dir.mkdir(parents=True, exist_ok=True)
        summary_path = self.settings.summary_dir / summary_key(material_name)
        summary_path.write_text(
            f"# {material_name}\n\n{summary_text}", encoding="utf-8"
        )

        upload_result = await self.feishu.upload_file(str(summary_path))
        logger.info("摘要已上传到飞书", name=material_name,
                    key=upload_result.get("file_key"))

        return {
            "status": "ok",
            "file": file_path,
            "source_key": source_key,
            "ocr_key": ocr_key,
            "summary_path": str(summary_path),
            "feishu_key": upload_result.get("file_key"),
        }

    async def process_all(self) -> Dict[str, Any]:
        """扫描 materials_base 下所有 PDF，逐一走三级存储链路。"""
        pdf_files = list(Path(self.settings.materials_base).glob("**/*.pdf"))
        if not pdf_files:
            return {"status": "skipped", "reason": "materials_base 下无 PDF 文件", "count": 0}

        results, errors = [], []
        for pdf_path in pdf_files:
            try:
                r = await self.process_file(str(pdf_path), pdf_path.stem)
                results.append(r)
            except Exception as e:
                logger.error("OCR 处理失败", file=str(pdf_path), error=str(e))
                errors.append({"file": str(pdf_path), "error": str(e)})

        return {
            "total": len(pdf_files),
            "success": len(results),
            "error_count": len(errors),
            "results": results,
            "errors": errors,
        }
