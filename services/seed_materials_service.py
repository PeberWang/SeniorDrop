# -*- coding: utf-8 -*-
"""批量录入 raw 资料服务 — 扫本地文件夹，每个文件上传飞书 drive + 建一条资料表记录。

用途：首次部署 / 管理员批量录入历史资料。
模拟学生通过表单逐个上传的行为：每文件一条独立 bitable 记录，附件字段填 file_token。

不做格式判断：Excel / Word / PDF / PPT / zip 全部原样上传。
格式相关的处理（转 PDF、OCR）由 ocr-materials 命令负责。
"""

import os
import structlog
from pathlib import Path
from typing import Dict, Any, List

from libs.feishu import FeishuAdapter
from services.sync_service import SyncService

logger = structlog.get_logger()

# 跳过这些隐藏文件 / 系统文件
_SKIP_NAMES = {".DS_Store", "Thumbs.db", ".gitkeep", "__MACOSX"}
_SKIP_SUFFIXES = {".tmp", ".crdownload"}


def _is_skippable(path: Path) -> bool:
    if path.name in _SKIP_NAMES:
        return True
    if path.suffix.lower() in _SKIP_SUFFIXES:
        return True
    # 跳过 __MACOSX 目录里的所有文件
    if "__MACOSX" in path.parts:
        return True
    return False


def scan_files(local_dir: str) -> List[Path]:
    """递归扫描目录，返回所有可上传文件路径。"""
    root = Path(local_dir)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"目录不存在或不是目录: {local_dir}")

    files = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and not _is_skippable(p):
            files.append(p)
    return files


class SeedMaterialsService:
    """批量录入 raw 资料到飞书 drive + 资料管理表。"""

    def __init__(self, feishu: FeishuAdapter, sync: SyncService):
        self.feishu = feishu
        self.sync = sync

    async def seed_from_dir(self, app_token: str, local_dir: str,
                             course_name: str, contributor: str = "管理员",
                             grade: str = "", material_type: str = "其他",
                             reason: str = "") -> Dict[str, Any]:
        """扫目录上传所有文件 + 建资料表记录。

        Args:
            app_token: bitable app token
            local_dir: 本地资料目录（递归扫描）
            course_name: 关联课程名（必须在课程主数据表中存在，否则 sync 阶段被门控）
            contributor: 贡献者署名（默认"管理员"）
            grade: 届别（如 "22级"，可空）
            material_type: 资料类型（PPT/笔记/真题/教材/...，默认"其他"）
            reason: 推荐理由（一条 reason 对应当前批次所有文件，符合"一对多"方案）

        Returns:
            {scanned, uploaded, failed, details, errors}
        """
        files = scan_files(local_dir)
        logger.info("扫描目录完成", dir=local_dir, count=len(files))

        results, errors = [], []
        for path in files:
            try:
                upload = await self.feishu.upload_file(str(path))
                file_token = upload["file_key"]
                rec = await self.sync.add_material_record(
                    app_token,
                    course_name=course_name,
                    contributor=contributor,
                    grade=grade,
                    material_type=material_type,
                    reason=reason,
                    file_token=file_token,
                    file_name=path.name,
                )
                results.append({
                    "file": str(path),
                    "file_token": file_token,
                    "record_id": rec["record_id"],
                })
                logger.info("文件已录入", file=path.name, course=course_name,
                            record_id=rec["record_id"])
            except Exception as e:
                logger.error("文件录入失败", file=str(path), error=str(e))
                errors.append({"file": str(path), "error": str(e)})

        logger.info("批量录入完成",
                    scanned=len(files), uploaded=len(results), failed=len(errors))
        return {
            "scanned": len(files),
            "uploaded": len(results),
            "failed": len(errors),
            "details": results[:5],
            "errors": errors[:5],
        }
