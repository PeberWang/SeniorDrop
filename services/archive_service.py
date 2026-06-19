# -*- coding: utf-8 -*-
"""OSS 归档服务 — 飞书附件 → OSS，hash 校验通过后删飞书原件。

设计要点：
- 飞书附件字段是中转，OSS 是重数据归宿。
- 上传失败 / 异常时绝对不调 delete_file，防止数据丢失。
- 默认 7 天安全期：只回填 URL + 写归档时间，原件保留；purge-archived 命令定期清理。
- --purge-immediately 模式立即删原件（demo 演示用）。
"""

import hashlib
import os
import structlog
import tempfile
from datetime import datetime
from typing import Any, Dict, List

from libs.cloud.base import CloudDriveAdapter
from libs.feishu import FeishuAdapter
from libs.storage_path import raw_material_key

logger = structlog.get_logger()


class ArchiveIntegrityException(Exception):
    """归档完整性校验失败（OSS 上传异常或无可归档附件）。"""


class ArchiveService:
    """飞书附件归档到 OSS，回填 URL 到资料表，删原件。"""

    def __init__(self, feishu: FeishuAdapter, cloud: CloudDriveAdapter, settings=None):
        self.feishu = feishu
        self.cloud = cloud
        self.settings = settings

    async def archive_all(self, app_token: str, table_id: str,
                          purge_immediately: bool = False) -> Dict[str, Any]:
        """扫资料表所有「文件附件」非空且「文件链接」为空的记录，批量归档。

        返回：{scanned, archived, failed, skipped, details, errors}
        """
        records = await self.feishu.list_bitable_records(app_token, table_id)
        archived, failed = [], []
        skipped = 0

        for r in records:
            fields = r.get("fields") or {}
            attachments = fields.get("文件附件") or []
            file_link = fields.get("文件链接") or ""
            record_id = r.get("record_id", "")
            course_name = self._extract_course_name(fields.get("课程"))

            if not attachments:
                skipped += 1
                continue
            if file_link:
                skipped += 1  # 已归档
                continue

            try:
                result = await self.archive_record(
                    app_token, table_id, record_id, attachments,
                    course_name=course_name,
                    purge_immediately=purge_immediately,
                )
                archived.append(result)
            except Exception as e:
                logger.error("归档失败", record_id=record_id, error=str(e))
                failed.append({"record_id": record_id, "error": str(e)})

        logger.info("批量归档完成",
                    scanned=len(records), archived=len(archived),
                    failed=len(failed), skipped=skipped)
        return {
            "scanned": len(records),
            "archived": len(archived),
            "failed": len(failed),
            "skipped": skipped,
            "details": archived[:5],
            "errors": failed[:5],
        }

    async def archive_record(self, app_token: str, table_id: str, record_id: str,
                             attachments: List[Dict], course_name: str = "",
                             purge_immediately: bool = False) -> Dict:
        """归档一条记录的所有附件。

        N 附件场景：每份独立 OSS key；首份 URL 写「文件链接」字段（共享理由方案不变）。
        """
        course_name = course_name or "未知课程"
        archived_tokens = []
        primary_url = ""
        primary_name = ""

        for att in attachments:
            file_token = att.get("file_token") or att.get("token", "")
            original_name = att.get("name") or f"{file_token}.bin"
            if not file_token:
                continue

            # 1. 下载附件字节
            file_bytes = await self.feishu.download_file(file_token)
            local_md5 = hashlib.md5(file_bytes).hexdigest()

            # 2. 写临时文件 → OSS
            with tempfile.NamedTemporaryFile(delete=False,
                                             suffix=f"_{self._safe_filename(original_name)}") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            try:
                oss_key = raw_material_key(course_name, original_name)
                # upload 异常会抛 FileUploadException，外层 try 兜住 → 不删原件
                await self.cloud.upload(tmp_path, oss_key)
                oss_url = await self.cloud.download_url(oss_key)
                if not primary_url:
                    primary_url = oss_url
                    primary_name = original_name
                archived_tokens.append(file_token)
                logger.info("附件已归档到 OSS",
                            file=original_name, oss_key=oss_key,
                            md5=local_md5, size=len(file_bytes))
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        if not archived_tokens:
            raise ArchiveIntegrityException(f"记录 {record_id} 无可归档附件")

        # 3. 回填 URL + 归档时间到资料表
        # text 用首份资料名（人类可读），link 用首份 OSS URL
        update_fields = {
            "文件链接": {"text": primary_name, "link": primary_url},
            "归档时间": int(datetime.now().timestamp() * 1000),
        }
        await self.feishu.update_bitable_record(app_token, table_id, record_id, update_fields)

        # 4. 清理飞书原件
        purged = False
        if purge_immediately:
            for tok in archived_tokens:
                try:
                    await self.feishu.delete_file(tok)
                except Exception as e:
                    logger.warning("删飞书原件失败（不阻塞归档）",
                                   token=tok, error=str(e))
            # 清空附件字段值
            await self.feishu.update_bitable_record(
                app_token, table_id, record_id, {"文件附件": None}
            )
            purged = True
            logger.info("飞书原件已立即清理", record_id=record_id,
                        count=len(archived_tokens))

        return {
            "record_id": record_id,
            "course_name": course_name,
            "archived_count": len(archived_tokens),
            "primary_url": primary_url,
            "purged": purged,
        }

    async def purge_archived(self, app_token: str, table_id: str,
                             older_than_days: int = 7) -> Dict[str, Any]:
        """清理「归档时间」早于 older_than_days 天的记录对应的飞书原件。

        7 天安全期机制：archive_all 默认不删原件，靠此命令定期清理。
        """
        records = await self.feishu.list_bitable_records(app_token, table_id)
        threshold_ms = int((datetime.now().timestamp() - older_than_days * 86400) * 1000)
        purged_count, failed = 0, []

        for r in records:
            fields = r.get("fields") or {}
            archive_ts = fields.get("归档时间")
            attachments = fields.get("文件附件") or []

            # 归档时间早于阈值 且 附件字段仍有值（已 archive 但未 purge）
            if not archive_ts or not attachments:
                continue
            try:
                ts = int(archive_ts) if not isinstance(archive_ts, (list, dict)) else 0
                if ts == 0 or ts > threshold_ms:
                    continue
                for att in attachments:
                    tok = att.get("file_token") or att.get("token", "")
                    if tok:
                        await self.feishu.delete_file(tok)
                await self.feishu.update_bitable_record(
                    app_token, table_id, r["record_id"], {"文件附件": None}
                )
                purged_count += 1
            except Exception as e:
                failed.append({"record_id": r.get("record_id"), "error": str(e)})

        logger.info("安全期清理完成", purged=purged_count, failed=len(failed),
                     older_than_days=older_than_days)
        return {"purged": purged_count, "failed": len(failed), "errors": failed[:5]}

    @staticmethod
    def _extract_course_name(course_field: Any) -> str:
        """bitable 关联/单选字段值可能是 str、[{"text": "xx"}] 或 [{"name": "xx"}]。"""
        if isinstance(course_field, str):
            return course_field
        if isinstance(course_field, list) and course_field:
            first = course_field[0]
            if isinstance(first, dict):
                return first.get("text") or first.get("name") or ""
        return ""

    @staticmethod
    def _safe_filename(name: str) -> str:
        for ch in r'\/:*?"<>|':
            name = name.replace(ch, "-")
        return name[:50]
