# -*- coding: utf-8 -*-
"""
数据结构适配器
封装 pandas/openpyxl，提供统一的文件读取接口
"""

import structlog
import json
from pathlib import Path
from typing import Any
import pandas as pd

from libs.exceptions import ConfigurationException

logger = structlog.get_logger()


def read_json(path: Path) -> Any:
    """读取 JSON 文件（UTF-8）。文件不存在返回 None。"""
    path = Path(path)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """写入 JSON 文件（UTF-8, LF, 缩进2, 保留中文）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class DataAdapter:
    """数据文件适配器"""

    @staticmethod
    def read_excel(file_path: str, sheet_name: str = None) -> pd.DataFrame:
        """读取 Excel 文件"""
        try:
            kwargs = {}
            if sheet_name:
                kwargs["sheet_name"] = sheet_name
            else:
                kwargs["engine"] = "openpyxl"
            df = pd.read_excel(file_path, **kwargs)
            logger.info("读取Excel成功", path=file_path, rows=len(df))
            return df
        except Exception as e:
            logger.error("读取Excel失败", path=file_path, error=str(e))
            raise ConfigurationException(f"读取Excel失败: {str(e)}")

    @staticmethod
    def read_csv(file_path: str, encoding: str = "utf-8") -> pd.DataFrame:
        """读取 CSV 文件"""
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            logger.info("读取CSV成功", path=file_path, rows=len(df))
            return df
        except Exception as e:
            logger.error("读取CSV失败", path=file_path, error=str(e))
            raise ConfigurationException(f"读取CSV失败: {str(e)}")

    @staticmethod
    def read_file(file_path: str) -> pd.DataFrame:
        """自动检测文件类型读取"""
        ext = file_path.lower()
        if ext.endswith(".xlsx") or ext.endswith(".xls"):
            return DataAdapter.read_excel(file_path)
        elif ext.endswith(".csv"):
            return DataAdapter.read_csv(file_path)
        else:
            raise ConfigurationException(f"不支持的文件格式: {file_path}")
