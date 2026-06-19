# -*- coding: utf-8 -*-
"""
PPE云端智能大礼包 - 表单数据导入服务
负责处理 Excel/CSV 文件的导入和数据映射
"""

import structlog
import os
import json
from typing import Dict, List, Optional, Any, Union
import pandas as pd

from libs.feishu import FeishuAdapter
from libs.data_adapter import DataAdapter
from config.settings import Settings

logger = structlog.get_logger()


class ImportService:
    """表单数据导入服务（Excel/CSV 批量导入到 bitable）"""

    def __init__(self, feishu: FeishuAdapter):
        """初始化服务"""
        self.feishu = feishu

    def read_excel_file(self, file_path: str, sheet_name: str = None) -> pd.DataFrame:
        """读取 Excel 文件"""
        return DataAdapter.read_excel(file_path, sheet_name)

    def read_csv_file(self, file_path: str, encoding: str = 'utf-8') -> pd.DataFrame:
        """读取 CSV 文件"""
        return DataAdapter.read_csv(file_path, encoding)

    def validate_course_data(self, df: pd.DataFrame, course_name_column: str = "课程名称") -> Dict[str, Any]:
        """验证课程数据格式（仅本地结构校验，不查 bitable）"""
        try:
            # 检查必需列
            required_columns = [course_name_column]
            for col in required_columns:
                if col not in df.columns:
                    raise ValueError(f"缺少必需列: {col}")

            # 检查数据完整性
            total_rows = len(df)
            empty_rows = df[course_name_column].isna().sum()
            valid_rows = total_rows - empty_rows

            # Excel 内部去重检查（不查 bitable，运行时门控由 sync 负责）
            all_names = df[course_name_column].dropna().tolist()
            seen, duplicates = set(), set()
            for name in all_names:
                if name in seen:
                    duplicates.add(name)
                seen.add(name)

            return {
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "empty_rows": empty_rows,
                "duplicate_courses": list(duplicates),
                "validation_passed": empty_rows == 0 and len(duplicates) == 0
            }

        except Exception as e:
            logger.error("验证课程数据失败", error=str(e))
            return {"validation_passed": False, "error": str(e)}

    def map_columns(self, df: pd.DataFrame, column_mapping: Dict[str, str]) -> pd.DataFrame:
        """映射列名到标准格式"""
        try:
            # 重命名列
            df_renamed = df.copy()
            for old_name, new_name in column_mapping.items():
                if old_name in df.columns:
                    df_renamed = df_renamed.rename(columns={old_name: new_name})
                    logger.info("列名映射", from_name=old_name, to_name=new_name)

            return df_renamed
        except Exception as e:
            logger.error("列名映射失败", error=str(e))
            raise

    async def import_to_bitable(
        self,
        app_token: str,
        df: pd.DataFrame,
        table_name: str,
        course_year_column: str = "学年",
        course_name_column: str = "课程名称",
        instructor_column: str = "授课教师",
        credits_column: str = "学分",
        course_type_column: str = "课程性质",
        is_incremental: bool = True
    ) -> Dict[str, Any]:
        """将数据导入到多维表格"""
        try:
            logger.info("开始导入数据到表格", table_name=table_name, rows=len(df))

            # 获取表格信息
            tables = await self.feishu.get_bitable_tables(app_token)
            target_table = None
            table_id = None

            # 查找目标表格
            for table in tables:
                if table["name"] == table_name:
                    target_table = table
                    table_id = table["table_id"]
                    break

            if not target_table:
                raise ValueError(f"未找到表格: {table_name}")

            logger.info("找到目标表格", table_id=table_id, table_name=table_name)

            results = []
            errors = []
            inserted_count = 0
            updated_count = 0

            # 按学年分组处理
            if course_year_column in df.columns:
                grouped = df.groupby(course_year_column)
                for year, group in grouped:
                    logger.info("处理学年", year=year, course_count=len(group))
                    result = await self._process_year_courses(
                        app_token,
                        table_id,
                        group,
                        year,
                        course_name_column,
                        instructor_column,
                        credits_column,
                        course_type_column,
                        is_incremental
                    )
                    results.extend(result["results"])
                    errors.extend(result["errors"])
                    inserted_count += result["inserted_count"]
                    updated_count += result["updated_count"]
            else:
                # 没有学年列，直接处理所有课程
                result = await self._process_year_courses(
                    app_token,
                    table_id,
                    df,
                    None,
                    course_name_column,
                    instructor_column,
                    credits_column,
                    course_type_column,
                    is_incremental
                )
                results.extend(result["results"])
                errors.extend(result["errors"])
                inserted_count = result["inserted_count"]
                updated_count = result["updated_count"]

            logger.info("数据导入完成", inserted_count=inserted_count, updated_count=updated_count, error_count=len(errors))
            return {
                "table_id": table_id,
                "table_name": table_name,
                "total_processed": len(df),
                "inserted_count": inserted_count,
                "updated_count": updated_count,
                "results": results,
                "errors": errors
            }

        except Exception as e:
            logger.error("导入数据到表格失败", error=str(e))
            return {"status": "error", "message": f"导入失败: {str(e)}"}

    async def _process_year_courses(
        self,
        app_token: str,
        table_id: str,
        courses_df: pd.DataFrame,
        year: str,
        course_name_column: str,
        instructor_column: str,
        credits_column: str,
        course_type_column: str,
        is_incremental: bool
    ) -> Dict[str, Any]:
        """处理特定学年的课程"""
        results = []
        errors = []
        inserted_count = 0
        updated_count = 0

        for index, course_data in courses_df.iterrows():
            try:
                course_name = course_data.get(course_name_column)
                if not course_name:
                    continue

                # 准备字段
                fields = {}

                # 必填字段
                fields["课程名称"] = course_name

                # 可选字段
                if year:
                    fields["学年"] = year
                if instructor_column in course_data and pd.notna(course_data[instructor_column]):
                    fields["授课教师"] = str(course_data[instructor_column])
                if credits_column in course_data and pd.notna(course_data[credits_column]):
                    fields["学分"] = float(course_data[credits_column])
                if course_type_column in course_data and pd.notna(course_data[course_type_column]):
                    fields["课程性质"] = str(course_data[course_type_column])

                # 检查课程是否已存在
                if is_incremental:
                    existing_record = await self.feishu.search_bitable_record(
                        app_token=app_token,
                        table_id=table_id,
                        field_name="课程名称",
                        value=course_name
                    )

                    if existing_record:
                        # 更新记录
                        update_result = await self.feishu.update_bitable_record(
                            app_token=app_token,
                            table_id=table_id,
                            record_id=existing_record["record_id"],
                            fields=fields
                        )
                        results.append({
                            "course_name": course_name,
                            "action": "update",
                            "record_id": existing_record["record_id"]
                        })
                        updated_count += 1
                    else:
                        # 插入新记录
                        insert_result = await self.feishu.add_bitable_record(
                            app_token=app_token,
                            table_id=table_id,
                            fields=fields
                        )
                        results.append({
                            "course_name": course_name,
                            "action": "insert",
                            "record_id": insert_result["record_id"]
                        })
                        inserted_count += 1
                else:
                    # 全量覆盖，直接插入
                    insert_result = await self.feishu.add_bitable_record(
                        app_token=app_token,
                        table_id=table_id,
                        fields=fields
                    )
                    results.append({
                        "course_name": course_name,
                        "action": "insert",
                        "record_id": insert_result["record_id"]
                    })
                    inserted_count += 1

            except Exception as e:
                errors.append({
                    "course_name": course_data.get(course_name_column),
                    "error": str(e)
                })

        return {
            "results": results,
            "errors": errors,
            "inserted_count": inserted_count,
            "updated_count": updated_count
        }

    async def import_from_config(self, config_path: str) -> Dict[str, Any]:
        """从配置文件导入数据"""
        try:
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            import_data = config.get("import", {})
            logger.info("读取导入配置", file_path=config_path, table_count=len(import_data))

            all_results = []
            all_errors = []

            for table_name, table_config in import_data.items():
                try:
                    file_path = table_config.get("file_path")
                    if not file_path or not os.path.exists(file_path):
                        logger.warning("文件不存在", table_name=table_name, file_path=file_path)
                        all_errors.append({
                            "table_name": table_name,
                            "error": "文件不存在"
                        })
                        continue

                    # 读取文件
                    file_type = file_path.lower()
                    if file_type.endswith('.xlsx'):
                        df = self.read_excel_file(file_path)
                    elif file_type.endswith('.csv'):
                        df = self.read_csv_file(file_path)
                    else:
                        logger.error("不支持的文件格式", file_path=file_path)
                        all_errors.append({
                            "table_name": table_name,
                            "error": "不支持的文件格式"
                        })
                        continue

                    # 列名映射
                    column_mapping = table_config.get("column_mapping", {})
                    if column_mapping:
                        df = self.map_columns(df, column_mapping)

                    # 验证数据
                    validation = self.validate_course_data(df)
                    if not validation["validation_passed"]:
                        logger.error("数据验证失败", table_name=table_name, validation=validation)
                        all_errors.append({
                            "table_name": table_name,
                            "error": f"数据验证失败: {validation.get('error', '未知错误')}"
                        })
                        continue

                    # 导入到表格
                    app_token = table_config.get("app_token")
                    if not app_token:
                        logger.error("缺少 App Token", table_name=table_name)
                        all_errors.append({
                            "table_name": table_name,
                            "error": "缺少 App Token"
                        })
                        continue

                    result = await self.import_to_bitable(
                        app_token=app_token,
                        df=df,
                        table_name=table_name,
                        course_year_column=column_mapping.get("学年", "学年"),
                        course_name_column=column_mapping.get("课程名称", "课程名称"),
                        instructor_column=column_mapping.get("授课教师", "授课教师"),
                        credits_column=column_mapping.get("学分", "学分"),
                        course_type_column=column_mapping.get("课程性质", "课程性质"),
                        is_incremental=table_config.get("incremental", True)
                    )

                    all_results.append(result)

                except Exception as e:
                    logger.error("表格导入失败", table_name=table_name, error=str(e))
                    all_errors.append({
                        "table_name": table_name,
                        "error": str(e)
                    })

            return {
                "total_tables": len(import_data),
                "successful_tables": len([r for r in all_results if "status" not in r]),
                "total_processed": sum(r.get("total_processed", 0) for r in all_results),
                "inserted_count": sum(r.get("inserted_count", 0) for r in all_results),
                "updated_count": sum(r.get("updated_count", 0) for r in all_results),
                "total_errors": len(all_errors),
                "results": all_results,
                "errors": all_errors
            }

        except FileNotFoundError:
            return {"status": "error", "message": f"配置文件不存在: {config_path}"}
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"配置文件格式错误: {str(e)}"}
        except Exception as e:
            return {"status": "error", "message": f"导入失败: {str(e)}"}