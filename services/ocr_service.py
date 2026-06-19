# -*- coding: utf-8 -*-
"""OCR 服务 — 从资料管理表扫已归档资料，OSS 下载，转 PDF（必要时），GLM-OCR 全文，LLM 摘要。

多格式处理：
  - PDF → 直接 GLM-OCR
  - Word/Excel/PPT → LibreOffice headless 转 PDF → GLM-OCR
  - zip → 解压临时目录 → 递归处理每个文件
  - 其他（图片等）→ 跳过 + 警告

输出：
  - 摘要 md → 飞书 drive（供知识助手问答）+ OSS（重数据）
  - 摘要文本 → 回填资料管理表「资料摘要」字段
  - OCR 全文 → OSS（重数据归档）

LibreOffice 依赖：
  - Windows 默认路径：C:\\Program Files\\LibreOffice\\program\\soffice.exe
  - macOS：/Applications/LibreOffice.app/Contents/MacOS/soffice
  - Linux：soffice 或 libreoffice（PATH 中）
  未安装时非 PDF 文件跳过 + 警告（README 必须说明依赖）。
"""

import asyncio
import os
import shutil
import structlog
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from libs.feishu import FeishuAdapter
from libs.llm_adapter import LLMAdapter
from libs.cloud.base import CloudDriveAdapter
from libs import ocr_adapter
from libs.storage_path import raw_material_key, ocr_text_key, summary_key
from config.settings import Settings

logger = structlog.get_logger()

COURSE_TABLE_NAME = "课程主数据表"
MATERIALS_TABLE_NAME = "资料管理表"

# 扩展名分类
_PDF_EXT = {".pdf"}
_OFFICE_EXT = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
_ZIP_EXT = {".zip", ".rar", ".7z"}
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def _find_soffice() -> Optional[str]:
    """查找 LibreOffice soffice 可执行文件路径，找不到返回 None。"""
    # 1. PATH 中查
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    # 2. Windows 默认安装路径
    win_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for p in win_paths:
        if os.path.exists(p):
            return p
    # 3. macOS 默认路径
    mac_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.exists(mac_path):
        return mac_path
    return None


async def _office_to_pdf(soffice_path: str, src_path: str,
                          out_dir: str, timeout: int = 120) -> str:
    """LibreOffice headless 转 PDF，返回 PDF 路径。"""
    cmd = [soffice_path, "--headless", "--convert-to", "pdf",
           "--outdir", out_dir, src_path]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"LibreOffice 转换超时（{timeout}s）：{src_path}")
    if proc.returncode != 0:
        raise RuntimeError(
            f"LibreOffice 转换失败 [{src_path}]: rc={proc.returncode} "
            f"stderr={stderr.decode('utf-8', errors='ignore')[:200]}"
        )
    pdf_name = Path(src_path).stem + ".pdf"
    pdf_path = os.path.join(out_dir, pdf_name)
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"LibreOffice 转换后未找到输出文件：{pdf_path}")
    return pdf_path


class OcrService:
    """从资料表扫已归档资料，转 PDF（必要时），GLM-OCR 全文，LLM 摘要。"""

    def __init__(self, feishu: FeishuAdapter, llm: LLMAdapter,
                 cloud: CloudDriveAdapter, settings: Settings):
        self.feishu = feishu
        self.llm = llm
        self.cloud = cloud
        self.settings = settings
        self._soffice = _find_soffice()
        if not self._soffice:
            logger.warning("未检测到 LibreOffice，非 PDF 文件将跳过 OCR。"
                           "请安装 LibreOffice（README 有说明）。")

    async def process_all(self) -> Dict[str, Any]:
        """扫资料表「文件链接」非空且「资料摘要」空的记录，逐一 OCR + 摘要。"""
        app_token = self.settings.bitable_app_token
        if not app_token:
            return {"status": "error", "message": "未配置 BITABLE_APP_TOKEN"}

        if not self.settings.glm_api_key:
            return {"status": "skipped", "reason": "未配置 GLM_API_KEY"}

        # 找资料表 table_id
        tables = await self.feishu.get_bitable_tables(app_token)
        name_to_id = {t["name"]: t["table_id"] for t in tables}
        table_id = name_to_id.get(MATERIALS_TABLE_NAME)
        if not table_id:
            return {"status": "error",
                    "message": f"未找到 {MATERIALS_TABLE_NAME}，请先 init-bitable"}

        records = await self.feishu.list_bitable_records(app_token, table_id)
        results, errors = [], []
        skipped = 0

        for r in records:
            fields = r.get("fields") or {}
            file_link = self._extract_url(fields.get("文件链接"))
            summary = self._select_text(fields.get("资料摘要"))
            record_id = r.get("record_id", "")
            course_name = self._select_text(fields.get("课程"))
            attachments = fields.get("文件附件") or []

            if not file_link:
                skipped += 1
                continue  # 未归档，跳过
            if summary:
                skipped += 1
                continue  # 已 OCR，跳过

            # 取首个附件名作为资料名
            file_name = ""
            if isinstance(attachments, list) and attachments:
                file_name = attachments[0].get("name") or ""

            try:
                result = await self.process_record(
                    app_token=app_token, table_id=table_id, record_id=record_id,
                    oss_url=file_link, file_name=file_name,
                    course_name=course_name,
                )
                results.append(result)
            except Exception as e:
                logger.error("OCR 处理失败", record_id=record_id, error=str(e))
                errors.append({"record_id": record_id, "error": str(e)})

        logger.info("批量 OCR 完成",
                    scanned=len(records), success=len(results),
                    errors=len(errors), skipped=skipped)
        return {
            "scanned": len(records),
            "success": len(results),
            "error_count": len(errors),
            "skipped": skipped,
            "results": results[:5],
            "errors": errors[:5],
        }

    async def process_record(self, app_token: str, table_id: str, record_id: str,
                              oss_url: str, file_name: str,
                              course_name: str = "") -> Dict[str, Any]:
        """处理单条记录：下载 → 转 PDF → OCR → 摘要 → 回填。"""
        course_name = course_name or "未知课程"
        safe_name = self._safe_filename(file_name or f"{record_id}.bin")
        ext = Path(safe_name).suffix.lower()

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. 从 OSS 下载源文件
            local_src = os.path.join(tmp_dir, safe_name)
            oss_key = self._extract_key_from_url(oss_url)
            await self._download_from_oss(oss_key, local_src)
            logger.info("源文件已从 OSS 下载", file=safe_name, size=os.path.getsize(local_src))

            # 2. 准备待 OCR 的 PDF 列表（zip 解压、Office 转 PDF）
            pdfs_to_ocr = await self._prepare_pdfs(local_src, tmp_dir, safe_name)
            if not pdfs_to_ocr:
                raise RuntimeError(f"无可 OCR 的 PDF：{safe_name}")

            # 3. 逐 PDF OCR + 拼接全文
            full_texts: List[str] = []
            for pdf_path in pdfs_to_ocr:
                text = await ocr_adapter.run_ocr(
                    pdf_path,
                    self.settings.glm_api_key,
                    self.settings.glm_ocr_url,
                )
                full_texts.append(text)
            full_text = "\n\n---\n\n".join(full_texts)

            # 4. LLM 摘要
            material_name = Path(safe_name).stem
            summary_text = await self.llm.summarize(full_text, title=material_name)

            # 5. OCR 全文存 OSS（重数据）
            ocr_local = os.path.join(tmp_dir, "ocr.md")
            with open(ocr_local, "w", encoding="utf-8") as f:
                f.write(full_text)
            ocr_key = ocr_text_key(f"{course_name}_{material_name}")
            await self.cloud.upload(ocr_local, ocr_key)

            # 6. 摘要存 OSS + 飞书 drive（轻数据）
            summary_local = os.path.join(tmp_dir, "summary.md")
            with open(summary_local, "w", encoding="utf-8") as f:
                f.write(f"# {material_name}\n\n{summary_text}")
            summary_oss_key = summary_key(f"{course_name}_{material_name}")
            summary_oss_path = os.path.join(tmp_dir, "summary_for_oss.md")
            shutil.copy(summary_local, summary_oss_path)
            await self.cloud.upload(summary_oss_path, summary_oss_key)
            # 飞书 drive 存一份（供知识助手问答）
            upload_result = await self.feishu.upload_file(summary_local)

            # 7. 回填资料表「资料摘要」字段（直接写文本）
            await self.feishu.update_bitable_record(
                app_token, table_id, record_id,
                {"资料摘要": summary_text}
            )

            logger.info("OCR + 摘要完成", record_id=record_id,
                        file=safe_name, summary_len=len(summary_text),
                        feishu_key=upload_result.get("file_key"))

            return {
                "status": "ok",
                "record_id": record_id,
                "file": safe_name,
                "ocr_key": ocr_key,
                "summary_oss_key": summary_oss_key,
                "feishu_key": upload_result.get("file_key"),
                "summary_chars": len(summary_text),
            }

    async def _prepare_pdfs(self, local_src: str, tmp_dir: str,
                              safe_name: str) -> List[str]:
        """根据扩展名准备待 OCR 的 PDF 列表。

        - PDF：直接返回 [local_src]
        - Office（Word/Excel/PPT）：LibreOffice 转 PDF
        - zip：解压到子目录，递归处理每个文件（合并所有 PDF）
        - 其他：返回空列表
        """
        ext = Path(safe_name).suffix.lower()

        if ext in _PDF_EXT:
            return [local_src]

        if ext in _OFFICE_EXT:
            if not self._soffice:
                logger.warning("LibreOffice 未安装，跳过 Office 文件 OCR", file=safe_name)
                return []
            try:
                out_dir = os.path.join(tmp_dir, "converted")
                os.makedirs(out_dir, exist_ok=True)
                pdf_path = await _office_to_pdf(self._soffice, local_src, out_dir)
                return [pdf_path]
            except Exception as e:
                logger.error("Office 转 PDF 失败", file=safe_name, error=str(e))
                return []

        if ext in _ZIP_EXT:
            extract_dir = os.path.join(tmp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            try:
                with zipfile.ZipFile(local_src, "r") as zf:
                    zf.extractall(extract_dir)
            except Exception as e:
                logger.error("zip 解压失败", file=safe_name, error=str(e))
                return []
            # 递归处理解压后的所有文件
            pdfs: List[str] = []
            for root, _, files in os.walk(extract_dir):
                for fn in files:
                    if fn.startswith(".") or fn.startswith("__MACOSX"):
                        continue
                    if fn.startswith("._"):
                        continue
                    sub_path = os.path.join(root, fn)
                    sub_pdfs = await self._prepare_pdfs(sub_path, tmp_dir, fn)
                    pdfs.extend(sub_pdfs)
            return pdfs

        if ext in _IMAGE_EXT:
            logger.warning("图片格式暂不支持 GLM-OCR（需 layout_parsing 接口），跳过",
                           file=safe_name)
            return []

        logger.warning("不支持的文件格式，跳过", file=safe_name, ext=ext)
        return []

    async def _download_from_oss(self, oss_key: str, local_path: str) -> None:
        """从 OSS 下载文件到本地。"""
        # oss2 同步接口，run_in_executor 包一层
        loop = asyncio.get_event_loop()

        def _sync_download():
            # OSS bucket 直接读字节到文件
            from libs.cloud.oss import AliyunOSSDrive  # noqa
            if not isinstance(self.cloud, AliyunOSSDrive):
                raise RuntimeError("OCR 服务仅支持 AliyunOSSDrive 后端")
            self.cloud.bucket.get_object_to_file(oss_key, local_path)

        await loop.run_in_executor(None, _sync_download)

    @staticmethod
    def _extract_key_from_url(url: str) -> str:
        """OSS URL → key（取 path 部分，去 leading /）。"""
        if not url:
            return ""
        from urllib.parse import urlparse
        path = urlparse(url).path
        return path.lstrip("/")

    @staticmethod
    def _extract_url(url_field: Any) -> str:
        """飞书 URL 字段（type 15）→ str link。"""
        if not url_field:
            return ""
        if isinstance(url_field, str):
            return url_field
        if isinstance(url_field, dict):
            return url_field.get("link") or url_field.get("text") or ""
        if isinstance(url_field, list) and url_field:
            first = url_field[0]
            if isinstance(first, dict):
                return first.get("link") or first.get("text") or ""
        return ""

    @staticmethod
    def _select_text(field_val: Any) -> str:
        """飞书单选/富文本字段值归一化为 str。"""
        if not field_val:
            return ""
        if isinstance(field_val, str):
            return field_val
        if isinstance(field_val, list) and field_val:
            first = field_val[0]
            if isinstance(first, dict):
                return first.get("text") or first.get("name") or ""
            return str(first)
        return str(field_val)

    @staticmethod
    def _safe_filename(name: str) -> str:
        for ch in r'\/:*?"<>|':
            name = name.replace(ch, "-")
        return name[:80]
